"""AXI4-Lite to Wishbone Classic bridge."""

from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.utils import exact_log2

from amaranth_soc.wishbone.bus import Signature as WBSignature, Feature as WBFeature
from ..axi.bus import AXI4LiteSignature, AXIResp


__all__ = ["AXI4LiteToWishbone"]


class AXI4LiteToWishbone(wiring.Component):
    """AXI4-Lite to Wishbone bridge.

    Converts AXI4-Lite transactions into Wishbone Classic bus cycles.

    Parameters
    ----------
    addr_width : int
        Address width in bits (AXI byte address width).
    data_width : int
        Data width (32 or 64).
    granularity : int
        Wishbone granularity (default 8).

    Members
    -------
    axi_bus : ``In(AXI4LiteSignature(...))``
        AXI4-Lite bus interface (slave/target side).
    wb_bus : ``Out(WBSignature(...))``
        Wishbone bus interface (master/initiator side).
    """

    def __init__(self, *, addr_width, data_width=32, granularity=8):
        if not isinstance(addr_width, int) or addr_width < 0:
            raise TypeError(f"Address width must be a non-negative integer, not {addr_width!r}")
        if data_width not in (32, 64):
            raise ValueError(f"Data width must be 32 or 64, not {data_width!r}")
        if granularity not in (8, 16, 32, 64):
            raise ValueError(f"Granularity must be one of 8, 16, 32, 64, not {granularity!r}")
        if granularity > data_width:
            raise ValueError(f"Granularity {granularity} may not be greater than data width "
                             f"{data_width}")

        self._addr_width  = addr_width
        self._data_width  = data_width
        self._granularity = granularity

        # Wishbone word address width
        addr_shift = exact_log2(data_width // granularity)
        wb_addr_width = max(0, addr_width - addr_shift)

        super().__init__({
            "axi_bus": In(AXI4LiteSignature(addr_width=addr_width,
                                            data_width=data_width)),
            "wb_bus":  Out(WBSignature(addr_width=wb_addr_width, data_width=data_width,
                                       granularity=granularity,
                                       features={WBFeature.ERR})),
        })

    @property
    def addr_width(self):
        return self._addr_width

    @property
    def data_width(self):
        return self._data_width

    @property
    def granularity(self):
        return self._granularity

    def elaborate(self, platform):
        m = Module()

        axi = self.axi_bus
        wb  = self.wb_bus

        addr_shift = exact_log2(self._data_width // self._granularity)

        # Latched signals
        wr_addr  = Signal(self._addr_width, name="wr_addr")
        wr_data  = Signal(self._data_width, name="wr_data")
        wr_strb  = Signal(self._data_width // 8, name="wr_strb")
        rd_addr  = Signal(self._addr_width, name="rd_addr")
        rd_data  = Signal(self._data_width, name="rd_data")
        wr_err   = Signal(name="wr_err")
        rd_err   = Signal(name="rd_err")

        # Default: no AXI ready/valid signals
        m.d.comb += [
            axi.awready.eq(0),
            axi.wready.eq(0),
            axi.bvalid.eq(0),
            axi.bresp.eq(AXIResp.OKAY),
            axi.arready.eq(0),
            axi.rvalid.eq(0),
            axi.rdata.eq(0),
            axi.rresp.eq(AXIResp.OKAY),
        ]

        # Default: Wishbone idle
        m.d.comb += [
            wb.cyc.eq(0),
            wb.stb.eq(0),
            wb.we.eq(0),
            wb.adr.eq(0),
            wb.dat_w.eq(0),
            wb.sel.eq(0),
        ]

        with m.FSM(name="fsm"):
            with m.State("IDLE"):
                # Write takes priority over read
                with m.If(axi.awvalid):
                    # Accept AW
                    m.d.comb += axi.awready.eq(1)
                    m.d.sync += wr_addr.eq(axi.awaddr)
                    # Check if W is also valid (can accept both simultaneously)
                    with m.If(axi.wvalid):
                        m.d.comb += axi.wready.eq(1)
                        m.d.sync += [
                            wr_data.eq(axi.wdata),
                            wr_strb.eq(axi.wstrb),
                        ]
                        m.next = "WR_CYCLE"
                    with m.Else():
                        m.next = "WR_DATA"
                with m.Elif(axi.arvalid):
                    # Accept AR
                    m.d.comb += axi.arready.eq(1)
                    m.d.sync += rd_addr.eq(axi.araddr)
                    m.next = "RD_CYCLE"

            with m.State("WR_DATA"):
                # Wait for W channel
                with m.If(axi.wvalid):
                    m.d.comb += axi.wready.eq(1)
                    m.d.sync += [
                        wr_data.eq(axi.wdata),
                        wr_strb.eq(axi.wstrb),
                    ]
                    m.next = "WR_CYCLE"

            with m.State("WR_CYCLE"):
                # Drive Wishbone write cycle
                m.d.comb += [
                    wb.cyc.eq(1),
                    wb.stb.eq(1),
                    wb.we.eq(1),
                    wb.adr.eq(wr_addr >> addr_shift),
                    wb.dat_w.eq(wr_data),
                    wb.sel.eq(wr_strb),
                ]
                with m.If(wb.ack | wb.err):
                    m.d.sync += wr_err.eq(wb.err)
                    m.next = "WR_RESP"

            with m.State("WR_RESP"):
                # Send B channel response
                m.d.comb += [
                    axi.bvalid.eq(1),
                    axi.bresp.eq(Mux(wr_err, AXIResp.SLVERR, AXIResp.OKAY)),
                ]
                with m.If(axi.bready):
                    m.next = "IDLE"

            with m.State("RD_CYCLE"):
                # Drive Wishbone read cycle
                m.d.comb += [
                    wb.cyc.eq(1),
                    wb.stb.eq(1),
                    wb.we.eq(0),
                    wb.adr.eq(rd_addr >> addr_shift),
                    wb.sel.eq((1 << (self._data_width // self._granularity)) - 1),
                ]
                with m.If(wb.ack | wb.err):
                    m.d.sync += [
                        rd_data.eq(wb.dat_r),
                        rd_err.eq(wb.err),
                    ]
                    m.next = "RD_RESP"

            with m.State("RD_RESP"):
                # Send R channel response
                m.d.comb += [
                    axi.rvalid.eq(1),
                    axi.rdata.eq(rd_data),
                    axi.rresp.eq(Mux(rd_err, AXIResp.SLVERR, AXIResp.OKAY)),
                ]
                with m.If(axi.rready):
                    m.next = "IDLE"

        return m
