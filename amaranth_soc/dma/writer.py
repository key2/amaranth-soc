"""DMA Write Engine — writes data to memory via AXI4 bus."""

from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.utils import exact_log2

from ..axi.bus import AXI4Signature

__all__ = ["DMAWriter"]


class DMAWriter(wiring.Component):
    """DMA Write Engine.

    Accepts data via a stream interface (data_in / data_valid / data_ready)
    and writes it to memory via an AXI4 bus.

    Parameters
    ----------
    addr_width : int
        Address width for the AXI4 bus.
    data_width : int
        Data width for the AXI4 bus (must be power of 2, >= 8).
    max_burst_len : int
        Maximum AXI burst length in beats (1–256, default 16).

    Members
    -------
    bus : ``Out(AXI4Signature(...))``
        AXI4 master port (write channels used, read channels left idle).
    start : ``In(1)``
        Pulse high for one cycle to begin a transfer.
    dst_addr : ``In(addr_width)``
        Destination address (latched on *start*).
    length : ``In(24)``
        Transfer length in beats (latched on *start*).
    busy : ``Out(1)``
        High while a transfer is in progress.
    done : ``Out(1)``
        Pulsed high for one cycle when the transfer completes.
    data_in : ``In(data_width)``
        Input data to write.
    data_valid : ``In(1)``
        High when *data_in* is valid.
    data_ready : ``Out(1)``
        Backpressure to the producer.
    """

    def __init__(self, *, addr_width=32, data_width=32, max_burst_len=16):
        if not isinstance(addr_width, int) or addr_width < 1:
            raise TypeError(
                f"Address width must be a positive integer, not {addr_width!r}")
        if not isinstance(data_width, int) or data_width < 8:
            raise ValueError(
                f"Data width must be an integer >= 8, not {data_width!r}")
        if data_width & (data_width - 1) != 0:
            raise ValueError(
                f"Data width must be a power of 2, not {data_width!r}")
        if not isinstance(max_burst_len, int) or not (1 <= max_burst_len <= 256):
            raise ValueError(
                f"max_burst_len must be 1..256, not {max_burst_len!r}")

        self._addr_width = addr_width
        self._data_width = data_width
        self._max_burst_len = max_burst_len

        super().__init__({
            # AXI4 master port (full signature; read channels stay idle)
            "bus": Out(AXI4Signature(addr_width=addr_width,
                                     data_width=data_width)),
            # Control
            "start":    In(1),
            "dst_addr": In(addr_width),
            "length":   In(24),
            # Status
            "busy":     Out(1),
            "done":     Out(1),
            # Input data stream
            "data_in":    In(data_width),
            "data_valid": In(1),
            "data_ready": Out(1),
        })

    @property
    def addr_width(self):
        return self._addr_width

    @property
    def data_width(self):
        return self._data_width

    @property
    def max_burst_len(self):
        return self._max_burst_len

    def elaborate(self, platform):
        m = Module()

        beats_remaining = Signal(24)
        current_addr = Signal(self._addr_width)
        bytes_per_beat = self._data_width // 8

        # Burst tracking
        burst_beats = Signal(9)       # total beats in current burst (1..256)
        burst_beat_cnt = Signal(9)    # beats sent so far in current burst

        with m.FSM():
            with m.State("IDLE"):
                m.d.comb += [
                    self.done.eq(0),
                    self.busy.eq(0),
                ]
                with m.If(self.start):
                    m.d.sync += [
                        current_addr.eq(self.dst_addr),
                        beats_remaining.eq(self.length),
                    ]
                    m.next = "AW_PHASE"

            with m.State("AW_PHASE"):
                m.d.comb += self.busy.eq(1)

                # Calculate burst length: min(remaining, max_burst_len)
                burst_len_m1 = Signal(8)  # AXI awlen = beats - 1
                cur_burst_beats = Signal(9)
                with m.If(beats_remaining >= self._max_burst_len):
                    m.d.comb += burst_len_m1.eq(self._max_burst_len - 1)
                    m.d.comb += cur_burst_beats.eq(self._max_burst_len)
                with m.Else():
                    m.d.comb += burst_len_m1.eq(beats_remaining - 1)
                    m.d.comb += cur_burst_beats.eq(beats_remaining)

                m.d.comb += [
                    self.bus.awaddr.eq(current_addr),
                    self.bus.awlen.eq(burst_len_m1),
                    self.bus.awsize.eq(exact_log2(bytes_per_beat)),
                    self.bus.awburst.eq(0b01),  # INCR
                    self.bus.awvalid.eq(1),
                ]
                with m.If(self.bus.awready):
                    m.d.sync += [
                        burst_beats.eq(cur_burst_beats),
                        burst_beat_cnt.eq(0),
                    ]
                    m.next = "W_PHASE"

            with m.State("W_PHASE"):
                m.d.comb += [
                    self.busy.eq(1),
                    self.bus.wdata.eq(self.data_in),
                    self.bus.wstrb.eq((1 << bytes_per_beat) - 1),
                    self.bus.wvalid.eq(self.data_valid),
                    self.data_ready.eq(self.bus.wready),
                    self.bus.wlast.eq(burst_beat_cnt == (burst_beats - 1)),
                ]
                with m.If(self.data_valid & self.bus.wready):
                    m.d.sync += burst_beat_cnt.eq(burst_beat_cnt + 1)
                    with m.If(burst_beat_cnt == (burst_beats - 1)):
                        # Last beat of this burst
                        m.next = "B_PHASE"

            with m.State("B_PHASE"):
                m.d.comb += [
                    self.busy.eq(1),
                    self.bus.bready.eq(1),
                ]
                with m.If(self.bus.bvalid):
                    # Update address and remaining count
                    m.d.sync += [
                        beats_remaining.eq(beats_remaining - burst_beats),
                        current_addr.eq(current_addr + (burst_beats * bytes_per_beat)),
                    ]
                    with m.If(beats_remaining == burst_beats):
                        # This was the last burst
                        m.next = "DONE"
                    with m.Else():
                        m.next = "AW_PHASE"

            with m.State("DONE"):
                m.d.comb += [
                    self.done.eq(1),
                    self.busy.eq(0),
                ]
                m.next = "IDLE"

        return m
