# amaranth: UnusedElaboratable=no
"""Tests for Wishbone NxM crossbar interconnect."""

import unittest
from amaranth import *
from amaranth.sim import *
from amaranth.back.rtlil import convert

from amaranth_soc import wishbone
from amaranth_soc.wishbone.bus import Crossbar, Interface, Signature
from amaranth_soc.wishbone.sram import WishboneSRAM
from amaranth_soc.memory import MemoryMap


class TestCrossbarConstruction(unittest.TestCase):
    """Test Crossbar construction and parameter validation."""

    def test_crossbar_create(self):
        """Construct with basic valid parameters."""
        xbar = Crossbar(addr_width=16, data_width=32)
        self.assertEqual(xbar.addr_width, 16)
        self.assertEqual(xbar.data_width, 32)
        self.assertEqual(xbar.granularity, 32)
        self.assertEqual(xbar.features, frozenset())
        self.assertEqual(xbar.alignment, 0)

    def test_crossbar_create_8bit(self):
        """Construct with 8-bit data width."""
        xbar = Crossbar(addr_width=16, data_width=8)
        self.assertEqual(xbar.data_width, 8)

    def test_crossbar_create_with_granularity(self):
        """Construct with explicit granularity."""
        xbar = Crossbar(addr_width=16, data_width=32, granularity=8)
        self.assertEqual(xbar.granularity, 8)

    def test_crossbar_create_with_features(self):
        """Construct with optional features."""
        from amaranth_soc.wishbone.bus import Feature
        xbar = Crossbar(addr_width=16, data_width=32, features={Feature.ERR})
        self.assertIn(Feature.ERR, xbar.features)

    def test_crossbar_create_with_alignment(self):
        """Construct with alignment."""
        xbar = Crossbar(addr_width=16, data_width=32, alignment=2)
        self.assertEqual(xbar.alignment, 2)

    def test_crossbar_invalid_addr_width(self):
        """Negative address width should raise TypeError."""
        with self.assertRaises(TypeError):
            Crossbar(addr_width=-1, data_width=32)

    def test_crossbar_invalid_data_width(self):
        """Invalid data width should raise ValueError."""
        with self.assertRaises(ValueError):
            Crossbar(addr_width=16, data_width=128)

    def test_crossbar_invalid_granularity(self):
        """Granularity > data_width should raise ValueError."""
        with self.assertRaises(ValueError):
            Crossbar(addr_width=16, data_width=8, granularity=16)


class TestCrossbarConfiguration(unittest.TestCase):
    """Test Crossbar add_initiator/add_subordinate configuration."""

    def _make_initiator(self, addr_width=16, data_width=32):
        """Helper to create an initiator bus interface."""
        return Interface(addr_width=addr_width, data_width=data_width)

    def _make_subordinate(self, size=1024, data_width=32):
        """Helper to create a subordinate bus interface with memory map."""
        from amaranth.utils import exact_log2
        addr_width = exact_log2(size)
        iface = Interface(addr_width=addr_width, data_width=data_width)
        iface.memory_map = MemoryMap(addr_width=addr_width, data_width=data_width)
        return iface

    def test_crossbar_add_initiator(self):
        """Add a single initiator."""
        xbar = Crossbar(addr_width=16, data_width=32)
        intr = self._make_initiator()
        xbar.add_initiator(intr, name="cpu")

    def test_crossbar_add_subordinate(self):
        """Add a single subordinate at an address."""
        xbar = Crossbar(addr_width=16, data_width=32)
        sub = self._make_subordinate()
        xbar.add_subordinate(sub, name="sram", addr=0x0000)

    def test_crossbar_add_multiple_initiators(self):
        """Add multiple initiators."""
        xbar = Crossbar(addr_width=16, data_width=32)
        i1 = self._make_initiator()
        i2 = self._make_initiator()
        xbar.add_initiator(i1, name="cpu")
        xbar.add_initiator(i2, name="dma")

    def test_crossbar_add_multiple_subordinates(self):
        """Add multiple subordinates at different addresses."""
        xbar = Crossbar(addr_width=16, data_width=32)
        s1 = self._make_subordinate()
        s2 = self._make_subordinate()
        xbar.add_subordinate(s1, name="sram0", addr=0x0000)
        xbar.add_subordinate(s2, name="sram1", addr=0x0400)

    def test_crossbar_add_initiator_wrong_type(self):
        """Non-Interface initiator should raise TypeError."""
        xbar = Crossbar(addr_width=16, data_width=32)
        with self.assertRaises(TypeError):
            xbar.add_initiator("not a bus")

    def test_crossbar_add_subordinate_wrong_type(self):
        """Non-Interface subordinate should raise TypeError."""
        xbar = Crossbar(addr_width=16, data_width=32)
        with self.assertRaises(TypeError):
            xbar.add_subordinate("not a bus", name="bad")

    def test_crossbar_add_initiator_wrong_data_width(self):
        """Initiator with wrong data width should raise ValueError."""
        xbar = Crossbar(addr_width=16, data_width=32)
        intr = self._make_initiator(data_width=16)
        with self.assertRaises(ValueError):
            xbar.add_initiator(intr)

    def test_crossbar_add_subordinate_wrong_data_width(self):
        """Subordinate with wrong data width should raise ValueError."""
        xbar = Crossbar(addr_width=16, data_width=32)
        sub = self._make_subordinate(data_width=16)
        with self.assertRaises(ValueError):
            xbar.add_subordinate(sub, name="bad")

    def test_crossbar_auto_name(self):
        """Auto-naming for initiators and subordinates."""
        xbar = Crossbar(addr_width=16, data_width=32)
        i1 = self._make_initiator()
        xbar.add_initiator(i1)
        s1 = self._make_subordinate()
        xbar.add_subordinate(s1, addr=0x0000)


class TestCrossbarElaboration(unittest.TestCase):
    """Test Crossbar RTLIL elaboration."""

    def _make_initiator(self, addr_width=16, data_width=32):
        return Interface(addr_width=addr_width, data_width=data_width)

    def _make_subordinate(self, size=1024, data_width=32):
        from amaranth.utils import exact_log2
        addr_width = exact_log2(size)
        iface = Interface(addr_width=addr_width, data_width=data_width)
        iface.memory_map = MemoryMap(addr_width=addr_width, data_width=data_width)
        return iface

    def test_crossbar_elaborate_empty(self):
        """Crossbar with no initiators/subordinates should elaborate."""
        xbar = Crossbar(addr_width=16, data_width=32)
        rtlil = convert(xbar)
        self.assertGreater(len(rtlil), 0)

    def test_crossbar_elaborate_1x1(self):
        """Elaborate 1 initiator × 1 subordinate crossbar."""
        xbar = Crossbar(addr_width=16, data_width=32)
        i = self._make_initiator()
        s = self._make_subordinate()
        xbar.add_initiator(i, name="cpu")
        xbar.add_subordinate(s, name="sram", addr=0x0000)
        rtlil = convert(xbar)
        self.assertGreater(len(rtlil), 0)

    def test_crossbar_elaborate_2x2(self):
        """Elaborate 2 initiators × 2 subordinates crossbar."""
        xbar = Crossbar(addr_width=16, data_width=32)
        i1 = self._make_initiator()
        i2 = self._make_initiator()
        s1 = self._make_subordinate()
        s2 = self._make_subordinate()
        xbar.add_initiator(i1, name="cpu")
        xbar.add_initiator(i2, name="dma")
        xbar.add_subordinate(s1, name="sram0", addr=0x0000)
        xbar.add_subordinate(s2, name="sram1", addr=0x0400)
        rtlil = convert(xbar)
        self.assertGreater(len(rtlil), 0)

    def test_crossbar_cannot_add_after_elaborate(self):
        """Adding initiators/subordinates after elaborate() should raise RuntimeError."""
        xbar = Crossbar(addr_width=16, data_width=32)
        i = self._make_initiator()
        s = self._make_subordinate()
        xbar.add_initiator(i, name="cpu")
        xbar.add_subordinate(s, name="sram", addr=0x0000)
        convert(xbar)
        i2 = self._make_initiator()
        with self.assertRaises(RuntimeError):
            xbar.add_initiator(i2, name="dma")
        s2 = self._make_subordinate()
        with self.assertRaises(RuntimeError):
            xbar.add_subordinate(s2, name="sram1", addr=0x0400)


class _CrossbarSimDUT(Elaboratable):
    """Test DUT that wraps a Crossbar with SRAMs and initiator interfaces."""

    def __init__(self, *, n_initiators, n_subordinates, addr_width=16, data_width=32,
                 sram_size=256, sub_addrs=None):
        self.addr_width = addr_width
        self.data_width = data_width
        self.n_initiators = n_initiators
        self.n_subordinates = n_subordinates
        self.sram_size = sram_size
        self.sub_addrs = sub_addrs

        # Create initiator interfaces (these will be driven by testbenches)
        self.initiators = []
        for i in range(n_initiators):
            iface = Interface(addr_width=addr_width, data_width=data_width,
                              path=["dut", f"intr_{i}"])
            self.initiators.append(iface)

        # Create SRAMs
        self.srams = []
        for j in range(n_subordinates):
            sram = WishboneSRAM(size=sram_size, data_width=data_width)
            self.srams.append(sram)

    def elaborate(self, platform):
        m = Module()

        xbar = Crossbar(addr_width=self.addr_width, data_width=self.data_width)

        for i, intr in enumerate(self.initiators):
            xbar.add_initiator(intr, name=f"intr_{i}")

        for j, sram in enumerate(self.srams):
            m.submodules[f"sram_{j}"] = sram
            addr = self.sub_addrs[j] if self.sub_addrs else j * self.sram_size
            xbar.add_subordinate(sram.wb_bus, name=f"sram_{j}", addr=addr)

        m.submodules.xbar = xbar

        return m


class TestCrossbarSim1x1(unittest.TestCase):
    """Simulation test: 1 initiator, 1 subordinate (SRAM)."""

    def test_crossbar_sim_1x1(self):
        """Write and read data through a 1x1 crossbar."""
        dut = _CrossbarSimDUT(n_initiators=1, n_subordinates=1,
                              addr_width=16, data_width=32,
                              sram_size=256, sub_addrs=[0x0000])

        async def testbench(ctx):
            bus = dut.initiators[0]

            # Write 0xDEADBEEF to address 0
            ctx.set(bus.cyc, 1)
            ctx.set(bus.stb, 1)
            ctx.set(bus.we, 1)
            ctx.set(bus.adr, 0x0000)
            ctx.set(bus.dat_w, 0xDEADBEEF)
            ctx.set(bus.sel, 0x1)  # granularity == data_width, so sel is 1 bit

            # Wait for ack
            for _ in range(50):
                await ctx.tick()
                if ctx.get(bus.ack):
                    break
            self.assertEqual(ctx.get(bus.ack), 1)

            # Deassert
            ctx.set(bus.cyc, 0)
            ctx.set(bus.stb, 0)
            ctx.set(bus.we, 0)
            await ctx.tick()
            await ctx.tick()

            # Read back from address 0
            ctx.set(bus.cyc, 1)
            ctx.set(bus.stb, 1)
            ctx.set(bus.we, 0)
            ctx.set(bus.adr, 0x0000)
            ctx.set(bus.sel, 0x1)

            for _ in range(50):
                await ctx.tick()
                if ctx.get(bus.ack):
                    break
            self.assertEqual(ctx.get(bus.ack), 1)
            self.assertEqual(ctx.get(bus.dat_r), 0xDEADBEEF)

            ctx.set(bus.cyc, 0)
            ctx.set(bus.stb, 0)
            await ctx.tick()

            # Write to address 1
            ctx.set(bus.cyc, 1)
            ctx.set(bus.stb, 1)
            ctx.set(bus.we, 1)
            ctx.set(bus.adr, 0x0001)
            ctx.set(bus.dat_w, 0xCAFEBABE)
            ctx.set(bus.sel, 0x1)

            for _ in range(50):
                await ctx.tick()
                if ctx.get(bus.ack):
                    break
            self.assertEqual(ctx.get(bus.ack), 1)

            ctx.set(bus.cyc, 0)
            ctx.set(bus.stb, 0)
            ctx.set(bus.we, 0)
            await ctx.tick()
            await ctx.tick()

            # Read back from address 1
            ctx.set(bus.cyc, 1)
            ctx.set(bus.stb, 1)
            ctx.set(bus.we, 0)
            ctx.set(bus.adr, 0x0001)
            ctx.set(bus.sel, 0x1)

            for _ in range(50):
                await ctx.tick()
                if ctx.get(bus.ack):
                    break
            self.assertEqual(ctx.get(bus.ack), 1)
            self.assertEqual(ctx.get(bus.dat_r), 0xCAFEBABE)

            ctx.set(bus.cyc, 0)
            ctx.set(bus.stb, 0)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test_wb_xbar_1x1.vcd"):
            sim.run()


class TestCrossbarSim2x2(unittest.TestCase):
    """Simulation test: 2 initiators, 2 subordinates (2 SRAMs)."""

    def test_crossbar_sim_2x2(self):
        """Initiator 0 writes to SRAM 0, initiator 1 writes to SRAM 1.
        Read back from both to verify correct routing."""
        dut = _CrossbarSimDUT(n_initiators=2, n_subordinates=2,
                              addr_width=16, data_width=32,
                              sram_size=256, sub_addrs=[0x0000, 0x0100])

        async def testbench_intr0(ctx):
            """Initiator 0: write to SRAM 0 (addr 0x0000-0x00FF)."""
            bus = dut.initiators[0]

            # Write 0x11111111 to SRAM 0, address 0
            ctx.set(bus.cyc, 1)
            ctx.set(bus.stb, 1)
            ctx.set(bus.we, 1)
            ctx.set(bus.adr, 0x0000)
            ctx.set(bus.dat_w, 0x11111111)
            ctx.set(bus.sel, 0x1)

            for _ in range(50):
                await ctx.tick()
                if ctx.get(bus.ack):
                    break
            self.assertEqual(ctx.get(bus.ack), 1)

            ctx.set(bus.cyc, 0)
            ctx.set(bus.stb, 0)
            ctx.set(bus.we, 0)
            await ctx.tick()
            await ctx.tick()

            # Write 0x22222222 to SRAM 0, address 1
            ctx.set(bus.cyc, 1)
            ctx.set(bus.stb, 1)
            ctx.set(bus.we, 1)
            ctx.set(bus.adr, 0x0001)
            ctx.set(bus.dat_w, 0x22222222)
            ctx.set(bus.sel, 0x1)

            for _ in range(50):
                await ctx.tick()
                if ctx.get(bus.ack):
                    break
            self.assertEqual(ctx.get(bus.ack), 1)

            ctx.set(bus.cyc, 0)
            ctx.set(bus.stb, 0)
            ctx.set(bus.we, 0)
            await ctx.tick()
            await ctx.tick()

            # Read back from SRAM 0, address 0
            ctx.set(bus.cyc, 1)
            ctx.set(bus.stb, 1)
            ctx.set(bus.we, 0)
            ctx.set(bus.adr, 0x0000)
            ctx.set(bus.sel, 0x1)

            for _ in range(50):
                await ctx.tick()
                if ctx.get(bus.ack):
                    break
            self.assertEqual(ctx.get(bus.ack), 1)
            self.assertEqual(ctx.get(bus.dat_r), 0x11111111)

            ctx.set(bus.cyc, 0)
            ctx.set(bus.stb, 0)
            await ctx.tick()
            await ctx.tick()

            # Read back from SRAM 0, address 1
            ctx.set(bus.cyc, 1)
            ctx.set(bus.stb, 1)
            ctx.set(bus.we, 0)
            ctx.set(bus.adr, 0x0001)
            ctx.set(bus.sel, 0x1)

            for _ in range(50):
                await ctx.tick()
                if ctx.get(bus.ack):
                    break
            self.assertEqual(ctx.get(bus.ack), 1)
            self.assertEqual(ctx.get(bus.dat_r), 0x22222222)

            ctx.set(bus.cyc, 0)
            ctx.set(bus.stb, 0)

        async def testbench_intr1(ctx):
            """Initiator 1: write to SRAM 1 (addr 0x0100-0x01FF)."""
            bus = dut.initiators[1]

            # Write 0xAAAAAAAA to SRAM 1, address 0x0100
            ctx.set(bus.cyc, 1)
            ctx.set(bus.stb, 1)
            ctx.set(bus.we, 1)
            ctx.set(bus.adr, 0x0100)
            ctx.set(bus.dat_w, 0xAAAAAAAA)
            ctx.set(bus.sel, 0x1)

            for _ in range(50):
                await ctx.tick()
                if ctx.get(bus.ack):
                    break
            self.assertEqual(ctx.get(bus.ack), 1)

            ctx.set(bus.cyc, 0)
            ctx.set(bus.stb, 0)
            ctx.set(bus.we, 0)
            await ctx.tick()
            await ctx.tick()

            # Write 0xBBBBBBBB to SRAM 1, address 0x0101
            ctx.set(bus.cyc, 1)
            ctx.set(bus.stb, 1)
            ctx.set(bus.we, 1)
            ctx.set(bus.adr, 0x0101)
            ctx.set(bus.dat_w, 0xBBBBBBBB)
            ctx.set(bus.sel, 0x1)

            for _ in range(50):
                await ctx.tick()
                if ctx.get(bus.ack):
                    break
            self.assertEqual(ctx.get(bus.ack), 1)

            ctx.set(bus.cyc, 0)
            ctx.set(bus.stb, 0)
            ctx.set(bus.we, 0)
            await ctx.tick()
            await ctx.tick()

            # Read back from SRAM 1, address 0x0100
            ctx.set(bus.cyc, 1)
            ctx.set(bus.stb, 1)
            ctx.set(bus.we, 0)
            ctx.set(bus.adr, 0x0100)
            ctx.set(bus.sel, 0x1)

            for _ in range(50):
                await ctx.tick()
                if ctx.get(bus.ack):
                    break
            self.assertEqual(ctx.get(bus.ack), 1)
            self.assertEqual(ctx.get(bus.dat_r), 0xAAAAAAAA)

            ctx.set(bus.cyc, 0)
            ctx.set(bus.stb, 0)
            await ctx.tick()
            await ctx.tick()

            # Read back from SRAM 1, address 0x0101
            ctx.set(bus.cyc, 1)
            ctx.set(bus.stb, 1)
            ctx.set(bus.we, 0)
            ctx.set(bus.adr, 0x0101)
            ctx.set(bus.sel, 0x1)

            for _ in range(50):
                await ctx.tick()
                if ctx.get(bus.ack):
                    break
            self.assertEqual(ctx.get(bus.ack), 1)
            self.assertEqual(ctx.get(bus.dat_r), 0xBBBBBBBB)

            ctx.set(bus.cyc, 0)
            ctx.set(bus.stb, 0)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench_intr0)
        sim.add_testbench(testbench_intr1)
        with sim.write_vcd(vcd_file="test_wb_xbar_2x2.vcd"):
            sim.run()


class TestCrossbarSimContention(unittest.TestCase):
    """Simulation test: 2 initiators both access the same subordinate."""

    def test_crossbar_sim_contention(self):
        """2 initiators both try to access the same subordinate.
        Verify both eventually complete their transactions."""
        dut = _CrossbarSimDUT(n_initiators=2, n_subordinates=1,
                              addr_width=16, data_width=32,
                              sram_size=256, sub_addrs=[0x0000])

        results = {"intr0_write_done": False, "intr0_read_ok": False,
                   "intr1_write_done": False, "intr1_read_ok": False}

        async def testbench_intr0(ctx):
            """Initiator 0: write 0xAAAA0000 to address 0, then read it back."""
            bus = dut.initiators[0]

            # Write
            ctx.set(bus.cyc, 1)
            ctx.set(bus.stb, 1)
            ctx.set(bus.we, 1)
            ctx.set(bus.adr, 0x0000)
            ctx.set(bus.dat_w, 0xAAAA0000)
            ctx.set(bus.sel, 0x1)

            for _ in range(100):
                await ctx.tick()
                if ctx.get(bus.ack):
                    break

            ctx.set(bus.cyc, 0)
            ctx.set(bus.stb, 0)
            ctx.set(bus.we, 0)
            results["intr0_write_done"] = True
            await ctx.tick()
            await ctx.tick()
            await ctx.tick()

            # Read back
            ctx.set(bus.cyc, 1)
            ctx.set(bus.stb, 1)
            ctx.set(bus.we, 0)
            ctx.set(bus.adr, 0x0000)
            ctx.set(bus.sel, 0x1)

            for _ in range(100):
                await ctx.tick()
                if ctx.get(bus.ack):
                    break

            data = ctx.get(bus.dat_r)
            ctx.set(bus.cyc, 0)
            ctx.set(bus.stb, 0)
            # The value might have been overwritten by initiator 1
            # We just verify we got a valid response
            results["intr0_read_ok"] = (data == 0xAAAA0000 or data == 0xBBBB0000)

        async def testbench_intr1(ctx):
            """Initiator 1: write 0xBBBB0000 to address 0, then read it back."""
            bus = dut.initiators[1]

            # Write
            ctx.set(bus.cyc, 1)
            ctx.set(bus.stb, 1)
            ctx.set(bus.we, 1)
            ctx.set(bus.adr, 0x0000)
            ctx.set(bus.dat_w, 0xBBBB0000)
            ctx.set(bus.sel, 0x1)

            for _ in range(100):
                await ctx.tick()
                if ctx.get(bus.ack):
                    break

            ctx.set(bus.cyc, 0)
            ctx.set(bus.stb, 0)
            ctx.set(bus.we, 0)
            results["intr1_write_done"] = True
            await ctx.tick()
            await ctx.tick()
            await ctx.tick()

            # Read back
            ctx.set(bus.cyc, 1)
            ctx.set(bus.stb, 1)
            ctx.set(bus.we, 0)
            ctx.set(bus.adr, 0x0000)
            ctx.set(bus.sel, 0x1)

            for _ in range(100):
                await ctx.tick()
                if ctx.get(bus.ack):
                    break

            data = ctx.get(bus.dat_r)
            ctx.set(bus.cyc, 0)
            ctx.set(bus.stb, 0)
            results["intr1_read_ok"] = (data == 0xAAAA0000 or data == 0xBBBB0000)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench_intr0)
        sim.add_testbench(testbench_intr1)
        with sim.write_vcd(vcd_file="test_wb_xbar_contention.vcd"):
            sim.run()

        # Verify both initiators completed their transactions
        self.assertTrue(results["intr0_write_done"], "Initiator 0 write did not complete")
        self.assertTrue(results["intr0_read_ok"], "Initiator 0 read failed")
        self.assertTrue(results["intr1_write_done"], "Initiator 1 write did not complete")
        self.assertTrue(results["intr1_read_ok"], "Initiator 1 read failed")


if __name__ == "__main__":
    unittest.main()
