"""AXI4-Lite timeout watchdog.

Monitors an AXI4-Lite bus and generates an error response if a transaction
doesn't complete within the timeout period.
"""

from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out

from .bus import AXI4LiteSignature, AXIResp


__all__ = ["AXI4Timeout"]


class AXI4Timeout(wiring.Component):
    """AXI4-Lite timeout watchdog.

    Sits between a master and slave as a transparent pass-through.
    Monitors AXI4-Lite transactions and generates a SLVERR response
    if a transaction doesn't complete within the timeout period.

    Parameters
    ----------
    addr_width : int
        Address width in bits.
    data_width : int
        Data width (32 or 64).
    timeout : int
        Timeout in clock cycles (default 1024).

    Members
    -------
    bus : ``In(AXI4LiteSignature(...))``
        Upstream (master-facing) port.
    sub : ``Out(AXI4LiteSignature(...))``
        Downstream (slave-facing) port.
    """

    def __init__(self, *, addr_width, data_width, timeout=1024):
        if not isinstance(addr_width, int) or addr_width < 0:
            raise TypeError(f"Address width must be a non-negative integer, not {addr_width!r}")
        if data_width not in (32, 64):
            raise ValueError(f"Data width must be one of 32, 64, not {data_width!r}")
        if not isinstance(timeout, int) or timeout < 1:
            raise ValueError(f"Timeout must be a positive integer, not {timeout!r}")

        self._addr_width = addr_width
        self._data_width = data_width
        self._timeout = timeout

        super().__init__({
            "bus": In(AXI4LiteSignature(addr_width=addr_width, data_width=data_width)),
            "sub": Out(AXI4LiteSignature(addr_width=addr_width, data_width=data_width)),
        })

    @property
    def addr_width(self):
        return self._addr_width

    @property
    def data_width(self):
        return self._data_width

    @property
    def timeout(self):
        return self._timeout

    def elaborate(self, platform):
        m = Module()

        bus = self.bus
        sub = self.sub

        # --- Write path timeout ---
        wr_counter = Signal(range(self._timeout + 1), name="wr_counter")
        wr_active = Signal(name="wr_active")
        wr_timed_out = Signal(name="wr_timed_out")

        # --- Read path timeout ---
        rd_counter = Signal(range(self._timeout + 1), name="rd_counter")
        rd_active = Signal(name="rd_active")
        rd_timed_out = Signal(name="rd_timed_out")

        # =====================================================================
        # Write path
        # =====================================================================
        # Normal pass-through for AW channel (when not timed out)
        with m.If(~wr_timed_out):
            m.d.comb += [
                sub.awaddr.eq(bus.awaddr),
                sub.awprot.eq(bus.awprot),
                sub.awvalid.eq(bus.awvalid),
                bus.awready.eq(sub.awready),
            ]
        with m.Else():
            # Timed out: accept AW from master but don't forward
            m.d.comb += [
                sub.awvalid.eq(0),
                bus.awready.eq(0),
            ]

        # Normal pass-through for W channel (when not timed out)
        with m.If(~wr_timed_out):
            m.d.comb += [
                sub.wdata.eq(bus.wdata),
                sub.wstrb.eq(bus.wstrb),
                sub.wvalid.eq(bus.wvalid),
                bus.wready.eq(sub.wready),
            ]
        with m.Else():
            m.d.comb += [
                sub.wvalid.eq(0),
                bus.wready.eq(0),
            ]

        # B channel: either pass-through or generate SLVERR on timeout
        with m.If(wr_timed_out):
            m.d.comb += [
                bus.bresp.eq(AXIResp.SLVERR),
                bus.bvalid.eq(1),
                sub.bready.eq(0),
            ]
        with m.Else():
            m.d.comb += [
                bus.bresp.eq(sub.bresp),
                bus.bvalid.eq(sub.bvalid),
                sub.bready.eq(bus.bready),
            ]

        # Write timeout FSM
        with m.FSM(name="wr_timeout"):
            with m.State("WR_IDLE"):
                m.d.sync += wr_timed_out.eq(0)
                # Start monitoring on AW handshake
                with m.If(bus.awvalid & bus.awready & ~wr_timed_out):
                    m.d.sync += [
                        wr_counter.eq(0),
                        wr_active.eq(1),
                    ]
                    m.next = "WR_MONITOR"

            with m.State("WR_MONITOR"):
                # Increment counter
                m.d.sync += wr_counter.eq(wr_counter + 1)

                # Check for normal completion (B handshake)
                with m.If(bus.bvalid & bus.bready):
                    m.d.sync += wr_active.eq(0)
                    m.next = "WR_IDLE"

                # Check for timeout
                with m.If(wr_counter >= self._timeout - 1):
                    m.d.sync += wr_timed_out.eq(1)
                    m.next = "WR_TIMEOUT_RESP"

            with m.State("WR_TIMEOUT_RESP"):
                # Generate SLVERR and wait for master to accept
                with m.If(bus.bready):
                    m.d.sync += [
                        wr_timed_out.eq(0),
                        wr_active.eq(0),
                    ]
                    m.next = "WR_IDLE"

        # =====================================================================
        # Read path
        # =====================================================================
        # Normal pass-through for AR channel (when not timed out)
        with m.If(~rd_timed_out):
            m.d.comb += [
                sub.araddr.eq(bus.araddr),
                sub.arprot.eq(bus.arprot),
                sub.arvalid.eq(bus.arvalid),
                bus.arready.eq(sub.arready),
            ]
        with m.Else():
            m.d.comb += [
                sub.arvalid.eq(0),
                bus.arready.eq(0),
            ]

        # R channel: either pass-through or generate SLVERR on timeout
        with m.If(rd_timed_out):
            m.d.comb += [
                bus.rdata.eq(0),
                bus.rresp.eq(AXIResp.SLVERR),
                bus.rvalid.eq(1),
                sub.rready.eq(0),
            ]
        with m.Else():
            m.d.comb += [
                bus.rdata.eq(sub.rdata),
                bus.rresp.eq(sub.rresp),
                bus.rvalid.eq(sub.rvalid),
                sub.rready.eq(bus.rready),
            ]

        # Read timeout FSM
        with m.FSM(name="rd_timeout"):
            with m.State("RD_IDLE"):
                m.d.sync += rd_timed_out.eq(0)
                # Start monitoring on AR handshake
                with m.If(bus.arvalid & bus.arready & ~rd_timed_out):
                    m.d.sync += [
                        rd_counter.eq(0),
                        rd_active.eq(1),
                    ]
                    m.next = "RD_MONITOR"

            with m.State("RD_MONITOR"):
                # Increment counter
                m.d.sync += rd_counter.eq(rd_counter + 1)

                # Check for normal completion (R handshake)
                with m.If(bus.rvalid & bus.rready):
                    m.d.sync += rd_active.eq(0)
                    m.next = "RD_IDLE"

                # Check for timeout
                with m.If(rd_counter >= self._timeout - 1):
                    m.d.sync += rd_timed_out.eq(1)
                    m.next = "RD_TIMEOUT_RESP"

            with m.State("RD_TIMEOUT_RESP"):
                # Generate SLVERR and wait for master to accept
                with m.If(bus.rready):
                    m.d.sync += [
                        rd_timed_out.eq(0),
                        rd_active.eq(0),
                    ]
                    m.next = "RD_IDLE"

        return m
