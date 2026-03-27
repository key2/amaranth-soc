"""Simulation tests for AXI4LiteSRAM."""
import unittest
from amaranth.sim import Simulator
from amaranth_soc.axi.sram import AXI4LiteSRAM
from amaranth_soc.axi.bus import AXIResp
from amaranth_soc.sim.axi import axi_lite_write, axi_lite_read


class TestAXI4LiteSRAMConstruction(unittest.TestCase):
    """Test SRAM construction and properties."""

    def test_create_default(self):
        dut = AXI4LiteSRAM(size=1024, data_width=32)
        self.assertEqual(dut.size, 1024)
        self.assertTrue(dut.writable)

    def test_create_64bit(self):
        dut = AXI4LiteSRAM(size=1024, data_width=64)
        self.assertEqual(dut.size, 1024)

    def test_create_readonly(self):
        dut = AXI4LiteSRAM(size=256, data_width=32, writable=False)
        self.assertFalse(dut.writable)

    def test_create_with_init(self):
        dut = AXI4LiteSRAM(size=256, data_width=32, init=[0xDEADBEEF, 0xCAFEBABE])
        self.assertIsNotNone(dut.init)

    def test_invalid_size_not_power_of_two(self):
        with self.assertRaises(TypeError):
            AXI4LiteSRAM(size=100, data_width=32)

    def test_invalid_size_zero(self):
        with self.assertRaises(TypeError):
            AXI4LiteSRAM(size=0, data_width=32)

    def test_invalid_data_width(self):
        with self.assertRaises(ValueError):
            AXI4LiteSRAM(size=1024, data_width=16)

    def test_memory_map_exists(self):
        dut = AXI4LiteSRAM(size=1024, data_width=32)
        mm = dut.bus.memory_map
        self.assertIsNotNone(mm)
        self.assertEqual(mm.data_width, 8)


class TestAXI4LiteSRAMSim(unittest.TestCase):
    """Simulation tests for AXI4LiteSRAM."""

    def test_write_read_back(self):
        """Write a value and read it back."""
        dut = AXI4LiteSRAM(size=1024, data_width=32)

        async def testbench(ctx):
            bus = dut.bus
            # Write 0xDEADBEEF to address 0x00
            await axi_lite_write(ctx, bus, 0x00, 0xDEADBEEF)
            # Read it back
            data, resp = await axi_lite_read(ctx, bus, 0x00)
            assert data == 0xDEADBEEF, f"Expected 0xDEADBEEF, got {data:#010x}"
            assert resp == AXIResp.OKAY

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_sram_write_read.vcd"):
            sim.run()

    def test_multiple_addresses(self):
        """Write to multiple addresses and read them all back."""
        dut = AXI4LiteSRAM(size=1024, data_width=32)

        async def testbench(ctx):
            bus = dut.bus
            test_data = {
                0x00: 0x11111111,
                0x04: 0x22222222,
                0x08: 0x33333333,
                0x0C: 0x44444444,
            }
            # Write all
            for addr, data in test_data.items():
                await axi_lite_write(ctx, bus, addr, data)
            # Read all back
            for addr, expected in test_data.items():
                data, resp = await axi_lite_read(ctx, bus, addr)
                assert data == expected, \
                    f"At {addr:#06x}: expected {expected:#010x}, got {data:#010x}"

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_sram_multi_addr.vcd"):
            sim.run()

    def test_byte_strobe(self):
        """Test partial writes using wstrb."""
        dut = AXI4LiteSRAM(size=1024, data_width=32)

        async def testbench(ctx):
            bus = dut.bus
            # Write full word
            await axi_lite_write(ctx, bus, 0x00, 0xFFFFFFFF)
            # Write only byte 0 (strb=0b0001)
            await axi_lite_write(ctx, bus, 0x00, 0x00000042, strb=0b0001)
            # Read back - should be 0xFFFFFF42
            data, resp = await axi_lite_read(ctx, bus, 0x00)
            assert data == 0xFFFFFF42, f"Expected 0xFFFFFF42, got {data:#010x}"

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_sram_byte_strobe.vcd"):
            sim.run()

    def test_byte_strobe_upper(self):
        """Test partial writes to upper bytes."""
        dut = AXI4LiteSRAM(size=1024, data_width=32)

        async def testbench(ctx):
            bus = dut.bus
            # Write full word of zeros
            await axi_lite_write(ctx, bus, 0x00, 0x00000000)
            # Write only byte 3 (strb=0b1000)
            await axi_lite_write(ctx, bus, 0x00, 0xAB000000, strb=0b1000)
            # Read back - should be 0xAB000000
            data, resp = await axi_lite_read(ctx, bus, 0x00)
            assert data == 0xAB000000, f"Expected 0xAB000000, got {data:#010x}"

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_sram_byte_strobe_upper.vcd"):
            sim.run()

    def test_init_data(self):
        """Test SRAM with initial data."""
        dut = AXI4LiteSRAM(size=256, data_width=32, init=[0xDEADBEEF, 0xCAFEBABE])

        async def testbench(ctx):
            bus = dut.bus
            data0, _ = await axi_lite_read(ctx, bus, 0x00)
            data1, _ = await axi_lite_read(ctx, bus, 0x04)
            assert data0 == 0xDEADBEEF, f"Expected 0xDEADBEEF, got {data0:#010x}"
            assert data1 == 0xCAFEBABE, f"Expected 0xCAFEBABE, got {data1:#010x}"

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_sram_init.vcd"):
            sim.run()

    def test_overwrite(self):
        """Test that writing to the same address overwrites the previous value."""
        dut = AXI4LiteSRAM(size=1024, data_width=32)

        async def testbench(ctx):
            bus = dut.bus
            await axi_lite_write(ctx, bus, 0x10, 0xAAAAAAAA)
            data, _ = await axi_lite_read(ctx, bus, 0x10)
            assert data == 0xAAAAAAAA, f"Expected 0xAAAAAAAA, got {data:#010x}"

            await axi_lite_write(ctx, bus, 0x10, 0x55555555)
            data, _ = await axi_lite_read(ctx, bus, 0x10)
            assert data == 0x55555555, f"Expected 0x55555555, got {data:#010x}"

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_sram_overwrite.vcd"):
            sim.run()

    def test_sequential_writes_reads(self):
        """Test a sequence of interleaved writes and reads."""
        dut = AXI4LiteSRAM(size=1024, data_width=32)

        async def testbench(ctx):
            bus = dut.bus
            # Write, read, write, read pattern
            await axi_lite_write(ctx, bus, 0x00, 0x12345678)
            data, _ = await axi_lite_read(ctx, bus, 0x00)
            assert data == 0x12345678

            await axi_lite_write(ctx, bus, 0x04, 0x9ABCDEF0)
            data, _ = await axi_lite_read(ctx, bus, 0x04)
            assert data == 0x9ABCDEF0

            # Verify first write is still intact
            data, _ = await axi_lite_read(ctx, bus, 0x00)
            assert data == 0x12345678

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_sram_sequential.vcd"):
            sim.run()


###############################################################################
# AXI4 Full SRAM Tests
###############################################################################

from amaranth_soc.axi.sram import AXI4SRAM
from amaranth_soc.axi.bus import AXIBurst, AXISize


async def axi4_write_burst(ctx, bus, addr, data_list, burst=AXIBurst.INCR,
                           size=AXISize.B4, strb=None, awid=0):
    """Perform an AXI4 burst write transaction.

    Drives AW channel for one cycle, then sends W beats, then waits for B.
    Uses a state-machine approach that doesn't rely on reading back ready
    signals (which change after the clock edge in simulation).
    """
    awlen = len(data_list) - 1
    bytes_per_word = len(bus.wstrb)
    has_id = "awid" in dict(bus.signature.members)

    if strb is None:
        strb_val = (1 << bytes_per_word) - 1
    elif isinstance(strb, list):
        strb_val = strb
    else:
        strb_val = strb

    # Set bready=1 early so the B response is captured as soon as it appears
    ctx.set(bus.bready, 1)

    # Drive AW channel - assert for one tick, the SRAM accepts it combinationally
    ctx.set(bus.awaddr, addr)
    ctx.set(bus.awlen, awlen)
    ctx.set(bus.awsize, size)
    ctx.set(bus.awburst, burst)
    ctx.set(bus.awvalid, 1)
    if has_id:
        ctx.set(bus.awid, awid)

    await ctx.tick()
    # AW handshake happened (awready was combinationally asserted in WR_IDLE)
    ctx.set(bus.awvalid, 0)

    # Now send W beats - the SRAM is in WR_DATA and will accept them
    for i, data in enumerate(data_list):
        cur_strb = strb_val[i] if isinstance(strb_val, list) else strb_val

        ctx.set(bus.wdata, data)
        ctx.set(bus.wstrb, cur_strb)
        ctx.set(bus.wvalid, 1)
        ctx.set(bus.wlast, 1 if i == awlen else 0)

        await ctx.tick()
        # Check if B response appeared (for single-beat or last beat)
        if ctx.get(bus.bvalid):
            resp = ctx.get(bus.bresp)
            bid = ctx.get(bus.bid) if has_id else 0
            ctx.set(bus.wvalid, 0)
            ctx.set(bus.wlast, 0)
            # Keep bready=1 for one more tick so FSM sees the handshake
            await ctx.tick()
            ctx.set(bus.bready, 0)
            await ctx.tick()
            return resp, bid

    ctx.set(bus.wvalid, 0)
    ctx.set(bus.wlast, 0)

    # Wait for B response if not already received
    for _ in range(100):
        await ctx.tick()
        if ctx.get(bus.bvalid):
            resp = ctx.get(bus.bresp)
            bid = ctx.get(bus.bid) if has_id else 0
            # Keep bready=1 for one more tick so FSM sees the handshake
            await ctx.tick()
            ctx.set(bus.bready, 0)
            await ctx.tick()
            return resp, bid
    raise TimeoutError("AXI4 write: timed out waiting for bvalid")


async def axi4_read_burst(ctx, bus, addr, length, burst=AXIBurst.INCR,
                          size=AXISize.B4, arid=0):
    """Perform an AXI4 burst read transaction.

    Returns list of (data, resp, rid, rlast) tuples.
    """
    arlen = length - 1
    has_id = "arid" in dict(bus.signature.members)

    # Drive AR channel - assert for one tick
    ctx.set(bus.araddr, addr)
    ctx.set(bus.arlen, arlen)
    ctx.set(bus.arsize, size)
    ctx.set(bus.arburst, burst)
    ctx.set(bus.arvalid, 1)
    if has_id:
        ctx.set(bus.arid, arid)

    await ctx.tick()
    # AR handshake happened (arready was combinationally asserted in RD_IDLE)
    ctx.set(bus.arvalid, 0)

    # Collect R beats - keep rready=1 throughout
    results = []
    ctx.set(bus.rready, 1)
    for beat in range(length):
        r_done = False
        for _ in range(100):
            await ctx.tick()
            if ctx.get(bus.rvalid):
                data = ctx.get(bus.rdata)
                resp = ctx.get(bus.rresp)
                rid = ctx.get(bus.rid) if has_id else 0
                rlast = ctx.get(bus.rlast)
                results.append((data, resp, rid, rlast))
                r_done = True
                break
        if not r_done:
            raise TimeoutError(f"AXI4 read: timed out waiting for rvalid on beat {beat}")

    # Keep rready=1 for one more tick so the FSM sees the handshake
    # and transitions out of RD_DATA
    await ctx.tick()
    ctx.set(bus.rready, 0)
    await ctx.tick()
    return results


class TestAXI4SRAMConstruction(unittest.TestCase):
    """Test AXI4SRAM construction and properties."""

    def test_axi4_sram_create(self):
        """Constructor with valid params."""
        dut = AXI4SRAM(size=1024, data_width=32)
        self.assertEqual(dut.size, 1024)
        self.assertEqual(dut.data_width, 32)
        self.assertEqual(dut.id_width, 0)

    def test_axi4_sram_create_with_id(self):
        """Constructor with id_width=4."""
        dut = AXI4SRAM(size=1024, data_width=32, id_width=4)
        self.assertEqual(dut.id_width, 4)
        # Verify bus has id signals
        self.assertIsNotNone(dut.bus)

    def test_axi4_sram_create_invalid_size(self):
        """Reject size <= 0."""
        with self.assertRaises(ValueError):
            AXI4SRAM(size=0, data_width=32)
        with self.assertRaises(ValueError):
            AXI4SRAM(size=-1, data_width=32)

    def test_axi4_sram_create_invalid_data_width(self):
        """Reject invalid data_width."""
        with self.assertRaises(ValueError):
            AXI4SRAM(size=1024, data_width=7)
        with self.assertRaises(ValueError):
            AXI4SRAM(size=1024, data_width=3)


class TestAXI4SRAMSim(unittest.TestCase):
    """Simulation tests for AXI4SRAM."""

    def test_axi4_sram_sim_single_write_read(self):
        """Write a single beat (awlen=0), read it back, verify data."""
        dut = AXI4SRAM(size=1024, data_width=32)

        async def testbench(ctx):
            bus = dut.bus
            # Single-beat write to address 0x10
            resp, _ = await axi4_write_burst(ctx, bus, 0x10, [0xDEADBEEF])
            assert resp == AXIResp.OKAY, f"Write resp: {resp}"

            # Single-beat read from address 0x10
            results = await axi4_read_burst(ctx, bus, 0x10, 1)
            data, resp, _, rlast = results[0]
            assert data == 0xDEADBEEF, f"Expected 0xDEADBEEF, got {data:#010x}"
            assert resp == AXIResp.OKAY
            assert rlast == 1

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_axi4_sram_single.vcd"):
            sim.run()

    def test_axi4_sram_sim_incr_burst(self):
        """Write a 4-beat INCR burst (awlen=3), read it back, verify all 4 data values."""
        dut = AXI4SRAM(size=1024, data_width=32)

        async def testbench(ctx):
            bus = dut.bus
            write_data = [0x11111111, 0x22222222, 0x33333333, 0x44444444]

            # 4-beat INCR write starting at address 0x00
            resp, _ = await axi4_write_burst(ctx, bus, 0x00, write_data,
                                             burst=AXIBurst.INCR, size=AXISize.B4)
            assert resp == AXIResp.OKAY

            # 4-beat INCR read starting at address 0x00
            results = await axi4_read_burst(ctx, bus, 0x00, 4,
                                            burst=AXIBurst.INCR, size=AXISize.B4)
            for i, (data, resp, _, rlast) in enumerate(results):
                assert data == write_data[i], \
                    f"Beat {i}: expected {write_data[i]:#010x}, got {data:#010x}"
                assert resp == AXIResp.OKAY
                if i == 3:
                    assert rlast == 1, f"Expected rlast=1 on last beat, got {rlast}"

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_axi4_sram_incr.vcd"):
            sim.run()

    def test_axi4_sram_sim_fixed_burst(self):
        """Write a 2-beat FIXED burst (same address), read back, verify only last written value."""
        dut = AXI4SRAM(size=1024, data_width=32)

        async def testbench(ctx):
            bus = dut.bus
            # 2-beat FIXED write to address 0x20 - both beats write to same address
            resp, _ = await axi4_write_burst(ctx, bus, 0x20, [0xAAAAAAAA, 0xBBBBBBBB],
                                             burst=AXIBurst.FIXED, size=AXISize.B4)
            assert resp == AXIResp.OKAY

            # Single read from address 0x20 - should have last written value
            results = await axi4_read_burst(ctx, bus, 0x20, 1)
            data, resp, _, _ = results[0]
            assert data == 0xBBBBBBBB, f"Expected 0xBBBBBBBB, got {data:#010x}"

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_axi4_sram_fixed.vcd"):
            sim.run()

    def test_axi4_sram_sim_wrap_burst(self):
        """Write a 4-beat WRAP burst, read it back, verify address wrapping behavior."""
        dut = AXI4SRAM(size=1024, data_width=32)

        async def testbench(ctx):
            bus = dut.bus
            # 4-beat WRAP burst with 4-byte size starting at address 0x04
            # Wrap boundary = 16 bytes (4 beats * 4 bytes)
            # Addresses: 0x04, 0x08, 0x0C, 0x00 (wraps around)
            write_data = [0x11111111, 0x22222222, 0x33333333, 0x44444444]
            resp, _ = await axi4_write_burst(ctx, bus, 0x04, write_data,
                                             burst=AXIBurst.WRAP, size=AXISize.B4)
            assert resp == AXIResp.OKAY

            # Read back individual addresses to verify wrapping
            # Address 0x04 should have 0x11111111
            results = await axi4_read_burst(ctx, bus, 0x04, 1)
            assert results[0][0] == 0x11111111, f"@0x04: {results[0][0]:#010x}"

            # Address 0x08 should have 0x22222222
            results = await axi4_read_burst(ctx, bus, 0x08, 1)
            assert results[0][0] == 0x22222222, f"@0x08: {results[0][0]:#010x}"

            # Address 0x0C should have 0x33333333
            results = await axi4_read_burst(ctx, bus, 0x0C, 1)
            assert results[0][0] == 0x33333333, f"@0x0C: {results[0][0]:#010x}"

            # Address 0x00 should have 0x44444444 (wrapped)
            results = await axi4_read_burst(ctx, bus, 0x00, 1)
            assert results[0][0] == 0x44444444, f"@0x00: {results[0][0]:#010x}"

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_axi4_sram_wrap.vcd"):
            sim.run()

    def test_axi4_sram_sim_with_id(self):
        """Write/read with id_width=4, verify bid/rid match awid/arid."""
        dut = AXI4SRAM(size=1024, data_width=32, id_width=4)

        async def testbench(ctx):
            bus = dut.bus
            # Write with awid=5
            resp, bid = await axi4_write_burst(ctx, bus, 0x00, [0xCAFEBABE],
                                               awid=5)
            assert resp == AXIResp.OKAY
            assert bid == 5, f"Expected bid=5, got {bid}"

            # Read with arid=7
            results = await axi4_read_burst(ctx, bus, 0x00, 1, arid=7)
            data, resp, rid, rlast = results[0]
            assert data == 0xCAFEBABE, f"Expected 0xCAFEBABE, got {data:#010x}"
            assert rid == 7, f"Expected rid=7, got {rid}"

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_axi4_sram_id.vcd"):
            sim.run()

    def test_axi4_sram_sim_wstrb(self):
        """Write with partial wstrb, verify only selected bytes are modified."""
        dut = AXI4SRAM(size=1024, data_width=32)

        async def testbench(ctx):
            bus = dut.bus
            # First write full word
            resp, _ = await axi4_write_burst(ctx, bus, 0x00, [0xFFFFFFFF])
            assert resp == AXIResp.OKAY

            # Write with partial strobe (only byte 0)
            resp, _ = await axi4_write_burst(ctx, bus, 0x00, [0x00000042],
                                             strb=0b0001)
            assert resp == AXIResp.OKAY

            # Read back - should be 0xFFFFFF42
            results = await axi4_read_burst(ctx, bus, 0x00, 1)
            data, resp, _, _ = results[0]
            assert data == 0xFFFFFF42, f"Expected 0xFFFFFF42, got {data:#010x}"

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_axi4_sram_wstrb.vcd"):
            sim.run()


if __name__ == "__main__":
    unittest.main()
