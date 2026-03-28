"""DMA Descriptor Splitter.

Splits large DMA descriptors into bus-sized chunks of at most *max_size*
bytes each.  Adds an auto-incrementing ``user_id`` field for packet tracking.
"""

from amaranth import *
from amaranth.lib.wiring import Component, In, Out

from amaranth_stream import Signature as StreamSignature

from .common import descriptor_layout, split_descriptor_layout


__all__ = ["DMADescriptorSplitter"]


class DMADescriptorSplitter(Component):
    """DMA Descriptor Splitter.

    Splits descriptors into shorter descriptors of at most *max_size* bytes.
    Adds an auto-incrementing ``user_id`` field for packet tracking.

    Parameters
    ----------
    max_size : :class:`int`
        Maximum transfer size per chunk (bytes).
    address_width : :class:`int`
        Width of the address field (default 32).

    Attributes
    ----------
    sink : In stream
        Input stream of descriptors.
    source : Out stream
        Output stream of split descriptors (with ``user_id``).
    terminate : In(1)
        Early termination signal.
    """

    def __init__(self, max_size, address_width=32):
        self._max_size = max_size
        self._address_width = address_width

        desc_sig = StreamSignature(
            descriptor_layout(address_width=address_width),
            has_first_last=True,
        )
        split_sig = StreamSignature(
            split_descriptor_layout(address_width=address_width),
            has_first_last=True,
        )

        super().__init__(
            {
                "sink": In(desc_sig),
                "source": Out(split_sig),
                "terminate": In(1),
            }
        )

    def elaborate(self, platform):
        m = Module()

        max_size = self._max_size
        sink = self.sink
        source = self.source

        # Internal signals
        length = Signal(24)
        length_next = Signal(24)

        # length_next computed outside FSM for timing
        m.d.comb += length_next.eq(length - max_size)

        # Pass through irq_disable and last_disable combinationally
        m.d.comb += [
            source.payload.irq_disable.eq(sink.payload.irq_disable),
            source.payload.last_disable.eq(sink.payload.last_disable),
        ]

        with m.FSM(name="splitter") as fsm:
            with m.State("IDLE"):
                # Set/clear signals for next descriptor
                m.d.sync += [
                    source.first.eq(1),
                    source.last.eq(0),
                    source.payload.address.eq(sink.payload.address),
                    length.eq(sink.payload.length),
                ]
                with m.If(sink.payload.length > max_size):
                    m.d.sync += source.payload.length.eq(max_size)
                with m.Else():
                    m.d.sync += [
                        source.last.eq(1),
                        source.payload.length.eq(sink.payload.length),
                    ]
                # Wait for a descriptor and go to RUN
                with m.If(sink.valid):
                    m.next = "RUN"

            with m.State("RUN"):
                m.d.comb += source.valid.eq(1)
                # When descriptor is accepted
                with m.If(source.ready):
                    # Clear first
                    m.d.sync += source.first.eq(0)
                    # Update address
                    m.d.sync += source.payload.address.eq(
                        source.payload.address + max_size
                    )
                    # Update length/last
                    m.d.sync += length.eq(length_next)
                    with m.If(length_next > max_size):
                        m.d.sync += source.payload.length.eq(max_size)
                    with m.Else():
                        m.d.sync += [
                            source.last.eq(1),
                            source.payload.length.eq(length_next),
                        ]
                    # On last or terminate
                    with m.If(source.last | self.terminate):
                        # Accept descriptor
                        m.d.comb += sink.ready.eq(1)
                        # Increment user_id
                        m.d.sync += source.payload.user_id.eq(
                            source.payload.user_id + 1
                        )
                        # Return to IDLE
                        m.next = "IDLE"

        return m
