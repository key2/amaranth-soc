# amaranth: UnusedElaboratable=no

"""Tests for MSIInterruptController and MSIController."""

import unittest
from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.sim import Simulator

from amaranth_soc.periph.intc import MSIInterruptController
from amaranth_soc.periph.msi import MSIController


# ===========================================================================
# MSIInterruptController construction tests
# ===========================================================================

class TestMSIInterruptControllerCreate(unittest.TestCase):
    """Test MSIInterruptController construction."""

    def test_intc_create(self):
        """Constructor validation — default parameters."""
        dut = MSIInterruptController(n_sources=4)
        self.assertEqual(dut.n_sources, 4)
        self.assertFalse(dut.edge_triggered)
        self.assertFalse(dut.priority)

    def test_intc_create_edge(self):
        """Constructor with edge_triggered=True."""
        dut = MSIInterruptController(n_sources=8, edge_triggered=True)
        self.assertEqual(dut.n_sources, 8)
        self.assertTrue(dut.edge_triggered)
        self.assertFalse(dut.priority)

    def test_intc_create_priority(self):
        """Constructor with priority=True."""
        dut = MSIInterruptController(n_sources=4, priority=True)
        self.assertEqual(dut.n_sources, 4)
        self.assertFalse(dut.edge_triggered)
        self.assertTrue(dut.priority)

    def test_intc_create_all_options(self):
        """Constructor with all options enabled."""
        dut = MSIInterruptController(n_sources=16, edge_triggered=True, priority=True)
        self.assertEqual(dut.n_sources, 16)
        self.assertTrue(dut.edge_triggered)
        self.assertTrue(dut.priority)

    def test_intc_create_invalid_n_sources(self):
        """Constructor rejects invalid n_sources."""
        with self.assertRaises(ValueError):
            MSIInterruptController(n_sources=0)
        with self.assertRaises(ValueError):
            MSIInterruptController(n_sources=-1)
        with self.assertRaises(ValueError):
            MSIInterruptController(n_sources="foo")


# ===========================================================================
# MSIInterruptController simulation tests
# ===========================================================================

class TestMSIInterruptControllerSimLevel(unittest.TestCase):
    """Simulation tests for level-sensitive MSIInterruptController."""

    def test_intc_sim_level_basic(self):
        """Assert source 2, verify irq=1, irq_vector=2, irq_valid=1.
        Deassert source 2, verify irq=0."""
        dut = MSIInterruptController(n_sources=4, edge_triggered=False)

        async def testbench(ctx):
            # Enable all sources
            ctx.set(dut.enable, 0b1111)
            await ctx.tick()

            # Assert source 2
            ctx.set(dut.sources, 0b0100)
            await ctx.tick()

            # Check outputs (combinational in level mode)
            self.assertEqual(ctx.get(dut.irq), 1)
            self.assertEqual(ctx.get(dut.irq_vector), 2)
            self.assertEqual(ctx.get(dut.irq_valid), 1)
            self.assertEqual(ctx.get(dut.pending), 0b0100)

            # Deassert source 2
            ctx.set(dut.sources, 0b0000)
            await ctx.tick()

            self.assertEqual(ctx.get(dut.irq), 0)
            self.assertEqual(ctx.get(dut.irq_valid), 0)
            self.assertEqual(ctx.get(dut.pending), 0b0000)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_intc_level_basic.vcd"):
            sim.run()

    def test_intc_sim_level_mask(self):
        """Assert source 2 but disable it in enable mask. Verify irq=0.
        Enable it, verify irq=1."""
        dut = MSIInterruptController(n_sources=4, edge_triggered=False)

        async def testbench(ctx):
            # Enable all except source 2
            ctx.set(dut.enable, 0b1011)
            ctx.set(dut.sources, 0b0100)
            await ctx.tick()

            # Source 2 is masked out
            self.assertEqual(ctx.get(dut.irq), 0)
            self.assertEqual(ctx.get(dut.irq_valid), 0)
            self.assertEqual(ctx.get(dut.pending), 0b0000)

            # Now enable source 2
            ctx.set(dut.enable, 0b1111)
            await ctx.tick()

            self.assertEqual(ctx.get(dut.irq), 1)
            self.assertEqual(ctx.get(dut.irq_valid), 1)
            self.assertEqual(ctx.get(dut.irq_vector), 2)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_intc_level_mask.vcd"):
            sim.run()


class TestMSIInterruptControllerSimEdge(unittest.TestCase):
    """Simulation tests for edge-triggered MSIInterruptController."""

    def test_intc_sim_edge_basic(self):
        """Pulse source 1. Verify pending[1]=1, irq=1.
        Assert irq_ready. Verify pending[1] cleared."""
        dut = MSIInterruptController(n_sources=4, edge_triggered=True)

        async def testbench(ctx):
            # Enable all sources
            ctx.set(dut.enable, 0b1111)
            await ctx.tick()

            # Assert source 1 (rising edge)
            ctx.set(dut.sources, 0b0010)
            await ctx.tick()
            # After one clock, the edge is detected and pending is set
            await ctx.tick()

            self.assertEqual(ctx.get(dut.pending) & 0b0010, 0b0010,
                             f"pending={ctx.get(dut.pending):#06b}")
            self.assertEqual(ctx.get(dut.irq), 1)
            self.assertEqual(ctx.get(dut.irq_valid), 1)
            self.assertEqual(ctx.get(dut.irq_vector), 1)

            # Deassert source (pending should remain latched)
            ctx.set(dut.sources, 0b0000)
            await ctx.tick()

            self.assertEqual(ctx.get(dut.pending) & 0b0010, 0b0010,
                             "Pending should remain latched after source deasserted")
            self.assertEqual(ctx.get(dut.irq), 1)

            # Acknowledge via irq_ready
            ctx.set(dut.irq_ready, 1)
            await ctx.tick()
            ctx.set(dut.irq_ready, 0)
            await ctx.tick()

            self.assertEqual(ctx.get(dut.pending) & 0b0010, 0b0000,
                             "Pending should be cleared after acknowledge")
            self.assertEqual(ctx.get(dut.irq), 0)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_intc_edge_basic.vcd"):
            sim.run()

    def test_intc_sim_edge_clear_strobe(self):
        """Test explicit clear strobe for edge-triggered interrupts."""
        dut = MSIInterruptController(n_sources=4, edge_triggered=True)

        async def testbench(ctx):
            ctx.set(dut.enable, 0b1111)
            await ctx.tick()

            # Trigger source 0
            ctx.set(dut.sources, 0b0001)
            await ctx.tick()
            await ctx.tick()

            self.assertEqual(ctx.get(dut.pending) & 0b0001, 0b0001)

            # Clear via explicit clear strobe
            ctx.set(dut.sources, 0b0000)
            ctx.set(dut.clear, 0b0001)
            await ctx.tick()
            ctx.set(dut.clear, 0b0000)
            await ctx.tick()

            self.assertEqual(ctx.get(dut.pending) & 0b0001, 0b0000,
                             "Pending should be cleared by explicit clear strobe")

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_intc_edge_clear.vcd"):
            sim.run()


class TestMSIInterruptControllerSimPriority(unittest.TestCase):
    """Simulation tests for priority-encoded MSIInterruptController."""

    def test_intc_sim_priority(self):
        """Assert sources 1 and 3 simultaneously. Verify irq_vector=1
        (lowest index). Acknowledge it. Verify irq_vector=3."""
        dut = MSIInterruptController(n_sources=4, edge_triggered=True, priority=True)

        async def testbench(ctx):
            # Enable all sources
            ctx.set(dut.enable, 0b1111)
            await ctx.tick()

            # Assert sources 1 and 3 simultaneously
            ctx.set(dut.sources, 0b1010)
            await ctx.tick()
            await ctx.tick()

            # Both should be pending
            pending = ctx.get(dut.pending)
            self.assertTrue(pending & 0b0010, f"Source 1 should be pending, got {pending:#06b}")
            self.assertTrue(pending & 0b1000, f"Source 3 should be pending, got {pending:#06b}")

            # Priority should select lowest index = 1
            self.assertEqual(ctx.get(dut.irq_vector), 1,
                             f"Expected vector 1, got {ctx.get(dut.irq_vector)}")
            self.assertEqual(ctx.get(dut.irq_valid), 1)

            # Deassert sources (pending remains latched)
            ctx.set(dut.sources, 0b0000)
            await ctx.tick()

            # Acknowledge vector 1
            ctx.set(dut.irq_ready, 1)
            await ctx.tick()
            ctx.set(dut.irq_ready, 0)
            await ctx.tick()

            # Now only source 3 should be pending
            pending = ctx.get(dut.pending)
            self.assertEqual(pending & 0b0010, 0b0000,
                             "Source 1 should be cleared after ack")
            self.assertTrue(pending & 0b1000,
                            f"Source 3 should still be pending, got {pending:#06b}")
            self.assertEqual(ctx.get(dut.irq_vector), 3,
                             f"Expected vector 3, got {ctx.get(dut.irq_vector)}")
            self.assertEqual(ctx.get(dut.irq_valid), 1)

            # Acknowledge vector 3
            ctx.set(dut.irq_ready, 1)
            await ctx.tick()
            ctx.set(dut.irq_ready, 0)
            await ctx.tick()

            # All cleared
            self.assertEqual(ctx.get(dut.pending), 0)
            self.assertEqual(ctx.get(dut.irq), 0)
            self.assertEqual(ctx.get(dut.irq_valid), 0)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_intc_priority.vcd"):
            sim.run()


# ===========================================================================
# MSIController construction tests
# ===========================================================================

class TestMSIControllerCreate(unittest.TestCase):
    """Test MSIController construction."""

    def test_msi_create(self):
        """Constructor validation — default parameters."""
        dut = MSIController(n_vectors=4)
        self.assertEqual(dut.n_vectors, 4)
        self.assertEqual(dut.addr_width, 64)
        self.assertEqual(dut.data_width, 32)

    def test_msi_create_custom(self):
        """Constructor with custom parameters."""
        dut = MSIController(n_vectors=16, addr_width=32, data_width=16)
        self.assertEqual(dut.n_vectors, 16)
        self.assertEqual(dut.addr_width, 32)
        self.assertEqual(dut.data_width, 16)

    def test_msi_create_invalid_n_vectors(self):
        """Constructor rejects invalid n_vectors."""
        with self.assertRaises(ValueError):
            MSIController(n_vectors=0)
        with self.assertRaises(ValueError):
            MSIController(n_vectors=-1)

    def test_msi_create_invalid_addr_width(self):
        """Constructor rejects invalid addr_width."""
        with self.assertRaises(ValueError):
            MSIController(n_vectors=4, addr_width=0)

    def test_msi_create_invalid_data_width(self):
        """Constructor rejects invalid data_width."""
        with self.assertRaises(ValueError):
            MSIController(n_vectors=4, data_width=0)


# ===========================================================================
# MSIController simulation tests
# ===========================================================================

class TestMSIControllerSim(unittest.TestCase):
    """Simulation tests for MSIController."""

    def test_msi_sim_basic(self):
        """Configure vector 0 with addr=0x1000, data=0xAB. Trigger source 0.
        Verify msi_addr=0x1000, msi_data=0xAB, msi_valid=1.
        Assert msi_ready. Verify cleared."""
        dut = MSIController(n_vectors=4, addr_width=32, data_width=32)

        async def testbench(ctx):
            # Configure vector 0: addr=0x1000, data=0xAB
            ctx.set(dut.cfg_vector, 0)
            ctx.set(dut.cfg_addr, 0x1000)
            ctx.set(dut.cfg_data, 0xAB)
            ctx.set(dut.cfg_we, 1)
            await ctx.tick()
            ctx.set(dut.cfg_we, 0)
            await ctx.tick()

            # Enable source 0
            ctx.set(dut.enable, 0b0001)
            await ctx.tick()

            # Trigger source 0 (rising edge)
            ctx.set(dut.sources, 0b0001)
            await ctx.tick()
            # Wait for edge detection and pending latch
            await ctx.tick()

            # Verify MSI output
            self.assertEqual(ctx.get(dut.msi_valid), 1,
                             "msi_valid should be 1")
            self.assertEqual(ctx.get(dut.msi_addr), 0x1000,
                             f"Expected addr 0x1000, got {ctx.get(dut.msi_addr):#x}")
            self.assertEqual(ctx.get(dut.msi_data), 0xAB,
                             f"Expected data 0xAB, got {ctx.get(dut.msi_data):#x}")

            # Acknowledge
            ctx.set(dut.sources, 0b0000)
            ctx.set(dut.msi_ready, 1)
            await ctx.tick()
            ctx.set(dut.msi_ready, 0)
            await ctx.tick()

            # Verify cleared
            self.assertEqual(ctx.get(dut.msi_valid), 0,
                             "msi_valid should be 0 after acknowledge")

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_msi_basic.vcd"):
            sim.run()

    def test_msi_sim_multi_vector(self):
        """Configure 2 vectors with different addr/data. Trigger both.
        Verify they are serviced in priority order."""
        dut = MSIController(n_vectors=4, addr_width=32, data_width=32)

        async def testbench(ctx):
            # Configure vector 0: addr=0x1000, data=0xAA
            ctx.set(dut.cfg_vector, 0)
            ctx.set(dut.cfg_addr, 0x1000)
            ctx.set(dut.cfg_data, 0xAA)
            ctx.set(dut.cfg_we, 1)
            await ctx.tick()

            # Configure vector 2: addr=0x2000, data=0xBB
            ctx.set(dut.cfg_vector, 2)
            ctx.set(dut.cfg_addr, 0x2000)
            ctx.set(dut.cfg_data, 0xBB)
            ctx.set(dut.cfg_we, 1)
            await ctx.tick()
            ctx.set(dut.cfg_we, 0)
            await ctx.tick()

            # Enable sources 0 and 2
            ctx.set(dut.enable, 0b0101)
            await ctx.tick()

            # Trigger both sources simultaneously
            ctx.set(dut.sources, 0b0101)
            await ctx.tick()
            # Wait for edge detection
            await ctx.tick()

            # Priority should select vector 0 first
            self.assertEqual(ctx.get(dut.msi_valid), 1)
            self.assertEqual(ctx.get(dut.msi_addr), 0x1000,
                             f"Expected addr 0x1000 (vec 0), got {ctx.get(dut.msi_addr):#x}")
            self.assertEqual(ctx.get(dut.msi_data), 0xAA,
                             f"Expected data 0xAA (vec 0), got {ctx.get(dut.msi_data):#x}")

            # Acknowledge vector 0
            ctx.set(dut.sources, 0b0000)
            ctx.set(dut.msi_ready, 1)
            await ctx.tick()
            ctx.set(dut.msi_ready, 0)
            await ctx.tick()

            # Now vector 2 should be presented
            self.assertEqual(ctx.get(dut.msi_valid), 1,
                             "msi_valid should still be 1 for vector 2")
            self.assertEqual(ctx.get(dut.msi_addr), 0x2000,
                             f"Expected addr 0x2000 (vec 2), got {ctx.get(dut.msi_addr):#x}")
            self.assertEqual(ctx.get(dut.msi_data), 0xBB,
                             f"Expected data 0xBB (vec 2), got {ctx.get(dut.msi_data):#x}")

            # Acknowledge vector 2
            ctx.set(dut.msi_ready, 1)
            await ctx.tick()
            ctx.set(dut.msi_ready, 0)
            await ctx.tick()

            # All cleared
            self.assertEqual(ctx.get(dut.msi_valid), 0,
                             "msi_valid should be 0 after all acknowledged")

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_msi_multi_vector.vcd"):
            sim.run()


if __name__ == "__main__":
    unittest.main()
