"""AXI timeout watchdogs.

Monitors AXI4-Lite and AXI4 buses and generates error responses if
transactions don't complete within the timeout period.
"""

from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out

from .bus import AXI4LiteSignature, AXI4Signature, AXIResp


__all__ = ["AXI4LiteTimeout", "AXI4Timeout"]


class AXI4LiteTimeout(wiring.Component):
    """AXI4-Lite timeout watchdog.

    Sits between a master and slave as a transparent pass-through.
    Monitors AXI4-Lite transactions and generates a SLVERR response
    if a transaction doesn't complete within the timeout period.

    Parameters
    ----------
    addr_width : int
        Address width in bits.
    data_width : int, power of 2, >= 32
        Data width. Must be a power of 2 and at least 32.
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
        if not isinstance(data_width, int) or data_width < 32:
            raise ValueError(f"Data width must be a positive integer >= 32, not {data_width!r}")
        if data_width & (data_width - 1) != 0:
            raise ValueError(f"Data width must be a power of 2, not {data_width!r}")
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


class AXI4Timeout(wiring.Component):
    """AXI4 Full timeout wrapper.

    Wraps an AXI4 subordinate interface and generates DECERR responses
    if the subordinate doesn't complete a burst within the timeout period.

    The timeout counter starts when an address phase completes (AW/AR handshake)
    and resets when the corresponding response completes (B handshake for writes,
    RLAST for reads).

    Parameters
    ----------
    addr_width : int
        Address width.
    data_width : int, power of 2, >= 8
        Data width.
    id_width : int
        ID signal width (default 0).
    timeout : int
        Timeout in clock cycles (default 1024).

    Members
    -------
    bus : ``In(AXI4Signature(...))``
        Upstream (master-facing) port.
    sub : ``Out(AXI4Signature(...))``
        Downstream (slave-facing) port.
    """

    def __init__(self, *, addr_width, data_width, id_width=0, timeout=1024):
        if not isinstance(addr_width, int) or addr_width < 0:
            raise TypeError(f"Address width must be a non-negative integer, not {addr_width!r}")
        if not isinstance(data_width, int) or data_width < 8:
            raise ValueError(f"Data width must be an integer >= 8, not {data_width!r}")
        if data_width & (data_width - 1) != 0:
            raise ValueError(f"Data width must be a power of 2, not {data_width!r}")
        if not isinstance(id_width, int) or id_width < 0:
            raise TypeError(f"ID width must be a non-negative integer, not {id_width!r}")
        if not isinstance(timeout, int) or timeout < 1:
            raise ValueError(f"Timeout must be a positive integer, not {timeout!r}")

        self._addr_width = addr_width
        self._data_width = data_width
        self._id_width = id_width
        self._timeout = timeout

        super().__init__({
            "bus": In(AXI4Signature(addr_width=addr_width, data_width=data_width,
                                    id_width=id_width)),
            "sub": Out(AXI4Signature(addr_width=addr_width, data_width=data_width,
                                     id_width=id_width)),
        })

    @property
    def addr_width(self):
        return self._addr_width

    @property
    def data_width(self):
        return self._data_width

    @property
    def id_width(self):
        return self._id_width

    @property
    def timeout(self):
        return self._timeout

    def elaborate(self, platform):
        m = Module()

        bus = self.bus
        sub = self.sub

        # --- Write path state ---
        wr_counter = Signal(range(self._timeout + 1), name="wr_counter")
        wr_timed_out = Signal(name="wr_timed_out")
        # Saved ID from AW handshake for timeout response
        wr_saved_id = Signal(max(1, self._id_width), name="wr_saved_id")

        # --- Read path state ---
        rd_counter = Signal(range(self._timeout + 1), name="rd_counter")
        rd_timed_out = Signal(name="rd_timed_out")
        # Saved ID from AR handshake for timeout response
        rd_saved_id = Signal(max(1, self._id_width), name="rd_saved_id")

        # =====================================================================
        # Write path
        # =====================================================================

        # AW channel: pass-through when not timed out
        with m.If(~wr_timed_out):
            m.d.comb += [
                sub.awaddr.eq(bus.awaddr),
                sub.awprot.eq(bus.awprot),
                sub.awvalid.eq(bus.awvalid),
                bus.awready.eq(sub.awready),
                sub.awlen.eq(bus.awlen),
                sub.awsize.eq(bus.awsize),
                sub.awburst.eq(bus.awburst),
                sub.awlock.eq(bus.awlock),
                sub.awcache.eq(bus.awcache),
                sub.awqos.eq(bus.awqos),
                sub.awregion.eq(bus.awregion),
            ]
            if self._id_width > 0:
                m.d.comb += sub.awid.eq(bus.awid)
        with m.Else():
            m.d.comb += [
                sub.awvalid.eq(0),
                bus.awready.eq(0),
            ]

        # W channel: pass-through when not timed out
        with m.If(~wr_timed_out):
            m.d.comb += [
                sub.wdata.eq(bus.wdata),
                sub.wstrb.eq(bus.wstrb),
                sub.wvalid.eq(bus.wvalid),
                sub.wlast.eq(bus.wlast),
                bus.wready.eq(sub.wready),
            ]
        with m.Else():
            m.d.comb += [
                sub.wvalid.eq(0),
                bus.wready.eq(0),
            ]

        # B channel: pass-through or generate DECERR on timeout
        with m.If(wr_timed_out):
            m.d.comb += [
                bus.bresp.eq(AXIResp.DECERR),
                bus.bvalid.eq(1),
                sub.bready.eq(0),
            ]
            if self._id_width > 0:
                m.d.comb += bus.bid.eq(wr_saved_id)
        with m.Else():
            m.d.comb += [
                bus.bresp.eq(sub.bresp),
                bus.bvalid.eq(sub.bvalid),
                sub.bready.eq(bus.bready),
            ]
            if self._id_width > 0:
                m.d.comb += bus.bid.eq(sub.bid)

        # Write timeout FSM
        with m.FSM(name="wr_timeout"):
            with m.State("WR_IDLE"):
                m.d.sync += wr_timed_out.eq(0)
                # Start monitoring on AW handshake
                with m.If(bus.awvalid & bus.awready & ~wr_timed_out):
                    m.d.sync += wr_counter.eq(0)
                    if self._id_width > 0:
                        m.d.sync += wr_saved_id.eq(bus.awid)
                    m.next = "WR_MONITOR"

            with m.State("WR_MONITOR"):
                m.d.sync += wr_counter.eq(wr_counter + 1)

                # Normal completion: B handshake
                with m.If(bus.bvalid & bus.bready):
                    m.next = "WR_IDLE"

                # Timeout
                with m.If(wr_counter >= self._timeout - 1):
                    m.d.sync += wr_timed_out.eq(1)
                    m.next = "WR_TIMEOUT_RESP"

            with m.State("WR_TIMEOUT_RESP"):
                # Generate DECERR B response, wait for master to accept
                with m.If(bus.bready):
                    m.d.sync += wr_timed_out.eq(0)
                    m.next = "WR_IDLE"

        # =====================================================================
        # Read path
        # =====================================================================

        # AR channel: pass-through when not timed out
        with m.If(~rd_timed_out):
            m.d.comb += [
                sub.araddr.eq(bus.araddr),
                sub.arprot.eq(bus.arprot),
                sub.arvalid.eq(bus.arvalid),
                bus.arready.eq(sub.arready),
                sub.arlen.eq(bus.arlen),
                sub.arsize.eq(bus.arsize),
                sub.arburst.eq(bus.arburst),
                sub.arlock.eq(bus.arlock),
                sub.arcache.eq(bus.arcache),
                sub.arqos.eq(bus.arqos),
                sub.arregion.eq(bus.arregion),
            ]
            if self._id_width > 0:
                m.d.comb += sub.arid.eq(bus.arid)
        with m.Else():
            m.d.comb += [
                sub.arvalid.eq(0),
                bus.arready.eq(0),
            ]

        # R channel: pass-through or generate DECERR on timeout
        with m.If(rd_timed_out):
            m.d.comb += [
                bus.rdata.eq(0),
                bus.rresp.eq(AXIResp.DECERR),
                bus.rvalid.eq(1),
                bus.rlast.eq(1),  # Single-beat DECERR with RLAST
                sub.rready.eq(0),
            ]
            if self._id_width > 0:
                m.d.comb += bus.rid.eq(rd_saved_id)
        with m.Else():
            m.d.comb += [
                bus.rdata.eq(sub.rdata),
                bus.rresp.eq(sub.rresp),
                bus.rvalid.eq(sub.rvalid),
                bus.rlast.eq(sub.rlast),
                sub.rready.eq(bus.rready),
            ]
            if self._id_width > 0:
                m.d.comb += bus.rid.eq(sub.rid)

        # Read timeout FSM
        with m.FSM(name="rd_timeout"):
            with m.State("RD_IDLE"):
                m.d.sync += rd_timed_out.eq(0)
                # Start monitoring on AR handshake
                with m.If(bus.arvalid & bus.arready & ~rd_timed_out):
                    m.d.sync += rd_counter.eq(0)
                    if self._id_width > 0:
                        m.d.sync += rd_saved_id.eq(bus.arid)
                    m.next = "RD_MONITOR"

            with m.State("RD_MONITOR"):
                m.d.sync += rd_counter.eq(rd_counter + 1)

                # Normal completion: R handshake with RLAST
                with m.If(bus.rvalid & bus.rready & bus.rlast):
                    m.next = "RD_IDLE"

                # Timeout
                with m.If(rd_counter >= self._timeout - 1):
                    m.d.sync += rd_timed_out.eq(1)
                    m.next = "RD_TIMEOUT_RESP"

            with m.State("RD_TIMEOUT_RESP"):
                # Generate DECERR R response with RLAST, wait for master to accept
                with m.If(bus.rready):
                    m.d.sync += rd_timed_out.eq(0)
                    m.next = "RD_IDLE"

        return m
