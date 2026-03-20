"""AXI burst-to-beat address generator per IHI0022L §A3.4.1."""

from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out

from .bus import AXIBurst


__all__ = ["AXIBurst2Beat"]


class AXIBurst2Beat(wiring.Component):
    """Converts AXI4 burst addresses to per-beat addresses.

    Given a burst start address, length, size, and type, generates
    the address for each beat in the burst.

    This is a combinational/registered helper used internally by
    AXI4ToAXI4Lite and other burst-aware components.

    Parameters
    ----------
    addr_width : int
        Address width in bits.
    data_width : int
        Data width in bits (determines natural alignment).

    Members
    -------
    addr : ``In(addr_width)``
        Start address of the burst (latched on ``first``).
    len : ``In(8)``
        Burst length minus one (AxLEN).
    size : ``In(3)``
        Burst size encoding (AxSIZE).
    burst : ``In(2)``
        Burst type (AxBURST): FIXED, INCR, or WRAP.
    first : ``In(1)``
        Pulse high for one cycle to load a new burst.
    next : ``In(1)``
        Pulse high to advance to the next beat.
    next_addr : ``Out(addr_width)``
        Address for the current beat.
    last : ``Out(1)``
        High when the current beat is the final beat.
    """

    def __init__(self, *, addr_width, data_width):
        if not isinstance(addr_width, int) or addr_width < 1:
            raise TypeError(f"Address width must be a positive integer, not {addr_width!r}")
        if not isinstance(data_width, int) or data_width < 8:
            raise ValueError(f"Data width must be >= 8, not {data_width!r}")
        if data_width & (data_width - 1) != 0:
            raise ValueError(f"Data width must be a power of 2, not {data_width!r}")

        self._addr_width = addr_width
        self._data_width = data_width

        super().__init__({
            # Inputs
            "addr":      In(addr_width),
            "len":       In(8),
            "size":      In(3),
            "burst":     In(2),
            "first":     In(1),
            "next":      In(1),
            # Outputs
            "next_addr": Out(addr_width),
            "last":      Out(1),
        })

    @property
    def addr_width(self):
        return self._addr_width

    @property
    def data_width(self):
        return self._data_width

    def elaborate(self, platform):
        m = Module()

        addr_width = self._addr_width

        # Internal registered state
        beat_count = Signal(8, name="beat_count")
        beat_addr  = Signal(addr_width, name="beat_addr")
        burst_len  = Signal(8, name="burst_len")
        burst_size = Signal(3, name="burst_size")
        burst_type = Signal(2, name="burst_type")
        start_addr = Signal(addr_width, name="start_addr")

        # Compute the byte increment: 1 << size
        size_bytes = Signal(addr_width, name="size_bytes")
        m.d.comb += size_bytes.eq(1 << burst_size)

        # Compute the incremented address
        incr_addr = Signal(addr_width, name="incr_addr")
        m.d.comb += incr_addr.eq(beat_addr + size_bytes)

        # Compute wrap mask: (burst_len + 1) * size_bytes - 1
        # This defines the wrapping region size.
        # wrap_boundary = start_addr & ~wrap_mask
        # wrapped_addr = wrap_boundary | (incr_addr & wrap_mask)
        wrap_mask = Signal(addr_width, name="wrap_mask")
        m.d.comb += wrap_mask.eq(((burst_len + 1) << burst_size) - 1)

        wrap_boundary = Signal(addr_width, name="wrap_boundary")
        m.d.comb += wrap_boundary.eq(start_addr & ~wrap_mask)

        wrapped_addr = Signal(addr_width, name="wrapped_addr")
        m.d.comb += wrapped_addr.eq(wrap_boundary | (incr_addr & wrap_mask))

        # Select next address based on burst type
        next_beat_addr = Signal(addr_width, name="next_beat_addr")
        with m.Switch(burst_type):
            with m.Case(AXIBurst.FIXED):
                m.d.comb += next_beat_addr.eq(beat_addr)  # stays the same
            with m.Case(AXIBurst.INCR):
                m.d.comb += next_beat_addr.eq(incr_addr)
            with m.Case(AXIBurst.WRAP):
                m.d.comb += next_beat_addr.eq(wrapped_addr)
            with m.Default():
                m.d.comb += next_beat_addr.eq(incr_addr)  # treat as INCR

        # Output: current beat address
        m.d.comb += self.next_addr.eq(beat_addr)

        # Output: last beat indicator
        m.d.comb += self.last.eq(beat_count == burst_len)

        # On first pulse, latch all burst parameters and set initial address
        with m.If(self.first):
            m.d.sync += [
                start_addr.eq(self.addr),
                beat_addr.eq(self.addr),
                burst_len.eq(self.len),
                burst_size.eq(self.size),
                burst_type.eq(self.burst),
                beat_count.eq(0),
            ]
        with m.Elif(self.next):
            # Advance to next beat
            m.d.sync += [
                beat_addr.eq(next_beat_addr),
                beat_count.eq(beat_count + 1),
            ]

        return m
