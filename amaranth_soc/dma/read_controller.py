"""Generic DMA Read Controller.

Bus-agnostic DMA read controller that generates read requests to a bus
master port and collects completions into a data FIFO.  The actual bus
protocol is handled externally by bus-specific adapters (PCIe, AXI4, etc.).
"""

from amaranth import *
from amaranth.lib.wiring import Component, In, Out
from amaranth.lib.data import StructLayout

from amaranth_stream import Signature as StreamSignature, StreamFIFO

from ..csr import reg as csr_reg, action as csr_action

from .common import split_descriptor_layout, dma_data_signature
from ..utils.reset_inserter import add_reset_domain


__all__ = ["DMAReadController"]


def _bus_read_request_layout(address_width):
    """Layout for a bus read request."""
    return StructLayout(
        {
            "address": address_width,
            "length": 24,
            "user_id": 8,
        }
    )


def _bus_read_completion_layout(data_width):
    """Layout for a bus read completion."""
    return StructLayout(
        {
            "data": data_width,
            "user_id": 8,
        }
    )


class _EnableReg(csr_reg.Register, access="rw"):
    """DMA Reader enable register."""

    enable: csr_reg.Field(csr_action.RW, 1)
    idle: csr_reg.Field(csr_action.R, 1)


def _dma_words_for_bytes(length, data_width):
    """Calculate number of data words needed for a byte length.

    Returns a combinational expression.
    """
    data_width_bytes = data_width // 8
    shift = (data_width_bytes - 1).bit_length()
    return (length + (data_width_bytes - 1)) >> shift


class DMAReadController(Component):
    """Generic DMA Read Controller.

    Reads data from a bus into a stream.  Generates read requests to a
    bus master port and collects completions into a data FIFO.

    Parameters
    ----------
    data_width : :class:`int`
        Width of the data bus in bits.
    address_width : :class:`int`
        Width of the address bus in bits (default 32).
    max_pending_requests : :class:`int`
        Maximum number of outstanding read requests (default 8).
    max_request_size : :class:`int`
        Maximum bytes per read request (default 512).
    data_fifo_depth : :class:`int`
        Depth of the data FIFO in words (default 256).

    Attributes
    ----------
    desc_sink : In stream
        Input stream of split descriptors.
    data_source : Out stream
        Output data stream.
    bus_req_source : Out stream
        Output stream of bus read requests.
    bus_cmp_sink : In stream
        Input stream of bus read completions.
    enable_reg : CSR register
        DMA enable control.
    irq : Out(1)
        Interrupt request (pulsed on descriptor completion).
    """

    def __init__(
        self,
        data_width,
        address_width=32,
        max_pending_requests=8,
        max_request_size=512,
        data_fifo_depth=256,
    ):
        self._data_width = data_width
        self._address_width = address_width
        self._max_pending_requests = max_pending_requests
        self._max_request_size = max_request_size
        self._data_fifo_depth = data_fifo_depth

        # Compute derived parameters
        data_width_bytes = data_width // 8
        self._max_words_per_request = max_request_size // data_width_bytes

        # Stream signatures
        desc_sig = StreamSignature(
            split_descriptor_layout(address_width=address_width),
            has_first_last=True,
        )
        data_sig = dma_data_signature(data_width)
        req_sig = StreamSignature(
            _bus_read_request_layout(address_width),
        )
        cmp_sig = StreamSignature(
            _bus_read_completion_layout(data_width),
            has_first_last=True,
        )

        # CSR
        self.enable_reg = _EnableReg()

        super().__init__(
            {
                "desc_sink": In(desc_sig),
                "data_source": Out(data_sig),
                "bus_req_source": Out(req_sig),
                "bus_cmp_sink": In(cmp_sig),
                "irq": Out(1),
            }
        )

    def elaborate(self, platform):
        m = Module()

        data_width = self._data_width
        data_fifo_depth = self._data_fifo_depth
        max_words_per_request = self._max_words_per_request

        # CSR submodule
        m.submodules.enable_reg = enable_reg = self.enable_reg
        enable = enable_reg.f.enable.data

        # Data FIFO
        data_sig = dma_data_signature(data_width)
        data_fifo = StreamFIFO(data_sig, data_fifo_depth, buffered=True)
        fifo_reset = Signal()
        rst_domain = add_reset_domain(m, fifo_reset)
        m.submodules.data_fifo = DomainRenamer({"sync": rst_domain})(data_fifo)

        # Connect data FIFO output to data_source
        m.d.comb += [
            self.data_source.payload.eq(data_fifo.o_stream.payload),
            self.data_source.valid.eq(data_fifo.o_stream.valid),
            self.data_source.first.eq(data_fifo.o_stream.first),
            self.data_source.last.eq(data_fifo.o_stream.last),
            data_fifo.o_stream.ready.eq(self.data_source.ready),
        ]

        # User ID tracking for first-beat detection
        last_user_id = Signal(8, init=0xFF)
        with m.If(
            self.bus_cmp_sink.valid & self.bus_cmp_sink.first & self.bus_cmp_sink.ready
        ):
            m.d.sync += last_user_id.eq(self.bus_cmp_sink.payload.user_id)

        # Connect bus completions to data FIFO
        with m.If(enable):
            m.d.comb += [
                data_fifo.i_stream.valid.eq(self.bus_cmp_sink.valid),
                self.bus_cmp_sink.ready.eq(data_fifo.i_stream.ready),
                data_fifo.i_stream.payload.eq(self.bus_cmp_sink.payload.data),
                data_fifo.i_stream.first.eq(
                    self.bus_cmp_sink.first
                    & (self.bus_cmp_sink.payload.user_id != last_user_id)
                ),
                data_fifo.i_stream.last.eq(self.bus_cmp_sink.last),
            ]
        with m.Else():
            # Accept and discard incoming completions when disabled
            m.d.comb += self.bus_cmp_sink.ready.eq(1)

        # Pending words tracking
        request_words = Signal(24)
        m.d.comb += request_words.eq(
            _dma_words_for_bytes(self.desc_sink.payload.length, data_width)
        )

        pending_words = Signal(range(data_fifo_depth + 1))
        pending_words_queue = Signal.like(pending_words)
        pending_words_dequeue = Signal.like(pending_words)

        m.d.comb += [
            # Queue pending words as read requests are emitted
            pending_words_queue.eq(
                Mux(self.desc_sink.valid & self.desc_sink.ready, request_words, 0)
            ),
            # Dequeue pending words as data is consumed from FIFO
            pending_words_dequeue.eq(
                Mux(data_fifo.o_stream.valid & data_fifo.o_stream.ready, 1, 0)
            ),
        ]

        m.d.sync += pending_words.eq(
            pending_words + pending_words_queue - pending_words_dequeue
        )
        with m.If(~enable):
            m.d.sync += pending_words.eq(0)

        # Request data path (always driven, valid controlled by FSM)
        m.d.comb += [
            self.bus_req_source.payload.user_id.eq(self.desc_sink.payload.user_id),
            self.bus_req_source.payload.address.eq(self.desc_sink.payload.address),
            self.bus_req_source.payload.length.eq(self.desc_sink.payload.length),
        ]

        # FSM
        with m.FSM(name="reader") as fsm:
            with m.State("IDLE"):
                # Reset FIFO when disabled
                with m.If(~enable):
                    m.d.comb += fifo_reset.eq(1)
                # Wait for descriptor and enough space
                with m.Elif(
                    self.desc_sink.valid
                    & (pending_words < (data_fifo_depth - max_words_per_request))
                ):
                    m.next = "REQUEST"

            with m.State("REQUEST"):
                m.d.comb += self.bus_req_source.valid.eq(1)
                # When request is accepted
                with m.If(self.bus_req_source.ready):
                    # Accept descriptor
                    m.d.comb += self.desc_sink.ready.eq(1)
                    # Return to idle
                    m.next = "IDLE"

        # Report idle status
        m.d.sync += enable_reg.f.idle.r_data.eq(fsm.ongoing("IDLE"))

        # IRQ on descriptor completion
        m.d.comb += self.irq.eq(
            self.desc_sink.valid
            & self.desc_sink.ready
            & self.desc_sink.last
            & ~self.desc_sink.payload.irq_disable
        )

        return m
