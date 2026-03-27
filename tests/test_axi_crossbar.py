"""Tests for AXI4-Lite NxM crossbar interconnect."""
import unittest
from amaranth.back.rtlil import convert

from amaranth_soc.axi.crossbar import AXI4LiteCrossbar
from amaranth_soc.axi.bus import AXI4LiteInterface
from amaranth_soc.memory import MemoryMap


class TestAXI4LiteCrossbarConstruction(unittest.TestCase):
    """Test AXI4LiteCrossbar construction and parameter validation."""

    def test_create_basic(self):
        """Construct with basic valid parameters."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        self.assertEqual(xbar.addr_width, 16)
        self.assertEqual(xbar.data_width, 32)

    def test_create_64bit(self):
        """Construct with 64-bit data width."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=64)
        self.assertEqual(xbar.data_width, 64)

    def test_create_wide_addr(self):
        """Construct with wide address width."""
        xbar = AXI4LiteCrossbar(addr_width=32, data_width=32)
        self.assertEqual(xbar.addr_width, 32)

    def test_create_zero_addr_width(self):
        """Construct with addr_width=0 (edge case)."""
        xbar = AXI4LiteCrossbar(addr_width=0, data_width=32)
        self.assertEqual(xbar.addr_width, 0)

    def test_invalid_addr_width_negative(self):
        """Negative address width should raise TypeError."""
        with self.assertRaises(TypeError):
            AXI4LiteCrossbar(addr_width=-1, data_width=32)

    def test_invalid_addr_width_string(self):
        """String address width should raise TypeError."""
        with self.assertRaises(TypeError):
            AXI4LiteCrossbar(addr_width="16", data_width=32)

    def test_invalid_data_width_16(self):
        """Data width 16 should raise ValueError."""
        with self.assertRaises(ValueError):
            AXI4LiteCrossbar(addr_width=16, data_width=16)

    def test_valid_data_width_128(self):
        """Data width 128 should now be accepted (power of 2 >= 32)."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=128)
        self.assertEqual(xbar.data_width, 128)

    def test_invalid_data_width_not_power_of_2(self):
        """Data width 48 (not power of 2) should raise ValueError."""
        with self.assertRaises(ValueError):
            AXI4LiteCrossbar(addr_width=16, data_width=48)


class TestAXI4LiteCrossbarConfiguration(unittest.TestCase):
    """Test AXI4LiteCrossbar add_master/add_slave configuration."""

    def _make_master(self, addr_width=16, data_width=32):
        """Helper to create a master bus interface."""
        return AXI4LiteInterface(addr_width=addr_width, data_width=data_width)

    def _make_slave(self, addr_width=14, data_width=32):
        """Helper to create a slave bus interface with memory map."""
        iface = AXI4LiteInterface(addr_width=addr_width, data_width=data_width)
        iface.memory_map = MemoryMap(addr_width=addr_width, data_width=8)
        return iface

    def test_add_master(self):
        """Add a single master."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        master = self._make_master()
        xbar.add_master(master, name="cpu")

    def test_add_slave(self):
        """Add a single slave."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        slave = self._make_slave()
        xbar.add_slave(slave, name="sram", addr=0x0000)

    def test_add_multiple_masters(self):
        """Add multiple masters."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        m1 = self._make_master()
        m2 = self._make_master()
        xbar.add_master(m1, name="cpu")
        xbar.add_master(m2, name="dma")

    def test_add_multiple_slaves(self):
        """Add multiple slaves at different addresses."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        s1 = self._make_slave()
        s2 = self._make_slave()
        xbar.add_slave(s1, name="sram", addr=0x0000)
        xbar.add_slave(s2, name="uart", addr=0x4000)

    def test_add_master_wrong_data_width(self):
        """Master with wrong data width should raise ValueError."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        master = self._make_master(data_width=64)
        with self.assertRaises(ValueError):
            xbar.add_master(master)

    def test_add_slave_wrong_data_width(self):
        """Slave with wrong data width should raise ValueError."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        slave = self._make_slave(data_width=64)
        with self.assertRaises(ValueError):
            xbar.add_slave(slave, name="bad")

    def test_add_master_wrong_type(self):
        """Non-AXI4LiteInterface master should raise TypeError."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        with self.assertRaises(TypeError):
            xbar.add_master("not a bus")

    def test_add_slave_wrong_type(self):
        """Non-AXI4LiteInterface slave should raise TypeError."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        with self.assertRaises(TypeError):
            xbar.add_slave("not a bus", name="bad")

    def test_auto_name_master(self):
        """Masters without explicit name get auto-named."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        m1 = self._make_master()
        m2 = self._make_master()
        xbar.add_master(m1)
        xbar.add_master(m2)

    def test_auto_name_slave(self):
        """Slaves without explicit name get auto-named."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        s1 = self._make_slave()
        xbar.add_slave(s1, addr=0x0000)


class TestAXI4LiteCrossbarElaboration(unittest.TestCase):
    """Test AXI4LiteCrossbar RTLIL elaboration."""

    def _make_master(self, addr_width=16, data_width=32):
        return AXI4LiteInterface(addr_width=addr_width, data_width=data_width)

    def _make_slave(self, addr_width=14, data_width=32):
        """Create a slave with memory map."""
        iface = AXI4LiteInterface(addr_width=addr_width, data_width=data_width)
        iface.memory_map = MemoryMap(addr_width=addr_width, data_width=8)
        return iface

    def test_elaborate_empty(self):
        """Crossbar with no masters/slaves should elaborate (empty module)."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        rtlil = convert(xbar)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_1x1(self):
        """Elaborate 1 master × 1 slave crossbar."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        m = self._make_master()
        s = self._make_slave()
        xbar.add_master(m, name="cpu")
        xbar.add_slave(s, name="sram", addr=0x0000)
        rtlil = convert(xbar)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_2x1(self):
        """Elaborate 2 masters × 1 slave crossbar."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        m1 = self._make_master()
        m2 = self._make_master()
        s = self._make_slave()
        xbar.add_master(m1, name="cpu")
        xbar.add_master(m2, name="dma")
        xbar.add_slave(s, name="sram", addr=0x0000)
        rtlil = convert(xbar)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_1x2(self):
        """Elaborate 1 master × 2 slaves crossbar."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        m = self._make_master()
        s1 = self._make_slave()
        s2 = self._make_slave()
        xbar.add_master(m, name="cpu")
        xbar.add_slave(s1, name="sram", addr=0x0000)
        xbar.add_slave(s2, name="uart", addr=0x4000)
        rtlil = convert(xbar)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_2x2(self):
        """Elaborate 2 masters × 2 slaves crossbar."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        m1 = self._make_master()
        m2 = self._make_master()
        s1 = self._make_slave()
        s2 = self._make_slave()
        xbar.add_master(m1, name="cpu")
        xbar.add_master(m2, name="dma")
        xbar.add_slave(s1, name="sram", addr=0x0000)
        xbar.add_slave(s2, name="uart", addr=0x4000)
        rtlil = convert(xbar)
        self.assertGreater(len(rtlil), 0)

    def test_cannot_add_after_elaborate(self):
        """Adding masters/slaves after elaborate() should raise RuntimeError."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        m = self._make_master()
        s = self._make_slave()
        xbar.add_master(m, name="cpu")
        xbar.add_slave(s, name="sram", addr=0x0000)
        # Elaborate to lock the crossbar
        convert(xbar)
        # Now adding should fail
        m2 = self._make_master()
        with self.assertRaises(RuntimeError):
            xbar.add_master(m2, name="dma")
        s2 = self._make_slave()
        with self.assertRaises(RuntimeError):
            xbar.add_slave(s2, name="uart", addr=0x4000)


###############################################################################
# AXI4 Full Crossbar Tests
###############################################################################

from amaranth.sim import Simulator
from amaranth_soc.axi.crossbar import AXI4Crossbar
from amaranth_soc.axi.bus import AXI4Interface, AXIBurst, AXISize, AXIResp
from amaranth_soc.axi.sram import AXI4SRAM


async def axi4_write_burst(ctx, bus, addr, data_list, burst=AXIBurst.INCR,
                           size=AXISize.B4, strb=None, awid=0):
    """Perform an AXI4 burst write transaction through a crossbar.

    The crossbar adds pipeline stages (decoder FSM + arbiter), so handshakes
    need an extra cycle: when awready appears, keep awvalid=1 for one more
    tick so the decoder's WR_ADDR state can complete the handshake.

    For W beats, the SRAM transitions to WR_RESP on the same cycle as the
    last beat (wlast=1), so bvalid may appear instead of wready on the last
    beat.
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

    # Drive AW channel
    ctx.set(bus.awaddr, addr)
    ctx.set(bus.awlen, awlen)
    ctx.set(bus.awsize, size)
    ctx.set(bus.awburst, burst)
    ctx.set(bus.awvalid, 1)
    ctx.set(bus.bready, 1)
    if has_id:
        ctx.set(bus.awid, awid)

    # Wait for AW handshake - keep awvalid=1 until we see awready,
    # then tick once more with awvalid still high so the decoder FSM
    # sees the completed handshake
    for _ in range(500):
        await ctx.tick()
        if ctx.get(bus.awready):
            # Keep awvalid=1 for one more tick so the handshake completes.
            await ctx.tick()
            ctx.set(bus.awvalid, 0)
            break
    else:
        raise TimeoutError("AXI4 write: timed out waiting for awready")

    # Send W beats
    for i, data in enumerate(data_list):
        cur_strb = strb_val[i] if isinstance(strb_val, list) else strb_val
        ctx.set(bus.wdata, data)
        ctx.set(bus.wstrb, cur_strb)
        ctx.set(bus.wvalid, 1)
        ctx.set(bus.wlast, 1 if i == awlen else 0)

        for _ in range(500):
            await ctx.tick()
            wr = ctx.get(bus.wready)
            bv = ctx.get(bus.bvalid)
            if wr or bv:
                # wready=1 means beat accepted; bvalid=1 means the SRAM
                # already transitioned to WR_RESP (last beat accepted)
                break
        else:
            raise TimeoutError(f"AXI4 write: timed out waiting for wready on beat {i}")

    ctx.set(bus.wvalid, 0)
    ctx.set(bus.wlast, 0)

    # Check if B response already appeared during W phase
    if ctx.get(bus.bvalid):
        resp = ctx.get(bus.bresp)
        bid = ctx.get(bus.bid) if has_id else 0
        await ctx.tick()
        ctx.set(bus.bready, 0)
        await ctx.tick()
        return resp, bid

    # Wait for B response
    for _ in range(500):
        await ctx.tick()
        if ctx.get(bus.bvalid):
            resp = ctx.get(bus.bresp)
            bid = ctx.get(bus.bid) if has_id else 0
            await ctx.tick()
            ctx.set(bus.bready, 0)
            await ctx.tick()
            return resp, bid
    raise TimeoutError("AXI4 write: timed out waiting for bvalid")


async def axi4_read_burst(ctx, bus, addr, length, burst=AXIBurst.INCR,
                          size=AXISize.B4, arid=0):
    """Perform an AXI4 burst read transaction through a crossbar.

    Same pipeline-aware handshake pattern as the write helper.
    """
    arlen = length - 1
    has_id = "arid" in dict(bus.signature.members)

    # Drive AR channel
    ctx.set(bus.araddr, addr)
    ctx.set(bus.arlen, arlen)
    ctx.set(bus.arsize, size)
    ctx.set(bus.arburst, burst)
    ctx.set(bus.arvalid, 1)
    if has_id:
        ctx.set(bus.arid, arid)

    # Wait for AR handshake with extra tick
    for _ in range(500):
        await ctx.tick()
        if ctx.get(bus.arready):
            await ctx.tick()
            ctx.set(bus.arvalid, 0)
            break
    else:
        raise TimeoutError("AXI4 read: timed out waiting for arready")

    # Collect R beats
    results = []
    ctx.set(bus.rready, 1)
    for beat in range(length):
        for _ in range(500):
            await ctx.tick()
            if ctx.get(bus.rvalid):
                data = ctx.get(bus.rdata)
                resp = ctx.get(bus.rresp)
                rid = ctx.get(bus.rid) if has_id else 0
                rlast = ctx.get(bus.rlast)
                results.append((data, resp, rid, rlast))
                break
        else:
            raise TimeoutError(f"AXI4 read: timed out on beat {beat}")

    await ctx.tick()
    ctx.set(bus.rready, 0)
    await ctx.tick()
    return results


class TestAXI4CrossbarConstruction(unittest.TestCase):
    """Test AXI4Crossbar construction and parameter validation."""

    def test_axi4_crossbar_create(self):
        """Constructor with valid params."""
        xbar = AXI4Crossbar(addr_width=16, data_width=32)
        self.assertEqual(xbar.addr_width, 16)
        self.assertEqual(xbar.data_width, 32)
        self.assertEqual(xbar.id_width, 0)

    def test_axi4_crossbar_create_with_id(self):
        """Constructor with id_width=4."""
        xbar = AXI4Crossbar(addr_width=16, data_width=32, id_width=4)
        self.assertEqual(xbar.addr_width, 16)
        self.assertEqual(xbar.data_width, 32)
        self.assertEqual(xbar.id_width, 4)

    def test_axi4_crossbar_invalid_addr_width(self):
        """Negative address width should raise TypeError."""
        with self.assertRaises(TypeError):
            AXI4Crossbar(addr_width=-1, data_width=32)

    def test_axi4_crossbar_invalid_data_width(self):
        """Data width < 8 should raise ValueError."""
        with self.assertRaises(ValueError):
            AXI4Crossbar(addr_width=16, data_width=4)

    def test_axi4_crossbar_invalid_data_width_not_pow2(self):
        """Non-power-of-2 data width should raise ValueError."""
        with self.assertRaises(ValueError):
            AXI4Crossbar(addr_width=16, data_width=48)

    def test_axi4_crossbar_invalid_id_width(self):
        """Negative ID width should raise TypeError."""
        with self.assertRaises(TypeError):
            AXI4Crossbar(addr_width=16, data_width=32, id_width=-1)


class TestAXI4CrossbarConfiguration(unittest.TestCase):
    """Test AXI4Crossbar add_manager/add_subordinate configuration."""

    def _make_manager(self, addr_width=16, data_width=32, id_width=0):
        return AXI4Interface(addr_width=addr_width, data_width=data_width,
                             id_width=id_width)

    def _make_subordinate(self, addr_width=14, data_width=32, id_width=0):
        iface = AXI4Interface(addr_width=addr_width, data_width=data_width,
                              id_width=id_width)
        iface.memory_map = MemoryMap(addr_width=addr_width, data_width=8)
        return iface

    def test_axi4_crossbar_add_manager(self):
        """Add a manager."""
        xbar = AXI4Crossbar(addr_width=16, data_width=32)
        mgr = self._make_manager()
        xbar.add_manager(mgr, name="cpu")

    def test_axi4_crossbar_add_subordinate(self):
        """Add a subordinate."""
        xbar = AXI4Crossbar(addr_width=16, data_width=32)
        sub = self._make_subordinate()
        xbar.add_subordinate(sub, name="sram", addr=0x0000)

    def test_axi4_crossbar_add_manager_wrong_data_width(self):
        """Manager with wrong data width should raise ValueError."""
        xbar = AXI4Crossbar(addr_width=16, data_width=32)
        mgr = self._make_manager(data_width=64)
        with self.assertRaises(ValueError):
            xbar.add_manager(mgr)

    def test_axi4_crossbar_add_manager_wrong_id_width(self):
        """Manager with wrong ID width should raise ValueError."""
        xbar = AXI4Crossbar(addr_width=16, data_width=32, id_width=4)
        mgr = self._make_manager(id_width=0)
        with self.assertRaises(ValueError):
            xbar.add_manager(mgr)

    def test_axi4_crossbar_add_subordinate_wrong_data_width(self):
        """Subordinate with wrong data width should raise ValueError."""
        xbar = AXI4Crossbar(addr_width=16, data_width=32)
        sub = self._make_subordinate(data_width=64)
        with self.assertRaises(ValueError):
            xbar.add_subordinate(sub, name="bad")

    def test_axi4_crossbar_add_manager_wrong_type(self):
        """Non-AXI4Interface manager should raise TypeError."""
        xbar = AXI4Crossbar(addr_width=16, data_width=32)
        with self.assertRaises(TypeError):
            xbar.add_manager("not a bus")

    def test_axi4_crossbar_add_subordinate_wrong_type(self):
        """Non-AXI4Interface subordinate should raise TypeError."""
        xbar = AXI4Crossbar(addr_width=16, data_width=32)
        with self.assertRaises(TypeError):
            xbar.add_subordinate("not a bus", name="bad")


class TestAXI4CrossbarElaboration(unittest.TestCase):
    """Test AXI4Crossbar RTLIL elaboration."""

    def _make_manager(self, addr_width=16, data_width=32, id_width=0):
        return AXI4Interface(addr_width=addr_width, data_width=data_width,
                             id_width=id_width)

    def _make_subordinate(self, addr_width=14, data_width=32, id_width=0):
        iface = AXI4Interface(addr_width=addr_width, data_width=data_width,
                              id_width=id_width)
        iface.memory_map = MemoryMap(addr_width=addr_width, data_width=8)
        return iface

    def test_axi4_crossbar_elaborate_1x1(self):
        """Elaborate 1 manager × 1 subordinate crossbar."""
        xbar = AXI4Crossbar(addr_width=16, data_width=32)
        m = self._make_manager()
        s = self._make_subordinate()
        xbar.add_manager(m, name="cpu")
        xbar.add_subordinate(s, name="sram", addr=0x0000)
        from amaranth.back.rtlil import convert
        rtlil = convert(xbar)
        self.assertGreater(len(rtlil), 0)

    def test_axi4_crossbar_elaborate_2x2(self):
        """Elaborate 2 managers × 2 subordinates crossbar."""
        xbar = AXI4Crossbar(addr_width=16, data_width=32)
        m1 = self._make_manager()
        m2 = self._make_manager()
        s1 = self._make_subordinate()
        s2 = self._make_subordinate()
        xbar.add_manager(m1, name="cpu")
        xbar.add_manager(m2, name="dma")
        xbar.add_subordinate(s1, name="sram0", addr=0x0000)
        xbar.add_subordinate(s2, name="sram1", addr=0x4000)
        from amaranth.back.rtlil import convert
        rtlil = convert(xbar)
        self.assertGreater(len(rtlil), 0)

    def test_axi4_crossbar_elaborate_with_id(self):
        """Elaborate crossbar with id_width=4."""
        xbar = AXI4Crossbar(addr_width=16, data_width=32, id_width=4)
        m = self._make_manager(id_width=4)
        s = self._make_subordinate(id_width=4)
        xbar.add_manager(m, name="cpu")
        xbar.add_subordinate(s, name="sram", addr=0x0000)
        from amaranth.back.rtlil import convert
        rtlil = convert(xbar)
        self.assertGreater(len(rtlil), 0)

    def test_axi4_crossbar_cannot_add_after_elaborate(self):
        """Adding managers/subordinates after elaborate() should raise RuntimeError."""
        xbar = AXI4Crossbar(addr_width=16, data_width=32)
        m = self._make_manager()
        s = self._make_subordinate()
        xbar.add_manager(m, name="cpu")
        xbar.add_subordinate(s, name="sram", addr=0x0000)
        from amaranth.back.rtlil import convert
        convert(xbar)
        m2 = self._make_manager()
        with self.assertRaises(RuntimeError):
            xbar.add_manager(m2, name="dma")
        s2 = self._make_subordinate()
        with self.assertRaises(RuntimeError):
            xbar.add_subordinate(s2, name="uart", addr=0x4000)


class TestAXI4CrossbarSim(unittest.TestCase):
    """Simulation tests for AXI4Crossbar."""

    def test_axi4_crossbar_sim_1x1(self):
        """1 manager, 1 subordinate (AXI4 SRAM). Write a 4-beat burst, read back, verify."""
        sram = AXI4SRAM(size=1024, data_width=32)

        # Build a wrapper module that contains the crossbar + SRAM
        from amaranth import Module
        from amaranth.lib import wiring

        class Top(wiring.Component):
            def __init__(self):
                self._sram = AXI4SRAM(size=1024, data_width=32)
                self._xbar = AXI4Crossbar(addr_width=16, data_width=32)
                self._mgr = AXI4Interface(addr_width=16, data_width=32,
                                          path=["mgr"])
                self._xbar.add_manager(self._mgr, name="cpu")
                self._xbar.add_subordinate(self._sram.bus, name="sram", addr=0x0000)
                super().__init__({})

            @property
            def mgr(self):
                return self._mgr

            def elaborate(self, platform):
                m = Module()
                m.submodules.xbar = self._xbar
                m.submodules.sram = self._sram
                return m

        dut = Top()

        async def testbench(ctx):
            bus = dut.mgr
            write_data = [0x11111111, 0x22222222, 0x33333333, 0x44444444]

            # 4-beat INCR write starting at address 0x00
            resp, _ = await axi4_write_burst(ctx, bus, 0x00, write_data,
                                             burst=AXIBurst.INCR, size=AXISize.B4)
            assert resp == AXIResp.OKAY, f"Write resp: {resp}"

            # 4-beat INCR read starting at address 0x00
            results = await axi4_read_burst(ctx, bus, 0x00, 4,
                                            burst=AXIBurst.INCR, size=AXISize.B4)
            for i, (data, resp, _, rlast) in enumerate(results):
                assert data == write_data[i], \
                    f"Beat {i}: expected {write_data[i]:#010x}, got {data:#010x}"
                assert resp == AXIResp.OKAY
            assert results[-1][3] == 1, "Expected rlast=1 on last beat"

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_axi4_crossbar_1x1.vcd"):
            sim.run()

    def test_axi4_crossbar_sim_2x2(self):
        """2 managers, 2 subordinates (2 AXI4 SRAMs). Cross-routing verification."""
        from amaranth import Module
        from amaranth.lib import wiring

        class Top(wiring.Component):
            def __init__(self):
                self._sram0 = AXI4SRAM(size=1024, data_width=32)
                self._sram1 = AXI4SRAM(size=1024, data_width=32)
                self._xbar = AXI4Crossbar(addr_width=16, data_width=32)
                self._mgr0 = AXI4Interface(addr_width=16, data_width=32,
                                           path=["mgr0"])
                self._mgr1 = AXI4Interface(addr_width=16, data_width=32,
                                           path=["mgr1"])
                self._xbar.add_manager(self._mgr0, name="cpu")
                self._xbar.add_manager(self._mgr1, name="dma")
                self._xbar.add_subordinate(self._sram0.bus, name="sram0", addr=0x0000)
                self._xbar.add_subordinate(self._sram1.bus, name="sram1", addr=0x0400)
                super().__init__({})

            @property
            def mgr0(self):
                return self._mgr0

            @property
            def mgr1(self):
                return self._mgr1

            def elaborate(self, platform):
                m = Module()
                m.submodules.xbar = self._xbar
                m.submodules.sram0 = self._sram0
                m.submodules.sram1 = self._sram1
                return m

        dut = Top()

        async def testbench(ctx):
            bus0 = dut.mgr0
            bus1 = dut.mgr1

            # Manager 0 writes to SRAM 0 (addr 0x0000)
            resp, _ = await axi4_write_burst(ctx, bus0, 0x0000, [0xAAAAAAAA])
            assert resp == AXIResp.OKAY, f"M0 write to SRAM0 resp: {resp}"

            # Manager 1 writes to SRAM 1 (addr 0x0400)
            resp, _ = await axi4_write_burst(ctx, bus1, 0x0400, [0xBBBBBBBB])
            assert resp == AXIResp.OKAY, f"M1 write to SRAM1 resp: {resp}"

            # Manager 0 reads back from SRAM 0
            results = await axi4_read_burst(ctx, bus0, 0x0000, 1)
            data, resp, _, _ = results[0]
            assert data == 0xAAAAAAAA, \
                f"M0 read SRAM0: expected 0xAAAAAAAA, got {data:#010x}"

            # Manager 1 reads back from SRAM 1
            results = await axi4_read_burst(ctx, bus1, 0x0400, 1)
            data, resp, _, _ = results[0]
            assert data == 0xBBBBBBBB, \
                f"M1 read SRAM1: expected 0xBBBBBBBB, got {data:#010x}"

            # Cross-read: Manager 0 reads from SRAM 1
            results = await axi4_read_burst(ctx, bus0, 0x0400, 1)
            data, resp, _, _ = results[0]
            assert data == 0xBBBBBBBB, \
                f"M0 read SRAM1: expected 0xBBBBBBBB, got {data:#010x}"

            # Cross-read: Manager 1 reads from SRAM 0
            results = await axi4_read_burst(ctx, bus1, 0x0000, 1)
            data, resp, _, _ = results[0]
            assert data == 0xAAAAAAAA, \
                f"M1 read SRAM0: expected 0xAAAAAAAA, got {data:#010x}"

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_axi4_crossbar_2x2.vcd"):
            sim.run()


if __name__ == "__main__":
    unittest.main()
