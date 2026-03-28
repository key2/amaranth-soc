"""Generic DMA Write Controller.

Bus-agnostic DMA write controller that buffers incoming data and issues
write requests to a bus master port.  The actual bus protocol is handled
externally by bus-specific adapters (PCIe, AXI4, etc.).
"""

from amaranth import *
from amaranth.lib.wiring import Component, In, Out
from amaranth.lib.data import StructLayout

from amaranth_stream import Signature as StreamSignature, StreamFIFO

from ..csr import reg as csr_reg, action as csr_action

from .common import split_descriptor_layout, dma_data_signature
from ..utils.reset_inserter import add_reset_domain


__all__ = ["DMAWriteController"]


def _bus_write_request_layout(address_width, data_width):
    """Layout for a bus write request (includes data)."""
    return StructLayout(
        {
            "address": address_width,
            "length": 24,
            "user_id": 8,
            "data": data_width,
        }
    )


class _EnableReg(csr_reg.Register, access="rw"):
    """DMA Writer enable register."""

    enable: csr_reg.Field(csr_action.RW, 1)
    idle: csr_reg.Field(csr_action.R, 1)


def _dma_words_for_bytes(length, data_width):
    """Calculate number of data words needed for a byte length."""
    data_width_bytes = data_width // 8
    shift = (data_width_bytes - 1).bit_length()
    return (length + (data_width_bytes - 1)) >> shift


class DMAWriteController(Component):
    """Generic DMA Write Controller.

    Writes data from a stream to a bus.  Buffers incoming data in a FIFO
    and issues write requests when enough data is available.

    Parameters
    ----------
    data_width : :class:`int`
        Width of the data bus in bits.
    address_width : :class:`int`
        Width of the address bus in bits (default 32).
    max_request_size : :class:`int`
        Maximum bytes per write request (default 512).
    data_fifo_depth : :class:`int`
        Depth of the data FIFO in words (default 256).

    Attributes
    ----------
    desc_sink : In stream
        Input stream of split descriptors.
    data_sink : In stream
        Input data stream.
    bus_req_source : Out stream
        Output stream of bus write requests (with data).
    enable_reg : CSR register
        DMA enable control.
    irq : Out(1)
        Interrupt request (pulsed on descriptor completion).
    """

    def __init__(
        self, data_width, address_width=32, max_request_size=512, data_fifo_depth=256
    ):
        self._data_width = data_width
        self._address_width = address_width
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
            _bus_write_request_layout(address_width, data_width),
            has_first_last=True,
        )

        # CSR
        self.enable_reg = _EnableReg()

        super().__init__(
            {
                "desc_sink": In(desc_sig),
                "data_sink": In(data_sig),
                "bus_req_source": Out(req_sig),
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

        # Data FIFO (buffers incoming data before writing)
        data_sig = dma_data_signature(data_width)
        data_fifo = StreamFIFO(data_sig, data_fifo_depth, buffered=True)
        fifo_reset = Signal()
        rst_domain = add_reset_domain(m, fifo_reset)
        m.submodules.data_fifo = DomainRenamer({"sync": rst_domain})(data_fifo)

        # By default, accept incoming data when disabled
        m.d.comb += self.data_sink.ready.eq(1)
        # When enabled, connect data sink to FIFO
        with m.If(enable):
            m.d.comb += [
                data_fifo.i_stream.payload.eq(self.data_sink.payload),
                data_fifo.i_stream.valid.eq(self.data_sink.valid),
                data_fifo.i_stream.first.eq(self.data_sink.first),
                data_fifo.i_stream.last.eq(self.data_sink.last),
                self.data_sink.ready.eq(data_fifo.i_stream.ready),
            ]

        # Request word count
        request_words = Signal(24)
        m.d.comb += request_words.eq(
            _dma_words_for_bytes(self.desc_sink.payload.length, data_width)
        )

        # Request counter (tracks words within current request)
        req_count = Signal(24)

        # Early termination on last data beat
        terminate = Signal()
        m.d.comb += terminate.eq(
            data_fifo.o_stream.last & ~self.desc_sink.payload.last_disable
        )

        # Request data path (always driven)
        m.d.comb += [
            self.bus_req_source.payload.user_id.eq(self.desc_sink.payload.user_id),
            self.bus_req_source.payload.address.eq(self.desc_sink.payload.address),
            self.bus_req_source.payload.length.eq(self.desc_sink.payload.length),
            self.bus_req_source.payload.data.eq(data_fifo.o_stream.payload),
            self.bus_req_source.first.eq(req_count == 0),
            self.bus_req_source.last.eq(req_count == (request_words - 1)),
        ]

        # FSM
        with m.FSM(name="writer") as fsm:
            with m.State("IDLE"):
                # Reset request count
                m.d.sync += req_count.eq(0)
                # Reset FIFO when disabled
                with m.If(~enable):
                    m.d.comb += fifo_reset.eq(1)
                # Wait for descriptor and enough data
                with m.Elif(self.desc_sink.valid & (data_fifo.level >= request_words)):
                    m.next = "WRITE"

            with m.State("WRITE"):
                m.d.comb += self.bus_req_source.valid.eq(1)
                # When request is accepted
                with m.If(self.bus_req_source.ready):
                    # Increment request count
                    m.d.sync += req_count.eq(req_count + 1)
                    # Accept data (only when not terminated)
                    m.d.comb += data_fifo.o_stream.ready.eq(~terminate)
                    # When last word
                    with m.If(self.bus_req_source.last):
                        # Accept descriptor
                        m.d.comb += self.desc_sink.ready.eq(1)
                        # Force accept data
                        m.d.comb += data_fifo.o_stream.ready.eq(1)
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
