"""Tests for AXI4LiteArbiter and AXI4Arbiter."""
import unittest
from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out, connect
from amaranth.lib.memory import MemoryData, Memory
from amaranth.back.rtlil import convert
from amaranth.sim import Simulator
from amaranth.utils import exact_log2

from amaranth_soc.axi.arbiter import AXI4LiteArbiter, AXI4Arbiter
from amaranth_soc.axi.bus import (
    AXI4LiteInterface, AXI4Signature, AXI4Interface, AXIResp, AXIBurst,
)
from amaranth_soc.memory import MemoryMap


# ---------------------------------------------------------------------------
# AXI4-Lite Arbiter tests (existing)
# ---------------------------------------------------------------------------

class TestAXI4LiteArbiter(unittest.TestCase):
    def test_create(self):
        arb = AXI4LiteArbiter(addr_width=16, data_width=32)
        self.assertIsNotNone(arb)

    def test_create_invalid_addr_width(self):
        with self.assertRaises(TypeError):
            AXI4LiteArbiter(addr_width=-1, data_width=32)

    def test_create_invalid_data_width(self):
        with self.assertRaises(ValueError):
            AXI4LiteArbiter(addr_width=16, data_width=16)

    def test_add_master(self):
        arb = AXI4LiteArbiter(addr_width=16, data_width=32)
        m1 = AXI4LiteInterface(addr_width=16, data_width=32)
        m1.memory_map = MemoryMap(addr_width=16, data_width=8)
        arb.add(m1)

    def test_add_master_wrong_addr_width(self):
        arb = AXI4LiteArbiter(addr_width=16, data_width=32)
        m1 = AXI4LiteInterface(addr_width=12, data_width=32)
        m1.memory_map = MemoryMap(addr_width=12, data_width=8)
        with self.assertRaises(ValueError):
            arb.add(m1)

    def test_add_master_wrong_data_width(self):
        arb = AXI4LiteArbiter(addr_width=16, data_width=32)
        m1 = AXI4LiteInterface(addr_width=16, data_width=64)
        m1.memory_map = MemoryMap(addr_width=16, data_width=8)
        with self.assertRaises(ValueError):
            arb.add(m1)

    def test_add_master_wrong_type(self):
        arb = AXI4LiteArbiter(addr_width=16, data_width=32)
        with self.assertRaises(TypeError):
            arb.add("not a bus")

    def test_elaborate_single_master(self):
        arb = AXI4LiteArbiter(addr_width=16, data_width=32)
        m1 = AXI4LiteInterface(addr_width=16, data_width=32)
        m1.memory_map = MemoryMap(addr_width=16, data_width=8)
        arb.add(m1)
        rtlil = convert(arb)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_two_masters(self):
        arb = AXI4LiteArbiter(addr_width=16, data_width=32)
        m1 = AXI4LiteInterface(addr_width=16, data_width=32)
        m1.memory_map = MemoryMap(addr_width=16, data_width=8)
        arb.add(m1)
        m2 = AXI4LiteInterface(addr_width=16, data_width=32)
        m2.memory_map = MemoryMap(addr_width=16, data_width=8)
        arb.add(m2)
        rtlil = convert(arb)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_no_masters(self):
        """Arbiter with no masters should still elaborate (tie-off path)."""
        arb = AXI4LiteArbiter(addr_width=16, data_width=32)
        rtlil = convert(arb)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_three_masters(self):
        arb = AXI4LiteArbiter(addr_width=16, data_width=32)
        for _ in range(3):
            m = AXI4LiteInterface(addr_width=16, data_width=32)
            m.memory_map = MemoryMap(addr_width=16, data_width=8)
            arb.add(m)
        rtlil = convert(arb)
        self.assertGreater(len(rtlil), 0)


# ---------------------------------------------------------------------------
# Simple AXI4 SRAM subordinate for arbiter testing
# ---------------------------------------------------------------------------

class _AXI4SRAMSub(wiring.Component):
    """Simple AXI4 SRAM subordinate for testing.

    Supports single-beat and burst transactions with byte-lane strobes.
    Uses In(sig) because this is a subordinate (receives AXI transactions).
    """
    def __init__(self, *, addr_width, data_width, id_width=0, depth=256):
        self._depth = depth
        self._data_width = data_width
        self._id_width = id_width
        self._addr_width = addr_width
        sig = AXI4Signature(addr_width=addr_width, data_width=data_width, id_width=id_width)
        super().__init__({"bus": In(sig)})

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
                        m.d.comb += [
                            rd_port.addr.eq(cur_rd_word_addr + 1),
                            rd_port.en.eq(1),
                        ]

        return m


# ---------------------------------------------------------------------------
# AXI4 simulation helpers
# ---------------------------------------------------------------------------

async def _axi4_write_burst(ctx, bus, addr, data_list, *, awid=0, has_id=True):
    """Perform an AXI4 burst write transaction.

    In Amaranth simulation, after await ctx.tick(), ctx.get() reads the
    combinational state based on UPDATED registers. So if a handshake
    completes on a tick, the FSM has already transitioned by the time
    we read. We handle this by checking for the NEXT state's signals
    (e.g., wready indicates the subordinate moved to DATA phase).
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

    # Wait for AW handshake — check awready OR wready (subordinate moved to data phase)
    for _ in range(100):
        await ctx.tick()
        if ctx.get(bus.awready) or ctx.get(bus.wready):
            break
    ctx.set(bus.awvalid, 0)

    # Write data beats
    for beat_idx, data_val in enumerate(data_list):
        ctx.set(bus.wdata, data_val)
        ctx.set(bus.wstrb, 0xF)
        ctx.set(bus.wlast, 1 if beat_idx == burst_len else 0)
        ctx.set(bus.wvalid, 1)

        for _ in range(100):
            await ctx.tick()
            if ctx.get(bus.wready) or ctx.get(bus.bvalid):
                break

    ctx.set(bus.wvalid, 0)
    ctx.set(bus.wlast, 0)

    # Wait for B response — DON'T set bready yet so we can read the response
    for _ in range(100):
        await ctx.tick()
        if ctx.get(bus.bvalid):
            break

    # Read response data while bvalid is high (before completing handshake)
    bresp = ctx.get(bus.bresp)
    bid = ctx.get(bus.bid) if has_id else 0

    # Now complete the B handshake
    ctx.set(bus.bready, 1)
    await ctx.tick()
    ctx.set(bus.bready, 0)
    await ctx.tick()

    return bresp, bid


async def _axi4_read_burst(ctx, bus, addr, num_beats, *, arid=0, has_id=True):
    """Perform an AXI4 burst read transaction.

    Handles both fast subordinates (arready in same cycle) and slow ones.
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

    # Wait for AR handshake — check arready OR rvalid (subordinate already responding)
    for _ in range(100):
        await ctx.tick()
        if ctx.get(bus.arready) or ctx.get(bus.rvalid):
            break
    ctx.set(bus.arvalid, 0)

    # Read data beats — read data BEFORE asserting rready to capture it
    data_list = []
    resp_list = []
    rid_list = []
    rlast_list = []

    for beat_idx in range(num_beats):
        # Wait for rvalid without rready (so data stays stable)
        for _ in range(100):
            if ctx.get(bus.rvalid):
                break
            await ctx.tick()
            if ctx.get(bus.rvalid):
                break

        # Capture data while rvalid is high
        data_list.append(ctx.get(bus.rdata))
        resp_list.append(ctx.get(bus.rresp))
        rid_list.append(ctx.get(bus.rid) if has_id else 0)
        rlast_list.append(ctx.get(bus.rlast))

        # Complete the handshake by asserting rready for one tick
        ctx.set(bus.rready, 1)
        await ctx.tick()
        ctx.set(bus.rready, 0)

    await ctx.tick()

    return data_list, resp_list, rid_list, rlast_list


# ---------------------------------------------------------------------------
# Arbiter test harness: arbiter + SRAM subordinate
# ---------------------------------------------------------------------------

class _ArbiterTestHarness(wiring.Component):
    """Arbiter + simple SRAM for testing.

    Exposes the master AXI4Interfaces directly for testbench access.
    """
    def __init__(self, *, addr_width, data_width, id_width=0, n_masters):
        self._addr_width = addr_width
        self._data_width = data_width
        self._id_width = id_width
        self._n_masters = n_masters
        self._master_ifaces = []

        # No external ports — testbench accesses master_ifaces directly
        super().__init__({})

    @property
    def masters(self):
        return self._master_ifaces

    def elaborate(self, platform):
        m = Module()

        arb = AXI4Arbiter(addr_width=self._addr_width, data_width=self._data_width,
                           id_width=self._id_width)

        sram = _AXI4SRAMSub(addr_width=self._addr_width, data_width=self._data_width,
                              id_width=self._id_width, depth=256)

        # Create and add master interfaces to arbiter
        for i in range(self._n_masters):
            master_iface = AXI4Interface(addr_width=self._addr_width,
                                          data_width=self._data_width,
                                          id_width=self._id_width)
            master_iface.memory_map = MemoryMap(addr_width=self._addr_width, data_width=8)
            arb.add(master_iface)
            self._master_ifaces.append(master_iface)

        m.submodules.arb = arb
        m.submodules.sram = sram

        # Wire arbiter bus (Out) to SRAM bus (In) manually
        # Out members of sig (driven by arbiter, read by SRAM):
        ab = arb.bus
        sb = sram.bus
        m.d.comb += [
            sb.awaddr.eq(ab.awaddr), sb.awprot.eq(ab.awprot),
            sb.awlen.eq(ab.awlen), sb.awsize.eq(ab.awsize),
            sb.awburst.eq(ab.awburst), sb.awlock.eq(ab.awlock),
            sb.awcache.eq(ab.awcache), sb.awqos.eq(ab.awqos),
            sb.awregion.eq(ab.awregion), sb.awvalid.eq(ab.awvalid),
            sb.wdata.eq(ab.wdata), sb.wstrb.eq(ab.wstrb),
            sb.wlast.eq(ab.wlast), sb.wvalid.eq(ab.wvalid),
            sb.bready.eq(ab.bready),
            sb.araddr.eq(ab.araddr), sb.arprot.eq(ab.arprot),
            sb.arlen.eq(ab.arlen), sb.arsize.eq(ab.arsize),
            sb.arburst.eq(ab.arburst), sb.arlock.eq(ab.arlock),
            sb.arcache.eq(ab.arcache), sb.arqos.eq(ab.arqos),
            sb.arregion.eq(ab.arregion), sb.arvalid.eq(ab.arvalid),
            sb.rready.eq(ab.rready),
        ]
        # In members of sig (driven by SRAM, read by arbiter):
        m.d.comb += [
            ab.awready.eq(sb.awready),
            ab.wready.eq(sb.wready),
            ab.bresp.eq(sb.bresp), ab.bvalid.eq(sb.bvalid),
            ab.arready.eq(sb.arready),
            ab.rdata.eq(sb.rdata), ab.rresp.eq(sb.rresp),
            ab.rvalid.eq(sb.rvalid), ab.rlast.eq(sb.rlast),
        ]
        if self._id_width > 0:
            m.d.comb += [
                sb.awid.eq(ab.awid), sb.arid.eq(ab.arid),
                ab.bid.eq(sb.bid), ab.rid.eq(sb.rid),
            ]

        return m


# ---------------------------------------------------------------------------
# AXI4 Arbiter tests
# ---------------------------------------------------------------------------

class TestAXI4Arbiter(unittest.TestCase):

    # --- Constructor tests ---

    def test_axi4_create(self):
        """Constructor with valid params."""
        arb = AXI4Arbiter(addr_width=16, data_width=32)
        self.assertIsNotNone(arb)

    def test_axi4_create_with_id(self):
        """Constructor with id_width=4."""
        arb = AXI4Arbiter(addr_width=16, data_width=32, id_width=4)
        self.assertIsNotNone(arb)
        self.assertEqual(arb._id_width, 4)

    def test_axi4_create_invalid_addr_width(self):
        """Reject negative addr_width."""
        with self.assertRaises(TypeError):
            AXI4Arbiter(addr_width=-1, data_width=32)

    def test_axi4_create_invalid_data_width(self):
        """Reject invalid data_width (not power of 2 or < 8)."""
        with self.assertRaises(ValueError):
            AXI4Arbiter(addr_width=16, data_width=4)
        with self.assertRaises(ValueError):
            AXI4Arbiter(addr_width=16, data_width=12)

    # --- add() tests ---

    def test_axi4_add_master(self):
        """Add a matching master."""
        arb = AXI4Arbiter(addr_width=16, data_width=32)
        m1 = AXI4Interface(addr_width=16, data_width=32)
        m1.memory_map = MemoryMap(addr_width=16, data_width=8)
        arb.add(m1)

    def test_axi4_add_wrong_data_width(self):
        """Reject mismatched data_width."""
        arb = AXI4Arbiter(addr_width=16, data_width=32)
        m1 = AXI4Interface(addr_width=16, data_width=64)
        m1.memory_map = MemoryMap(addr_width=16, data_width=8)
        with self.assertRaises(ValueError):
            arb.add(m1)

    def test_axi4_add_wrong_id_width(self):
        """Reject mismatched id_width."""
        arb = AXI4Arbiter(addr_width=16, data_width=32, id_width=4)
        m1 = AXI4Interface(addr_width=16, data_width=32, id_width=2)
        m1.memory_map = MemoryMap(addr_width=16, data_width=8)
        with self.assertRaises(ValueError):
            arb.add(m1)

    def test_axi4_add_wrong_type(self):
        """Reject non-AXI4Interface."""
        arb = AXI4Arbiter(addr_width=16, data_width=32)
        with self.assertRaises(TypeError):
            arb.add("not a bus")

    # --- Elaborate tests ---

    def test_axi4_elaborate_single_master(self):
        """Elaborate with 1 master."""
        arb = AXI4Arbiter(addr_width=16, data_width=32)
        m1 = AXI4Interface(addr_width=16, data_width=32)
        m1.memory_map = MemoryMap(addr_width=16, data_width=8)
        arb.add(m1)
        rtlil = convert(arb)
        self.assertGreater(len(rtlil), 0)

    def test_axi4_elaborate_two_masters(self):
        """Elaborate with 2 masters."""
        arb = AXI4Arbiter(addr_width=16, data_width=32)
        m1 = AXI4Interface(addr_width=16, data_width=32)
        m1.memory_map = MemoryMap(addr_width=16, data_width=8)
        arb.add(m1)
        m2 = AXI4Interface(addr_width=16, data_width=32)
        m2.memory_map = MemoryMap(addr_width=16, data_width=8)
        arb.add(m2)
        rtlil = convert(arb)
        self.assertGreater(len(rtlil), 0)

    def test_axi4_elaborate_no_masters(self):
        """Elaborate tie-off path."""
        arb = AXI4Arbiter(addr_width=16, data_width=32)
        rtlil = convert(arb)
        self.assertGreater(len(rtlil), 0)

    def test_axi4_elaborate_no_masters_with_id(self):
        """Elaborate tie-off path with id_width > 0."""
        arb = AXI4Arbiter(addr_width=16, data_width=32, id_width=4)
        rtlil = convert(arb)
        self.assertGreater(len(rtlil), 0)

    def test_axi4_elaborate_with_id(self):
        """Elaborate with id_width > 0 and masters."""
        arb = AXI4Arbiter(addr_width=16, data_width=32, id_width=4)
        m1 = AXI4Interface(addr_width=16, data_width=32, id_width=4)
        m1.memory_map = MemoryMap(addr_width=16, data_width=8)
        arb.add(m1)
        rtlil = convert(arb)
        self.assertGreater(len(rtlil), 0)

    # --- Simulation tests ---

    def test_axi4_sim_single_master_burst(self):
        """Simulation: Single master writes a 4-beat burst, reads it back, verifies data."""
        dut = _ArbiterTestHarness(addr_width=16, data_width=32, id_width=4, n_masters=1)

        async def testbench(ctx):
            bus = dut.masters[0]
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
        with sim.write_vcd("test_axi4_arbiter_single_master.vcd"):
            sim.run()

    def test_axi4_sim_two_masters_elaborate(self):
        """Two-master arbiter elaborates and converts to RTLIL correctly."""
        dut = _ArbiterTestHarness(addr_width=16, data_width=32, id_width=4, n_masters=2)
        rtlil = convert(dut)
        self.assertGreater(len(rtlil), 0)


if __name__ == "__main__":
    unittest.main()
