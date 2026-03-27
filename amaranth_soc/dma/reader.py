"""DMA Read Engine — reads data from memory via AXI4 bus."""

from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.utils import exact_log2

from ..axi.bus import AXI4Signature

__all__ = ["DMAReader"]


class DMAReader(wiring.Component):
    """DMA Read Engine.

    Reads data from memory via an AXI4 bus and outputs it as a stream
    (data_out / data_valid / data_ready handshake).

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
        AXI4 master port (read channels used, write channels left idle).
    start : ``In(1)``
        Pulse high for one cycle to begin a transfer.
    src_addr : ``In(addr_width)``
        Source address (latched on *start*).
    length : ``In(24)``
        Transfer length in beats (latched on *start*).
    busy : ``Out(1)``
        High while a transfer is in progress.
    done : ``Out(1)``
        Pulsed high for one cycle when the transfer completes.
    data_out : ``Out(data_width)``
        Output data from the read.
    data_valid : ``Out(1)``
        High when *data_out* is valid.
    data_ready : ``In(1)``
        Backpressure from the consumer.
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
            # AXI4 master port (full signature; write channels stay idle)
            "bus": Out(AXI4Signature(addr_width=addr_width,
                                     data_width=data_width)),
            # Control
            "start":    In(1),
            "src_addr": In(addr_width),
            "length":   In(24),
            # Status
            "busy":     Out(1),
            "done":     Out(1),
            # Output data stream
            "data_out":   Out(data_width),
            "data_valid": Out(1),
            "data_ready": In(1),
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
        burst_beats = Signal(9)  # actual number of beats in this burst (1..256)

        with m.FSM():
            with m.State("IDLE"):
                m.d.comb += [
                    self.done.eq(0),
                    self.busy.eq(0),
                ]
                with m.If(self.start):
                    m.d.sync += [
                        current_addr.eq(self.src_addr),
                        beats_remaining.eq(self.length),
                    ]
                    m.next = "AR_PHASE"

            with m.State("AR_PHASE"):
                m.d.comb += self.busy.eq(1)

                # Calculate burst length: min(remaining, max_burst_len)
                burst_len_m1 = Signal(8)  # AXI arlen = beats - 1
                with m.If(beats_remaining >= self._max_burst_len):
                    m.d.comb += burst_len_m1.eq(self._max_burst_len - 1)
                    m.d.comb += burst_beats.eq(self._max_burst_len)
                with m.Else():
                    m.d.comb += burst_len_m1.eq(beats_remaining - 1)
                    m.d.comb += burst_beats.eq(beats_remaining)

                m.d.comb += [
                    self.bus.araddr.eq(current_addr),
                    self.bus.arlen.eq(burst_len_m1),
                    self.bus.arsize.eq(exact_log2(bytes_per_beat)),
                    self.bus.arburst.eq(0b01),  # INCR
                    self.bus.arvalid.eq(1),
                ]
                with m.If(self.bus.arready):
                    m.d.sync += [
                        beats_remaining.eq(beats_remaining - burst_beats),
                        current_addr.eq(current_addr + (burst_beats * bytes_per_beat)),
                    ]
                    m.next = "R_PHASE"

            with m.State("R_PHASE"):
                m.d.comb += [
                    self.busy.eq(1),
                    self.data_out.eq(self.bus.rdata),
                    self.data_valid.eq(self.bus.rvalid),
                    self.bus.rready.eq(self.data_ready),
                ]
                with m.If(self.bus.rvalid & self.data_ready & self.bus.rlast):
                    with m.If(beats_remaining == 0):
                        m.next = "DONE"
                    with m.Else():
                        m.next = "AR_PHASE"

            with m.State("DONE"):
                m.d.comb += [
                    self.done.eq(1),
                    self.busy.eq(0),
                ]
                m.next = "IDLE"

        return m
