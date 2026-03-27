"""Tests for AXI4LiteDecoder and AXI4Decoder."""
import unittest
from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out, connect
from amaranth.lib.memory import MemoryData, Memory
from amaranth.back.rtlil import convert
from amaranth.sim import Simulator
from amaranth.utils import exact_log2

from amaranth_soc.axi.decoder import AXI4LiteDecoder, AXI4Decoder
from amaranth_soc.axi.bus import (
    AXI4LiteInterface, AXI4LiteSignature, AXI4Signature, AXI4Interface,
    AXIResp, AXIBurst,
)
from amaranth_soc.memory import MemoryMap


# ---------------------------------------------------------------------------
# AXI4-Lite Decoder tests (existing)
# ---------------------------------------------------------------------------

class TestAXI4LiteDecoder(unittest.TestCase):
    def test_create(self):
        dec = AXI4LiteDecoder(addr_width=16, data_width=32)
        self.assertIsNotNone(dec.memory_map)
        self.assertEqual(dec.memory_map.addr_width, 16)
        self.assertEqual(dec.memory_map.data_width, 8)

    def test_create_invalid_addr_width(self):
        with self.assertRaises(TypeError):
            AXI4LiteDecoder(addr_width=-1, data_width=32)

    def test_create_invalid_data_width(self):
        with self.assertRaises(ValueError):
            AXI4LiteDecoder(addr_width=16, data_width=16)

    def test_add_subordinate(self):
        dec = AXI4LiteDecoder(addr_width=16, data_width=32)
        sub = AXI4LiteInterface(addr_width=14, data_width=32)
        sub.memory_map = MemoryMap(addr_width=14, data_width=8)
        dec.add(sub, name='sub1', addr=0x0000)

    def test_add_subordinate_wrong_data_width(self):
        dec = AXI4LiteDecoder(addr_width=16, data_width=32)
        sub = AXI4LiteInterface(addr_width=14, data_width=64)
        sub.memory_map = MemoryMap(addr_width=14, data_width=8)
        with self.assertRaises(ValueError):
            dec.add(sub, name='sub1', addr=0x0000)

    def test_add_subordinate_wrong_type(self):
        dec = AXI4LiteDecoder(addr_width=16, data_width=32)
        with self.assertRaises(TypeError):
            dec.add("not a bus", name='sub1', addr=0x0000)

    def test_elaborate_single_sub(self):
        dec = AXI4LiteDecoder(addr_width=16, data_width=32)
        sub1 = AXI4LiteInterface(addr_width=14, data_width=32)
        sub1.memory_map = MemoryMap(addr_width=14, data_width=8)
        dec.add(sub1, name='sub1', addr=0x0000)
        # Should elaborate without error
        rtlil = convert(dec)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_two_subs(self):
        dec = AXI4LiteDecoder(addr_width=16, data_width=32)
        sub1 = AXI4LiteInterface(addr_width=14, data_width=32)
        sub1.memory_map = MemoryMap(addr_width=14, data_width=8)
        dec.add(sub1, name='sub1', addr=0x0000)
        sub2 = AXI4LiteInterface(addr_width=14, data_width=32)
        sub2.memory_map = MemoryMap(addr_width=14, data_width=8)
        dec.add(sub2, name='sub2', addr=0x4000)
        # Should elaborate without error
        rtlil = convert(dec)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_no_subs(self):
        """Decoder with no subordinates should still elaborate (DECERR path)."""
        dec = AXI4LiteDecoder(addr_width=16, data_width=32)
        rtlil = convert(dec)
        self.assertGreater(len(rtlil), 0)

    def test_align_to(self):
        dec = AXI4LiteDecoder(addr_width=16, data_width=32)
        dec.align_to(12)  # Align to 4096 bytes

    def test_pipelined_create(self):
        """Constructor with pipelined=True."""
        dec = AXI4LiteDecoder(addr_width=16, data_width=32, pipelined=True)
        self.assertTrue(dec.pipelined)
        self.assertIsNotNone(dec.memory_map)
        self.assertEqual(dec.memory_map.addr_width, 16)

    def test_pipelined_default_false(self):
        """Default is pipelined=False."""
        dec = AXI4LiteDecoder(addr_width=16, data_width=32)
        self.assertFalse(dec.pipelined)

    def test_pipelined_elaborate(self):
        """Elaborate with pipelined=True and subordinates."""
        dec = AXI4LiteDecoder(addr_width=16, data_width=32, pipelined=True)
        sub1 = AXI4LiteInterface(addr_width=14, data_width=32)
        sub1.memory_map = MemoryMap(addr_width=14, data_width=8)
        dec.add(sub1, name='sub1', addr=0x0000)
        sub2 = AXI4LiteInterface(addr_width=14, data_width=32)
        sub2.memory_map = MemoryMap(addr_width=14, data_width=8)
        dec.add(sub2, name='sub2', addr=0x4000)
        rtlil = convert(dec)
        self.assertGreater(len(rtlil), 0)

    def test_pipelined_sim_write_read(self):
        """Simulation: pipelined decoder with SRAM — write a value, read it back."""
        dut = _PipelinedLiteDecoderWithSRAM(addr_width=16, data_width=32, sram_depth=256)

        async def testbench(ctx):
            bus = dut.bus

            # Write 0xDEADBEEF to address 0x0000
            bresp = await _axi4lite_write(ctx, bus, addr=0x0000, data=0xDEADBEEF)
            assert bresp == AXIResp.OKAY, f"Write: expected OKAY, got {AXIResp(bresp)}"

            # Read back from address 0x0000
            rdata, rresp = await _axi4lite_read(ctx, bus, addr=0x0000)
            assert rresp == AXIResp.OKAY, f"Read: expected OKAY, got {AXIResp(rresp)}"
            assert rdata == 0xDEADBEEF, f"Data mismatch: expected 0xDEADBEEF, got {rdata:#010x}"

            # Write 0xCAFEBABE to address 0x0004
            bresp = await _axi4lite_write(ctx, bus, addr=0x0004, data=0xCAFEBABE)
            assert bresp == AXIResp.OKAY, f"Write: expected OKAY, got {AXIResp(bresp)}"

            # Read back from address 0x0004
            rdata, rresp = await _axi4lite_read(ctx, bus, addr=0x0004)
            assert rresp == AXIResp.OKAY, f"Read: expected OKAY, got {AXIResp(rresp)}"
            assert rdata == 0xCAFEBABE, f"Data mismatch: expected 0xCAFEBABE, got {rdata:#010x}"

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("test_pipelined_lite_write_read.vcd"):
            sim.run()

    def test_pipelined_sim_back_to_back_reads(self):
        """Simulation: two back-to-back reads complete correctly in pipelined mode."""
        dut = _PipelinedLiteDecoderWithSRAM(addr_width=16, data_width=32, sram_depth=256)

        async def testbench(ctx):
            bus = dut.bus

            # Pre-fill two addresses
            bresp = await _axi4lite_write(ctx, bus, addr=0x0000, data=0x11111111)
            assert bresp == AXIResp.OKAY
            bresp = await _axi4lite_write(ctx, bus, addr=0x0004, data=0x22222222)
            assert bresp == AXIResp.OKAY

            # Back-to-back reads: issue first read
            rdata1, rresp1 = await _axi4lite_read(ctx, bus, addr=0x0000)
            assert rresp1 == AXIResp.OKAY, f"Read 1: expected OKAY, got {AXIResp(rresp1)}"
            assert rdata1 == 0x11111111, f"Read 1: expected 0x11111111, got {rdata1:#010x}"

            # Issue second read immediately after first completes
            rdata2, rresp2 = await _axi4lite_read(ctx, bus, addr=0x0004)
            assert rresp2 == AXIResp.OKAY, f"Read 2: expected OKAY, got {AXIResp(rresp2)}"
            assert rdata2 == 0x22222222, f"Read 2: expected 0x22222222, got {rdata2:#010x}"

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("test_pipelined_lite_back_to_back_reads.vcd"):
            sim.run()


# ---------------------------------------------------------------------------
# Simple AXI4-Lite SRAM subordinate for testing (handles AW/W separately)
# ---------------------------------------------------------------------------

class _AXI4LiteSRAMSub(wiring.Component):
    """Simple AXI4-Lite SRAM that handles AW and W channels independently.

    Unlike AXI4LiteSRAM which requires AW+W simultaneously, this subordinate
    accepts AW and W in any order, matching the decoder's serialized forwarding.
    """
    def __init__(self, *, addr_width, data_width, depth=256):
        self._depth = depth
        self._data_width = data_width
        self._addr_width = addr_width
        sig = AXI4LiteSignature(addr_width=addr_width, data_width=data_width)
        super().__init__({"bus": Out(sig)})

    def elaborate(self, platform):
        m = Module()

        bus = self.bus
        data_width = self._data_width
        bytes_per_word = data_width // 8
        word_addr_shift = exact_log2(bytes_per_word) if bytes_per_word > 1 else 0

        mem = Memory(MemoryData(depth=self._depth, shape=unsigned(data_width), init=[]))
        m.submodules.mem = mem
        rd_port = mem.read_port()
        wr_port = mem.write_port(granularity=8)

        # Latched write address
        wr_addr = Signal(self._addr_width, name="wr_addr")

        # --- Write FSM ---
        with m.FSM(name="wr_fsm"):
            with m.State("WR_IDLE"):
                m.d.comb += bus.awready.eq(1)
                with m.If(bus.awvalid):
                    m.d.sync += wr_addr.eq(bus.awaddr)
                    m.next = "WR_DATA"

            with m.State("WR_DATA"):
                m.d.comb += bus.wready.eq(1)
                m.d.comb += [
                    wr_port.addr.eq(wr_addr[word_addr_shift:]),
                    wr_port.data.eq(bus.wdata),
                ]
                with m.If(bus.wvalid):
                    m.d.comb += wr_port.en.eq(bus.wstrb)
                    m.next = "WR_RESP"

            with m.State("WR_RESP"):
                m.d.comb += [
                    bus.bvalid.eq(1),
                    bus.bresp.eq(AXIResp.OKAY),
                ]
                with m.If(bus.bready):
                    m.next = "WR_IDLE"

        # --- Read FSM ---
        with m.FSM(name="rd_fsm"):
            with m.State("RD_IDLE"):
                m.d.comb += bus.arready.eq(1)
                with m.If(bus.arvalid):
                    m.d.comb += [
                        rd_port.addr.eq(bus.araddr[word_addr_shift:]),
                        rd_port.en.eq(1),
                    ]
                    m.next = "RD_DATA"

            with m.State("RD_DATA"):
                m.d.comb += [
                    bus.rvalid.eq(1),
                    bus.rdata.eq(rd_port.data),
                    bus.rresp.eq(AXIResp.OKAY),
                ]
                with m.If(bus.rready):
                    m.next = "RD_IDLE"

        return m


# ---------------------------------------------------------------------------
# AXI4-Lite pipelined decoder + SRAM wrapper for simulation
# ---------------------------------------------------------------------------

class _PipelinedLiteDecoderWithSRAM(wiring.Component):
    """Wraps a pipelined AXI4LiteDecoder with one _AXI4LiteSRAMSub subordinate."""
    def __init__(self, *, addr_width, data_width, sram_depth=256):
        self._addr_width = addr_width
        self._data_width = data_width
        self._sram_depth = sram_depth
        sig = AXI4LiteSignature(addr_width=addr_width, data_width=data_width)
        super().__init__({"bus": In(sig)})

    def elaborate(self, platform):
        m = Module()

        dec = AXI4LiteDecoder(addr_width=self._addr_width, data_width=self._data_width,
                              pipelined=True)

        # Create SRAM subordinate with separate AW/W handling
        sub_addr_width = self._addr_width - 1  # half the address space
        sram = _AXI4LiteSRAMSub(addr_width=sub_addr_width, data_width=self._data_width,
                                 depth=self._sram_depth)

        sram.bus.memory_map = MemoryMap(addr_width=sub_addr_width, data_width=8)
        dec.add(sram.bus, name="sram", addr=0x0000)

        m.submodules.dec = dec
        m.submodules.sram = sram

        # Wire our bus to the decoder's bus
        m.d.comb += [
            # AW channel
            dec.bus.awaddr.eq(self.bus.awaddr),
            dec.bus.awprot.eq(self.bus.awprot),
            dec.bus.awvalid.eq(self.bus.awvalid),
            self.bus.awready.eq(dec.bus.awready),
            # W channel
            dec.bus.wdata.eq(self.bus.wdata),
            dec.bus.wstrb.eq(self.bus.wstrb),
            dec.bus.wvalid.eq(self.bus.wvalid),
            self.bus.wready.eq(dec.bus.wready),
            # B channel
            self.bus.bresp.eq(dec.bus.bresp),
            self.bus.bvalid.eq(dec.bus.bvalid),
            dec.bus.bready.eq(self.bus.bready),
            # AR channel
            dec.bus.araddr.eq(self.bus.araddr),
            dec.bus.arprot.eq(self.bus.arprot),
            dec.bus.arvalid.eq(self.bus.arvalid),
            self.bus.arready.eq(dec.bus.arready),
            # R channel
            self.bus.rdata.eq(dec.bus.rdata),
            self.bus.rresp.eq(dec.bus.rresp),
            self.bus.rvalid.eq(dec.bus.rvalid),
            dec.bus.rready.eq(self.bus.rready),
        ]

        return m


# ---------------------------------------------------------------------------
# AXI4-Lite simulation helpers
# ---------------------------------------------------------------------------

async def _axi4lite_write(ctx, bus, addr, data, *, wstrb=0xF):
    """Perform an AXI4-Lite write transaction.

    Drives AW and W channels simultaneously, keeps them asserted until the
    B response is received.

    Parameters
    ----------
    ctx : SimulatorContext
    bus : AXI4-Lite bus interface
    addr : int
        Write address.
    data : int
        Write data.
    wstrb : int
        Write strobe (default 0xF for all bytes).

    Returns
    -------
    int
        bresp value.
    """
    # Drive AW, W, and bready simultaneously
    ctx.set(bus.awaddr, addr)
    ctx.set(bus.awprot, 0)
    ctx.set(bus.awvalid, 1)
    ctx.set(bus.wdata, data)
    ctx.set(bus.wstrb, wstrb)
    ctx.set(bus.wvalid, 1)
    ctx.set(bus.bready, 1)

    # Wait for B response (AW and W handshakes happen along the way)
    bresp = 0
    for _ in range(100):
        await ctx.tick()
        if ctx.get(bus.bvalid):
            bresp = ctx.get(bus.bresp)
            break

    # Clean up
    ctx.set(bus.awvalid, 0)
    ctx.set(bus.wvalid, 0)
    ctx.set(bus.bready, 0)
    await ctx.tick()

    return bresp


async def _axi4lite_read(ctx, bus, addr):
    """Perform an AXI4-Lite read transaction.

    Drives AR channel and rready, waits for R response.

    Parameters
    ----------
    ctx : SimulatorContext
    bus : AXI4-Lite bus interface
    addr : int
        Read address.

    Returns
    -------
    tuple of (int, int)
        (rdata, rresp)
    """
    # Drive AR and rready
    ctx.set(bus.araddr, addr)
    ctx.set(bus.arprot, 0)
    ctx.set(bus.arvalid, 1)
    ctx.set(bus.rready, 1)

    # Wait for R response
    rdata = 0
    rresp = 0
    for _ in range(100):
        await ctx.tick()
        if ctx.get(bus.rvalid):
            rdata = ctx.get(bus.rdata)
            rresp = ctx.get(bus.rresp)
            break

    # Clean up
    ctx.set(bus.arvalid, 0)
    ctx.set(bus.rready, 0)
    await ctx.tick()

    return rdata, rresp


# ---------------------------------------------------------------------------
# Simple AXI4 SRAM subordinate for testing
# ---------------------------------------------------------------------------

class _AXI4SRAMSub(wiring.Component):
    """Simple AXI4 SRAM subordinate for testing.

    Supports single-beat and burst transactions with byte-lane strobes.
    """
    def __init__(self, *, addr_width, data_width, id_width=0, depth=256):
        self._depth = depth
        self._data_width = data_width
        self._id_width = id_width
        self._addr_width = addr_width
        sig = AXI4Signature(addr_width=addr_width, data_width=data_width, id_width=id_width)
        super().__init__({"bus": Out(sig)})

    def elaborate(self, platform):
        m = Module()

        bus = self.bus
        data_width = self._data_width
        id_width = self._id_width
        has_id = id_width > 0
        bytes_per_word = data_width // 8
        word_addr_shift = exact_log2(bytes_per_word) if bytes_per_word > 1 else 0

        # Simple memory array
        mem = Memory(MemoryData(depth=self._depth, shape=unsigned(data_width), init=[]))
        m.submodules.mem = mem
        rd_port = mem.read_port()
        wr_port = mem.write_port(granularity=8)

        # Latched signals for write path
        wr_addr = Signal(self._addr_width, name="wr_addr")
        wr_len = Signal(8, name="wr_len")
        wr_beat_cnt = Signal(8, name="wr_beat_cnt")
        if has_id:
            wr_id = Signal(id_width, name="wr_id")

        # Latched signals for read path
        rd_addr = Signal(self._addr_width, name="rd_addr")
        rd_len = Signal(8, name="rd_len")
        rd_beat_cnt = Signal(8, name="rd_beat_cnt")
        if has_id:
            rd_id = Signal(id_width, name="rd_id")

        # --- Write FSM ---
        with m.FSM(name="wr_fsm"):
            with m.State("WR_IDLE"):
                m.d.comb += bus.awready.eq(1)
                with m.If(bus.awvalid):
                    m.d.sync += [
                        wr_addr.eq(bus.awaddr),
                        wr_len.eq(bus.awlen),
                        wr_beat_cnt.eq(0),
                    ]
                    if has_id:
                        m.d.sync += wr_id.eq(bus.awid)
                    m.next = "WR_DATA"

            with m.State("WR_DATA"):
                m.d.comb += bus.wready.eq(1)
                # Compute word address for current beat
                cur_wr_word_addr = Signal(self._addr_width, name="cur_wr_word_addr")
                if word_addr_shift > 0:
                    m.d.comb += cur_wr_word_addr.eq(
                        (wr_addr >> word_addr_shift) + wr_beat_cnt
                    )
                else:
                    m.d.comb += cur_wr_word_addr.eq(wr_addr + wr_beat_cnt)

                m.d.comb += [
                    wr_port.addr.eq(cur_wr_word_addr),
                    wr_port.data.eq(bus.wdata),
                ]
                with m.If(bus.wvalid):
                    m.d.comb += wr_port.en.eq(bus.wstrb)
                    m.d.sync += wr_beat_cnt.eq(wr_beat_cnt + 1)
                    with m.If(bus.wlast):
                        m.next = "WR_RESP"

            with m.State("WR_RESP"):
                m.d.comb += [
                    bus.bvalid.eq(1),
                    bus.bresp.eq(AXIResp.OKAY),
                ]
                if has_id:
                    m.d.comb += bus.bid.eq(wr_id)
                with m.If(bus.bready):
                    m.next = "WR_IDLE"

        # --- Read FSM ---
        with m.FSM(name="rd_fsm"):
            with m.State("RD_IDLE"):
                m.d.comb += bus.arready.eq(1)
                with m.If(bus.arvalid):
                    m.d.sync += [
                        rd_addr.eq(bus.araddr),
                        rd_len.eq(bus.arlen),
                        rd_beat_cnt.eq(0),
                    ]
                    if has_id:
                        m.d.sync += rd_id.eq(bus.arid)
                    # Start first read
                    if word_addr_shift > 0:
                        m.d.comb += rd_port.addr.eq(bus.araddr >> word_addr_shift)
                    else:
                        m.d.comb += rd_port.addr.eq(bus.araddr)
                    m.d.comb += rd_port.en.eq(1)
                    m.next = "RD_DATA"

            with m.State("RD_DATA"):
                # Compute word address for current beat
                cur_rd_word_addr = Signal(self._addr_width, name="cur_rd_word_addr")
                if word_addr_shift > 0:
                    m.d.comb += cur_rd_word_addr.eq(
                        (rd_addr >> word_addr_shift) + rd_beat_cnt
                    )
                else:
                    m.d.comb += cur_rd_word_addr.eq(rd_addr + rd_beat_cnt)

                m.d.comb += [
                    bus.rvalid.eq(1),
                    bus.rdata.eq(rd_port.data),
                    bus.rresp.eq(AXIResp.OKAY),
                    bus.rlast.eq(rd_beat_cnt == rd_len),
                ]
                if has_id:
                    m.d.comb += bus.rid.eq(rd_id)

                with m.If(bus.rready):
                    with m.If(rd_beat_cnt == rd_len):
                        m.next = "RD_IDLE"
                    with m.Else():
                        m.d.sync += rd_beat_cnt.eq(rd_beat_cnt + 1)
                        # Pre-fetch next beat
                        m.d.comb += [
                            rd_port.addr.eq(cur_rd_word_addr + 1),
                            rd_port.en.eq(1),
                        ]

        return m


# ---------------------------------------------------------------------------
# Top-level wrapper for simulation: decoder + SRAM subordinate
# ---------------------------------------------------------------------------

class _DecoderWithSRAM(wiring.Component):
    """Wraps an AXI4Decoder with one SRAM subordinate for simulation."""
    def __init__(self, *, addr_width, data_width, id_width=0, sram_depth=256):
        self._addr_width = addr_width
        self._data_width = data_width
        self._id_width = id_width
        self._sram_depth = sram_depth
        sig = AXI4Signature(addr_width=addr_width, data_width=data_width, id_width=id_width)
        super().__init__({"bus": In(sig)})

    def elaborate(self, platform):
        m = Module()

        dec = AXI4Decoder(addr_width=self._addr_width, data_width=self._data_width,
                          id_width=self._id_width)

        # Create SRAM subordinate
        sub_addr_width = self._addr_width - 1  # half the address space
        sram = _AXI4SRAMSub(addr_width=sub_addr_width, data_width=self._data_width,
                             id_width=self._id_width, depth=self._sram_depth)

        sram.bus.memory_map = MemoryMap(addr_width=sub_addr_width, data_width=8)
        dec.add(sram.bus, name="sram", addr=0x0000)

        m.submodules.dec = dec
        m.submodules.sram = sram

        # Wire our bus to the decoder's bus
        m.d.comb += [
            # AW channel
            dec.bus.awaddr.eq(self.bus.awaddr),
            dec.bus.awprot.eq(self.bus.awprot),
            dec.bus.awlen.eq(self.bus.awlen),
            dec.bus.awsize.eq(self.bus.awsize),
            dec.bus.awburst.eq(self.bus.awburst),
            dec.bus.awlock.eq(self.bus.awlock),
            dec.bus.awcache.eq(self.bus.awcache),
            dec.bus.awqos.eq(self.bus.awqos),
            dec.bus.awregion.eq(self.bus.awregion),
            dec.bus.awvalid.eq(self.bus.awvalid),
            self.bus.awready.eq(dec.bus.awready),
            # W channel
            dec.bus.wdata.eq(self.bus.wdata),
            dec.bus.wstrb.eq(self.bus.wstrb),
            dec.bus.wlast.eq(self.bus.wlast),
            dec.bus.wvalid.eq(self.bus.wvalid),
            self.bus.wready.eq(dec.bus.wready),
            # B channel
            self.bus.bresp.eq(dec.bus.bresp),
            self.bus.bvalid.eq(dec.bus.bvalid),
            dec.bus.bready.eq(self.bus.bready),
            # AR channel
            dec.bus.araddr.eq(self.bus.araddr),
            dec.bus.arprot.eq(self.bus.arprot),
            dec.bus.arlen.eq(self.bus.arlen),
            dec.bus.arsize.eq(self.bus.arsize),
            dec.bus.arburst.eq(self.bus.arburst),
            dec.bus.arlock.eq(self.bus.arlock),
            dec.bus.arcache.eq(self.bus.arcache),
            dec.bus.arqos.eq(self.bus.arqos),
            dec.bus.arregion.eq(self.bus.arregion),
            dec.bus.arvalid.eq(self.bus.arvalid),
            self.bus.arready.eq(dec.bus.arready),
            # R channel
            self.bus.rdata.eq(dec.bus.rdata),
            self.bus.rresp.eq(dec.bus.rresp),
            self.bus.rvalid.eq(dec.bus.rvalid),
            self.bus.rlast.eq(dec.bus.rlast),
            dec.bus.rready.eq(self.bus.rready),
        ]
        if self._id_width > 0:
            m.d.comb += [
                dec.bus.awid.eq(self.bus.awid),
                self.bus.bid.eq(dec.bus.bid),
                dec.bus.arid.eq(self.bus.arid),
                self.bus.rid.eq(dec.bus.rid),
            ]

        return m


# ---------------------------------------------------------------------------
# AXI4 simulation helpers
# ---------------------------------------------------------------------------

async def _axi4_write_burst(ctx, bus, addr, data_list, *, awid=0, has_id=True):
    """Perform an AXI4 burst write transaction.

    In Amaranth's simulation model, ctx.set() sets values for the NEXT tick,
    and ctx.get() reads the CURRENT tick's values after await ctx.tick().
    AXI handshakes complete when both valid and ready are high on the same tick.

    Parameters
    ----------
    ctx : SimulatorContext
    bus : AXI4 bus interface
    addr : int
        Write address.
    data_list : list of int
        Data values for each beat.
    awid : int
        Transaction ID.
    has_id : bool
        Whether the bus has ID signals.
    """
    burst_len = len(data_list) - 1  # awlen = N-1

    # Drive AW channel
    ctx.set(bus.awaddr, addr)
    ctx.set(bus.awlen, burst_len)
    ctx.set(bus.awsize, 2)  # 4 bytes
    ctx.set(bus.awburst, AXIBurst.INCR)
    ctx.set(bus.awprot, 0)
    ctx.set(bus.awlock, 0)
    ctx.set(bus.awcache, 0)
    ctx.set(bus.awqos, 0)
    ctx.set(bus.awregion, 0)
    ctx.set(bus.awvalid, 1)
    if has_id:
        ctx.set(bus.awid, awid)

    # Wait for AW handshake
    for _ in range(100):
        await ctx.tick()
        if ctx.get(bus.awready):
            break
    # Don't deassert awvalid yet — wait for next tick so FSM latches transition
    await ctx.tick()
    ctx.set(bus.awvalid, 0)

    # Write data beats
    for beat_idx, data_val in enumerate(data_list):
        ctx.set(bus.wdata, data_val)
        ctx.set(bus.wstrb, 0xF)
        ctx.set(bus.wlast, 1 if beat_idx == burst_len else 0)
        ctx.set(bus.wvalid, 1)

        # Wait for W handshake
        for _ in range(100):
            await ctx.tick()
            if ctx.get(bus.wready):
                break

    # W handshake for last beat completed on this tick.
    # Wait one more tick so the FSM latches the transition before we deassert.
    await ctx.tick()
    ctx.set(bus.wvalid, 0)
    ctx.set(bus.wlast, 0)

    # Wait for B response
    ctx.set(bus.bready, 1)
    for _ in range(100):
        # Check if bvalid is already high (fast DECERR path)
        if ctx.get(bus.bvalid):
            break
        await ctx.tick()
        if ctx.get(bus.bvalid):
            break
    bresp = ctx.get(bus.bresp)
    bid = ctx.get(bus.bid) if has_id else 0
    ctx.set(bus.bready, 0)
    await ctx.tick()

    return bresp, bid


async def _axi4_read_burst(ctx, bus, addr, num_beats, *, arid=0, has_id=True):
    """Perform an AXI4 burst read transaction.

    Parameters
    ----------
    ctx : SimulatorContext
    bus : AXI4 bus interface
    addr : int
        Read address.
    num_beats : int
        Number of beats to read.
    arid : int
        Transaction ID.
    has_id : bool
        Whether the bus has ID signals.

    Returns
    -------
    tuple of (list of int, list of int, list of int, list of int)
        (data_list, resp_list, rid_list, rlast_list)
    """
    burst_len = num_beats - 1  # arlen = N-1

    # Drive AR channel
    ctx.set(bus.araddr, addr)
    ctx.set(bus.arlen, burst_len)
    ctx.set(bus.arsize, 2)  # 4 bytes
    ctx.set(bus.arburst, AXIBurst.INCR)
    ctx.set(bus.arprot, 0)
    ctx.set(bus.arlock, 0)
    ctx.set(bus.arcache, 0)
    ctx.set(bus.arqos, 0)
    ctx.set(bus.arregion, 0)
    ctx.set(bus.arvalid, 1)
    if has_id:
        ctx.set(bus.arid, arid)

    # Wait for AR handshake
    for _ in range(100):
        await ctx.tick()
        if ctx.get(bus.arready):
            break
    # Wait one more tick so FSM latches the transition
    await ctx.tick()
    ctx.set(bus.arvalid, 0)

    # Read data beats
    ctx.set(bus.rready, 1)
    data_list = []
    resp_list = []
    rid_list = []
    rlast_list = []

    for beat_idx in range(num_beats):
        for _ in range(100):
            if ctx.get(bus.rvalid):
                break
            await ctx.tick()
            if ctx.get(bus.rvalid):
                break
        data_list.append(ctx.get(bus.rdata))
        resp_list.append(ctx.get(bus.rresp))
        rid_list.append(ctx.get(bus.rid) if has_id else 0)
        rlast_list.append(ctx.get(bus.rlast))
        # Tick to consume this beat
        await ctx.tick()

    ctx.set(bus.rready, 0)
    await ctx.tick()

    return data_list, resp_list, rid_list, rlast_list


# ---------------------------------------------------------------------------
# AXI4 Decoder tests
# ---------------------------------------------------------------------------

class TestAXI4Decoder(unittest.TestCase):

    # --- Constructor tests ---

    def test_axi4_create(self):
        """Constructor with valid params."""
        dec = AXI4Decoder(addr_width=16, data_width=32)
        self.assertIsNotNone(dec.memory_map)
        self.assertEqual(dec.memory_map.addr_width, 16)
        self.assertEqual(dec.memory_map.data_width, 8)

    def test_axi4_create_with_id(self):
        """Constructor with id_width=4."""
        dec = AXI4Decoder(addr_width=16, data_width=32, id_width=4)
        self.assertIsNotNone(dec.memory_map)
        self.assertEqual(dec._id_width, 4)

    def test_axi4_create_invalid_addr_width(self):
        with self.assertRaises(TypeError):
            AXI4Decoder(addr_width=-1, data_width=32)

    def test_axi4_create_invalid_data_width_too_small(self):
        with self.assertRaises(ValueError):
            AXI4Decoder(addr_width=16, data_width=4)

    def test_axi4_create_invalid_data_width_not_pow2(self):
        with self.assertRaises(ValueError):
            AXI4Decoder(addr_width=16, data_width=12)

    def test_axi4_create_invalid_id_width(self):
        with self.assertRaises(TypeError):
            AXI4Decoder(addr_width=16, data_width=32, id_width=-1)

    # --- add() tests ---

    def test_axi4_add_subordinate(self):
        """Add a subordinate with matching params."""
        dec = AXI4Decoder(addr_width=16, data_width=32, id_width=4)
        sub = AXI4Interface(addr_width=14, data_width=32, id_width=4)
        sub.memory_map = MemoryMap(addr_width=14, data_width=8)
        dec.add(sub, name='sub1', addr=0x0000)

    def test_axi4_add_wrong_data_width(self):
        """Reject mismatched data_width."""
        dec = AXI4Decoder(addr_width=16, data_width=32, id_width=4)
        sub = AXI4Interface(addr_width=14, data_width=64, id_width=4)
        sub.memory_map = MemoryMap(addr_width=14, data_width=8)
        with self.assertRaises(ValueError):
            dec.add(sub, name='sub1', addr=0x0000)

    def test_axi4_add_wrong_id_width(self):
        """Reject mismatched id_width."""
        dec = AXI4Decoder(addr_width=16, data_width=32, id_width=4)
        sub = AXI4Interface(addr_width=14, data_width=32, id_width=2)
        sub.memory_map = MemoryMap(addr_width=14, data_width=8)
        with self.assertRaises(ValueError):
            dec.add(sub, name='sub1', addr=0x0000)

    def test_axi4_add_wrong_type(self):
        """Reject non-AXI4Interface."""
        dec = AXI4Decoder(addr_width=16, data_width=32)
        with self.assertRaises(TypeError):
            dec.add("not a bus", name='sub1', addr=0x0000)

    def test_axi4_add_wrong_type_axi4lite(self):
        """Reject AXI4LiteInterface (must be AXI4Interface)."""
        dec = AXI4Decoder(addr_width=16, data_width=32)
        sub = AXI4LiteInterface(addr_width=14, data_width=32)
        sub.memory_map = MemoryMap(addr_width=14, data_width=8)
        with self.assertRaises(TypeError):
            dec.add(sub, name='sub1', addr=0x0000)

    # --- Elaborate tests ---

    def test_axi4_elaborate_single_sub(self):
        """Elaborate with 1 subordinate."""
        dec = AXI4Decoder(addr_width=16, data_width=32)
        sub1 = AXI4Interface(addr_width=14, data_width=32)
        sub1.memory_map = MemoryMap(addr_width=14, data_width=8)
        dec.add(sub1, name='sub1', addr=0x0000)
        rtlil = convert(dec)
        self.assertGreater(len(rtlil), 0)

    def test_axi4_elaborate_single_sub_with_id(self):
        """Elaborate with 1 subordinate and id_width > 0."""
        dec = AXI4Decoder(addr_width=16, data_width=32, id_width=4)
        sub1 = AXI4Interface(addr_width=14, data_width=32, id_width=4)
        sub1.memory_map = MemoryMap(addr_width=14, data_width=8)
        dec.add(sub1, name='sub1', addr=0x0000)
        rtlil = convert(dec)
        self.assertGreater(len(rtlil), 0)

    def test_axi4_elaborate_two_subs(self):
        """Elaborate with 2 subordinates."""
        dec = AXI4Decoder(addr_width=16, data_width=32)
        sub1 = AXI4Interface(addr_width=14, data_width=32)
        sub1.memory_map = MemoryMap(addr_width=14, data_width=8)
        dec.add(sub1, name='sub1', addr=0x0000)
        sub2 = AXI4Interface(addr_width=14, data_width=32)
        sub2.memory_map = MemoryMap(addr_width=14, data_width=8)
        dec.add(sub2, name='sub2', addr=0x4000)
        rtlil = convert(dec)
        self.assertGreater(len(rtlil), 0)

    def test_axi4_elaborate_no_subs(self):
        """Elaborate with 0 subordinates (DECERR only)."""
        dec = AXI4Decoder(addr_width=16, data_width=32)
        rtlil = convert(dec)
        self.assertGreater(len(rtlil), 0)

    def test_axi4_elaborate_no_subs_with_id(self):
        """Elaborate with 0 subordinates and id_width > 0."""
        dec = AXI4Decoder(addr_width=16, data_width=32, id_width=4)
        rtlil = convert(dec)
        self.assertGreater(len(rtlil), 0)

    def test_axi4_align_to(self):
        dec = AXI4Decoder(addr_width=16, data_width=32)
        dec.align_to(12)

    # --- Simulation tests ---

    def test_axi4_sim_write_read_single_sub(self):
        """Simulation: write a burst of 4 beats, read it back, verify data."""
        dut = _DecoderWithSRAM(addr_width=16, data_width=32, id_width=4, sram_depth=256)

        async def testbench(ctx):
            bus = dut.bus
            test_data = [0xDEAD0001, 0xDEAD0002, 0xDEAD0003, 0xDEAD0004]

            # Write burst of 4 beats to address 0x0000
            bresp, bid = await _axi4_write_burst(
                ctx, bus, addr=0x0000, data_list=test_data, awid=0x5)
            assert bresp == AXIResp.OKAY, f"Expected OKAY, got {AXIResp(bresp)}"
            assert bid == 0x5, f"Expected bid=0x5, got {bid:#x}"

            # Read burst of 4 beats from address 0x0000
            data_list, resp_list, rid_list, rlast_list = await _axi4_read_burst(
                ctx, bus, addr=0x0000, num_beats=4, arid=0xA)

            # Verify responses
            for i, resp in enumerate(resp_list):
                assert resp == AXIResp.OKAY, \
                    f"Beat {i}: expected OKAY, got {AXIResp(resp)}"
            for i, rid in enumerate(rid_list):
                assert rid == 0xA, f"Beat {i}: expected rid=0xA, got {rid:#x}"

            # Verify rlast on last beat only
            assert rlast_list[-1] == 1, "rlast should be 1 on last beat"

            # Verify data
            for i, (expected, actual) in enumerate(zip(test_data, data_list)):
                assert actual == expected, \
                    f"Data mismatch at beat {i}: expected {expected:#x}, got {actual:#x}"

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("test_axi4_decoder_write_read.vcd"):
            sim.run()

    def test_axi4_sim_decerr(self):
        """Simulation: send transaction to unmapped address, verify DECERR."""
        dut = _DecoderWithSRAM(addr_width=16, data_width=32, id_width=4, sram_depth=256)

        async def testbench(ctx):
            bus = dut.bus

            # Write single beat to unmapped address (upper half)
            bresp, bid = await _axi4_write_burst(
                ctx, bus, addr=0x8000, data_list=[0xBADBAD], awid=0x7)
            assert bresp == AXIResp.DECERR, f"Expected DECERR, got {AXIResp(bresp)}"
            assert bid == 0x7, f"Expected bid=0x7, got {bid:#x}"

            # Read single beat from unmapped address
            data_list, resp_list, rid_list, rlast_list = await _axi4_read_burst(
                ctx, bus, addr=0x8000, num_beats=1, arid=0xB)

            assert resp_list[0] == AXIResp.DECERR, \
                f"Expected DECERR, got {AXIResp(resp_list[0])}"
            assert data_list[0] == 0, f"Expected rdata=0, got {data_list[0]:#x}"
            assert rlast_list[0] == 1, "rlast should be 1 for single-beat DECERR"
            assert rid_list[0] == 0xB, f"Expected rid=0xB, got {rid_list[0]:#x}"

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("test_axi4_decoder_decerr.vcd"):
            sim.run()


if __name__ == "__main__":
    unittest.main()
