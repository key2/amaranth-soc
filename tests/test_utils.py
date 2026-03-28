"""Tests for amaranth_soc.utils: WaitTimer and add_reset_domain."""

import unittest
from amaranth import *
from amaranth.sim import Simulator

from amaranth_soc.utils.wait_timer import WaitTimer
from amaranth_soc.utils.reset_inserter import add_reset_domain


class TestWaitTimer(unittest.TestCase):
    """Tests for WaitTimer."""

    def _run_sim(self, dut, testbench, *, vcd_name="test_wait_timer.vcd"):
        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(f"tests/{vcd_name}"):
            sim.run()

    def test_basic_timeout(self):
        """done asserts after exactly N cycles with wait held high."""
        dut = WaitTimer(cycles=10)

        async def testbench(ctx):
            ctx.set(dut.wait, 1)
            for i in range(10):
                await ctx.tick()
                done = ctx.get(dut.done)
                if i < 9:
                    assert done == 0, f"done asserted early at cycle {i + 1}"
            assert ctx.get(dut.done) == 1, "done not asserted after 10 cycles"

        self._run_sim(dut, testbench, vcd_name="test_wait_timer_basic.vcd")

    def test_done_stays_high(self):
        """done remains asserted while wait stays high after timeout."""
        dut = WaitTimer(cycles=5)

        async def testbench(ctx):
            ctx.set(dut.wait, 1)
            for _ in range(5):
                await ctx.tick()
            assert ctx.get(dut.done) == 1
            # Should stay high
            for _ in range(5):
                await ctx.tick()
                assert ctx.get(dut.done) == 1

        self._run_sim(dut, testbench, vcd_name="test_wait_timer_stays.vcd")

    def test_reset_on_deassert(self):
        """Deasserting wait mid-count resets counter."""
        dut = WaitTimer(cycles=10)

        async def testbench(ctx):
            ctx.set(dut.wait, 1)
            for _ in range(5):
                await ctx.tick()
            assert ctx.get(dut.done) == 0
            # Deassert
            ctx.set(dut.wait, 0)
            await ctx.tick()
            await ctx.tick()
            # Re-assert: needs full 10 cycles again
            ctx.set(dut.wait, 1)
            for i in range(10):
                await ctx.tick()
                if i < 9:
                    assert ctx.get(dut.done) == 0
            assert ctx.get(dut.done) == 1

        self._run_sim(dut, testbench, vcd_name="test_wait_timer_reset.vcd")

    def test_cycles_1(self):
        """Edge case: cycles=1 asserts done after single tick."""
        dut = WaitTimer(cycles=1)

        async def testbench(ctx):
            ctx.set(dut.wait, 1)
            await ctx.tick()
            assert ctx.get(dut.done) == 1

        self._run_sim(dut, testbench, vcd_name="test_wait_timer_1.vcd")

    def test_cycles_0_raises(self):
        """cycles=0 raises ValueError."""
        with self.assertRaises(ValueError):
            WaitTimer(cycles=0)

    def test_wait_low_done_stays_low(self):
        """done stays low when wait is never asserted."""
        dut = WaitTimer(cycles=5)

        async def testbench(ctx):
            for _ in range(10):
                await ctx.tick()
                assert ctx.get(dut.done) == 0

        self._run_sim(dut, testbench, vcd_name="test_wait_timer_low.vcd")


class TestResetInserter(unittest.TestCase):
    """Tests for add_reset_domain."""

    def test_counter_resets(self):
        """Counter in reset domain resets when reset signal is asserted."""

        class DUT(Elaboratable):
            def __init__(self):
                self.reset = Signal()
                self.counter = Signal(8)

            def elaborate(self, platform):
                m = Module()
                domain = add_reset_domain(m, self.reset)
                m.d[domain] += self.counter.eq(self.counter + 1)
                return m

        dut = DUT()

        async def testbench(ctx):
            # Let counter run for 5 cycles
            for _ in range(5):
                await ctx.tick()
            val = ctx.get(dut.counter)
            assert val == 5, f"Expected 5, got {val}"

            # Assert reset
            ctx.set(dut.reset, 1)
            await ctx.tick()
            await ctx.tick()
            # Counter should be reset
            val = ctx.get(dut.counter)
            assert val <= 1, f"Expected 0 or 1, got {val}"

            # Deassert reset, counter should resume
            ctx.set(dut.reset, 0)
            await ctx.tick()
            await ctx.tick()
            await ctx.tick()
            val = ctx.get(dut.counter)
            assert val >= 2, f"Expected >= 2, got {val}"

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_reset_inserter.vcd"):
            sim.run()

    def test_custom_name(self):
        """Custom domain name is used."""

        class DUT(Elaboratable):
            def __init__(self):
                self.reset = Signal()

            def elaborate(self, platform):
                m = Module()
                name = add_reset_domain(m, self.reset, name="my_reset")
                assert name == "my_reset"
                return m

        dut = DUT()
        sim = Simulator(dut)
        sim.add_clock(1e-6)

        async def tb(ctx):
            await ctx.tick()

        sim.add_testbench(tb)
        sim.run()

    def test_default_name(self):
        """Default domain name is _rst_sync."""

        class DUT(Elaboratable):
            def __init__(self):
                self.reset = Signal()

            def elaborate(self, platform):
                m = Module()
                name = add_reset_domain(m, self.reset)
                assert name == "_rst_sync"
                return m

        dut = DUT()
        sim = Simulator(dut)
        sim.add_clock(1e-6)

        async def tb(ctx):
            await ctx.tick()

        sim.add_testbench(tb)
        sim.run()


if __name__ == "__main__":
    unittest.main()
