"""AXI4 (full) to AXI4-Lite adapter with burst decomposition."""

from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.utils import exact_log2

from .bus import AXI4Signature, AXI4LiteSignature, AXIResp, AXIBurst
from .burst import AXIBurst2Beat


__all__ = ["AXI4ToAXI4Lite"]


class AXI4ToAXI4Lite(wiring.Component):
    """AXI4 to AXI4-Lite adapter.

    Decomposes AXI4 burst transactions into individual AXI4-Lite
    transactions. Strips ID, cache, QoS, region, and user signals.

    Parameters
    ----------
    addr_width : int
        Address width.
    data_width : int, power of 2, >= 32
        Data width. Must be a power of 2 and at least 32.
    id_width : int
        AXI4 ID width (for the upstream port).

    Members
    -------
    axi4_bus : ``In(AXI4Signature(...))``
        AXI4 (full) upstream slave port.
    axi4lite_bus : ``Out(AXI4LiteSignature(...))``
        AXI4-Lite downstream master port.
    """

    def __init__(self, *, addr_width, data_width=32, id_width=4):
        if not isinstance(addr_width, int) or addr_width < 1:
            raise TypeError(f"Address width must be a positive integer, not {addr_width!r}")
        if not isinstance(data_width, int) or data_width < 32:
            raise ValueError(f"Data width must be a positive integer >= 32, not {data_width!r}")
        if data_width & (data_width - 1) != 0:
            raise ValueError(f"Data width must be a power of 2, not {data_width!r}")
        if not isinstance(id_width, int) or id_width < 0:
            raise TypeError(f"ID width must be a non-negative integer, not {id_width!r}")

        self._addr_width = addr_width
        self._data_width = data_width
        self._id_width   = id_width

        super().__init__({
            "axi4_bus":     In(AXI4Signature(addr_width=addr_width, data_width=data_width,
                                             id_width=id_width)),
            "axi4lite_bus": Out(AXI4LiteSignature(addr_width=addr_width,
                                                   data_width=data_width)),
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

    def elaborate(self, platform):
        m = Module()

        axi4 = self.axi4_bus
        lite  = self.axi4lite_bus

        # --- Burst-to-beat converters ---
        m.submodules.wr_b2b = wr_b2b = AXIBurst2Beat(addr_width=self._addr_width,
                                                       data_width=self._data_width)
        m.submodules.rd_b2b = rd_b2b = AXIBurst2Beat(addr_width=self._addr_width,
                                                       data_width=self._data_width)

        # --- Write path ---
        wr_id       = Signal(max(1, self._id_width), name="wr_id")
        wr_resp     = Signal(2, name="wr_resp")  # accumulated worst response
        wr_beat_cnt = Signal(8, name="wr_beat_cnt")
        wr_len      = Signal(8, name="wr_len")

        # Default: no handshake signals
        m.d.comb += [
            axi4.awready.eq(0),
            axi4.wready.eq(0),
            axi4.bvalid.eq(0),
            axi4.bresp.eq(AXIResp.OKAY),
        ]
        if self._id_width > 0:
            m.d.comb += axi4.bid.eq(wr_id)

        m.d.comb += [
            lite.awvalid.eq(0),
            lite.awaddr.eq(0),
            lite.wvalid.eq(0),
            lite.wdata.eq(0),
            lite.wstrb.eq(0),
            lite.bready.eq(0),
        ]

        # Connect burst2beat inputs (active during write)
        m.d.comb += [
            wr_b2b.first.eq(0),
            wr_b2b.next.eq(0),
        ]

        with m.FSM(name="wr_fsm"):
            with m.State("WR_IDLE"):
                # Wait for AW valid
                with m.If(axi4.awvalid):
                    m.d.comb += axi4.awready.eq(1)
                    # Latch burst parameters
                    if self._id_width > 0:
                        m.d.sync += wr_id.eq(axi4.awid)
                    m.d.sync += [
                        wr_len.eq(axi4.awlen),
                        wr_resp.eq(AXIResp.OKAY),
                        wr_beat_cnt.eq(0),
                    ]
                    # Load burst2beat
                    m.d.comb += [
                        wr_b2b.addr.eq(axi4.awaddr),
                        wr_b2b.len.eq(axi4.awlen),
                        wr_b2b.size.eq(axi4.awsize),
                        wr_b2b.burst.eq(axi4.awburst),
                        wr_b2b.first.eq(1),
                    ]
                    m.next = "WR_BEAT"

            with m.State("WR_BEAT"):
                # Wait for W data from upstream, then forward as AXI4-Lite write
                # Drive AW + W to downstream simultaneously
                with m.If(axi4.wvalid):
                    m.d.comb += [
                        lite.awaddr.eq(wr_b2b.next_addr),
                        lite.awvalid.eq(1),
                        lite.wdata.eq(axi4.wdata),
                        lite.wstrb.eq(axi4.wstrb),
                        lite.wvalid.eq(1),
                    ]
                    # When both AW and W are accepted downstream
                    with m.If(lite.awready & lite.wready):
                        m.d.comb += axi4.wready.eq(1)  # consume upstream W
                        m.next = "WR_BEAT_RESP"

            with m.State("WR_BEAT_RESP"):
                # Wait for B response from downstream for this beat
                m.d.comb += lite.bready.eq(1)
                with m.If(lite.bvalid):
                    # Accumulate worst response (higher value = worse)
                    with m.If(lite.bresp > wr_resp):
                        m.d.sync += wr_resp.eq(lite.bresp)
                    # Check if this was the last beat
                    with m.If(wr_beat_cnt == wr_len):
                        m.next = "WR_RESP"
                    with m.Else():
                        # Advance to next beat
                        m.d.comb += wr_b2b.next.eq(1)
                        m.d.sync += wr_beat_cnt.eq(wr_beat_cnt + 1)
                        m.next = "WR_BEAT"

            with m.State("WR_RESP"):
                # Send single B response back to upstream
                m.d.comb += [
                    axi4.bvalid.eq(1),
                    axi4.bresp.eq(wr_resp),
                ]
                with m.If(axi4.bready):
                    m.next = "WR_IDLE"

        # --- Read path ---
        rd_id       = Signal(max(1, self._id_width), name="rd_id")
        rd_beat_cnt = Signal(8, name="rd_beat_cnt")
        rd_len      = Signal(8, name="rd_len")
        rd_data     = Signal(self._data_width, name="rd_data")
        rd_resp     = Signal(2, name="rd_resp")

        m.d.comb += [
            axi4.arready.eq(0),
            axi4.rvalid.eq(0),
            axi4.rdata.eq(0),
            axi4.rresp.eq(AXIResp.OKAY),
            axi4.rlast.eq(0),
        ]
        if self._id_width > 0:
            m.d.comb += axi4.rid.eq(rd_id)

        m.d.comb += [
            lite.arvalid.eq(0),
            lite.araddr.eq(0),
            lite.rready.eq(0),
        ]

        # Connect burst2beat inputs (active during read)
        m.d.comb += [
            rd_b2b.first.eq(0),
            rd_b2b.next.eq(0),
        ]

        with m.FSM(name="rd_fsm"):
            with m.State("RD_IDLE"):
                # Wait for AR valid
                with m.If(axi4.arvalid):
                    m.d.comb += axi4.arready.eq(1)
                    # Latch burst parameters
                    if self._id_width > 0:
                        m.d.sync += rd_id.eq(axi4.arid)
                    m.d.sync += [
                        rd_len.eq(axi4.arlen),
                        rd_beat_cnt.eq(0),
                    ]
                    # Load burst2beat
                    m.d.comb += [
                        rd_b2b.addr.eq(axi4.araddr),
                        rd_b2b.len.eq(axi4.arlen),
                        rd_b2b.size.eq(axi4.arsize),
                        rd_b2b.burst.eq(axi4.arburst),
                        rd_b2b.first.eq(1),
                    ]
                    m.next = "RD_BEAT_ADDR"

            with m.State("RD_BEAT_ADDR"):
                # Issue AXI4-Lite read for current beat
                m.d.comb += [
                    lite.araddr.eq(rd_b2b.next_addr),
                    lite.arvalid.eq(1),
                ]
                with m.If(lite.arready):
                    m.next = "RD_BEAT_DATA"

            with m.State("RD_BEAT_DATA"):
                # Wait for R response from downstream
                m.d.comb += lite.rready.eq(1)
                with m.If(lite.rvalid):
                    # Latch data and response
                    m.d.sync += [
                        rd_data.eq(lite.rdata),
                        rd_resp.eq(lite.rresp),
                    ]
                    m.next = "RD_FORWARD"

            with m.State("RD_FORWARD"):
                # Forward R data to upstream with correct rlast
                m.d.comb += [
                    axi4.rvalid.eq(1),
                    axi4.rdata.eq(rd_data),
                    axi4.rresp.eq(rd_resp),
                    axi4.rlast.eq(rd_beat_cnt == rd_len),
                ]
                with m.If(axi4.rready):
                    with m.If(rd_beat_cnt == rd_len):
                        # Last beat done
                        m.next = "RD_IDLE"
                    with m.Else():
                        # Advance to next beat
                        m.d.comb += rd_b2b.next.eq(1)
                        m.d.sync += rd_beat_cnt.eq(rd_beat_cnt + 1)
                        m.next = "RD_BEAT_ADDR"

        return m
