"""Wishbone Classic to AXI4-Lite bridge."""

from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.utils import exact_log2

from amaranth_soc.wishbone.bus import Signature as WBSignature, Feature as WBFeature
from ..axi.bus import AXI4LiteSignature, AXIResp


__all__ = ["WishboneToAXI4Lite"]


class WishboneToAXI4Lite(wiring.Component):
    """Wishbone to AXI4-Lite bridge.

    Converts Wishbone Classic bus cycles into AXI4-Lite transactions.

    Parameters
    ----------
    addr_width : int
        Address width in bits (Wishbone word address width).
    data_width : int
        Data width (32 or 64).
    granularity : int
        Wishbone granularity (default 8).

    Members
    -------
    wb_bus : ``In(WBSignature(...))``
        Wishbone bus interface (slave/target side).
    axi_bus : ``Out(AXI4LiteSignature(...))``
        AXI4-Lite bus interface (master/initiator side).
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

        # Compute the AXI byte address width.
        # Wishbone word address + log2(data_width // granularity) gives byte address bits.
        addr_shift = exact_log2(data_width // granularity)
        axi_addr_width = addr_width + addr_shift

        super().__init__({
            "wb_bus":  In(WBSignature(addr_width=addr_width, data_width=data_width,
                                      granularity=granularity,
                                      features={WBFeature.ERR})),
            "axi_bus": Out(AXI4LiteSignature(addr_width=axi_addr_width,
                                             data_width=data_width)),
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

        wb  = self.wb_bus
        axi = self.axi_bus

        addr_shift = exact_log2(self._data_width // self._granularity)

        # Latched write data/strobe for when AW is accepted before W or vice versa
        wdata_latched = Signal(self._data_width, name="wdata_latched")
        wstrb_latched = Signal(self._data_width // 8, name="wstrb_latched")
        awaddr_latched = Signal(self._addr_width + addr_shift, name="awaddr_latched")

        # Default: no Wishbone ack/err
        m.d.comb += [
            wb.ack.eq(0),
            wb.err.eq(0),
            wb.dat_r.eq(0),
        ]

        # Default: no AXI valid signals
        m.d.comb += [
            axi.awvalid.eq(0),
            axi.wvalid.eq(0),
            axi.bready.eq(0),
            axi.arvalid.eq(0),
            axi.rready.eq(0),
        ]

        with m.FSM(name="fsm"):
            with m.State("IDLE"):
                with m.If(wb.cyc & wb.stb):
                    with m.If(wb.we):
                        # Write: latch data and go to WRITE_ADDR
                        m.d.sync += [
                            wdata_latched.eq(wb.dat_w),
                            wstrb_latched.eq(wb.sel),
                            awaddr_latched.eq(wb.adr << addr_shift),
                        ]
                        m.next = "WRITE_ADDR"
                    with m.Else():
                        # Read: go to READ_ADDR
                        m.next = "READ_ADDR"

            with m.State("WRITE_ADDR"):
                # Drive both AW and W channels simultaneously
                m.d.comb += [
                    axi.awaddr.eq(awaddr_latched),
                    axi.awvalid.eq(1),
                    axi.wdata.eq(wdata_latched),
                    axi.wstrb.eq(wstrb_latched),
                    axi.wvalid.eq(1),
                ]
                with m.If(axi.awready & axi.wready):
                    # Both accepted
                    m.next = "WRITE_RESP"
                with m.Elif(axi.awready & ~axi.wready):
                    # AW accepted, W pending
                    m.next = "WRITE_DATA"
                with m.Elif(~axi.awready & axi.wready):
                    # W accepted, AW pending
                    m.next = "WRITE_ADDR_PENDING"

            with m.State("WRITE_DATA"):
                # Only W channel pending (AW already accepted)
                m.d.comb += [
                    axi.wdata.eq(wdata_latched),
                    axi.wstrb.eq(wstrb_latched),
                    axi.wvalid.eq(1),
                ]
                with m.If(axi.wready):
                    m.next = "WRITE_RESP"

            with m.State("WRITE_ADDR_PENDING"):
                # Only AW channel pending (W already accepted)
                m.d.comb += [
                    axi.awaddr.eq(awaddr_latched),
                    axi.awvalid.eq(1),
                ]
                with m.If(axi.awready):
                    m.next = "WRITE_RESP"

            with m.State("WRITE_RESP"):
                # Wait for B channel response
                m.d.comb += axi.bready.eq(1)
                with m.If(axi.bvalid):
                    m.d.comb += [
                        wb.ack.eq(1),
                        wb.err.eq(axi.bresp != AXIResp.OKAY),
                    ]
                    m.next = "IDLE"

            with m.State("READ_ADDR"):
                # Drive AR channel
                m.d.comb += [
                    axi.araddr.eq(wb.adr << addr_shift),
                    axi.arvalid.eq(1),
                ]
                with m.If(axi.arready):
                    m.next = "READ_DATA"

            with m.State("READ_DATA"):
                # Wait for R channel response
                m.d.comb += axi.rready.eq(1)
                with m.If(axi.rvalid):
                    m.d.comb += [
                        wb.ack.eq(1),
                        wb.dat_r.eq(axi.rdata),
                        wb.err.eq(axi.rresp != AXIResp.OKAY),
                    ]
                    m.next = "IDLE"

        return m
