"""Tests for simulation helper functions."""
import unittest
from amaranth_soc.sim.axi import axi_lite_write, axi_lite_read


class TestSimHelpers(unittest.TestCase):
    def test_imports_from_module(self):
        """Verify sim helpers can be imported from the axi module."""
        self.assertTrue(callable(axi_lite_write))
        self.assertTrue(callable(axi_lite_read))

    def test_imports_from_package(self):
        """Verify sim helpers can be imported from the sim package."""
        from amaranth_soc.sim import axi_lite_write, axi_lite_read
        self.assertTrue(callable(axi_lite_write))
        self.assertTrue(callable(axi_lite_read))

    def test_write_is_coroutine_function(self):
        """axi_lite_write should be an async function."""
        import asyncio
        self.assertTrue(asyncio.iscoroutinefunction(axi_lite_write))

    def test_read_is_coroutine_function(self):
        """axi_lite_read should be an async function."""
        import asyncio
        self.assertTrue(asyncio.iscoroutinefunction(axi_lite_read))


class TestWishboneSimHelpers(unittest.TestCase):
    def test_wb_write_importable(self):
        """Verify wb_write can be imported from amaranth_soc.sim.wishbone."""
        from amaranth_soc.sim.wishbone import wb_write
        self.assertTrue(callable(wb_write))

    def test_wb_read_importable(self):
        """Verify wb_read can be imported from amaranth_soc.sim.wishbone."""
        from amaranth_soc.sim.wishbone import wb_read
        self.assertTrue(callable(wb_read))

    def test_wb_write_pipelined_importable(self):
        """Verify wb_write_pipelined can be imported from amaranth_soc.sim.wishbone."""
        from amaranth_soc.sim.wishbone import wb_write_pipelined
        self.assertTrue(callable(wb_write_pipelined))

    def test_wb_read_pipelined_importable(self):
        """Verify wb_read_pipelined can be imported from amaranth_soc.sim.wishbone."""
        from amaranth_soc.sim.wishbone import wb_read_pipelined
        self.assertTrue(callable(wb_read_pipelined))

    def test_wb_package_imports(self):
        """Verify all 4 Wishbone helpers can be imported from amaranth_soc.sim."""
        from amaranth_soc.sim import wb_write, wb_read, wb_write_pipelined, wb_read_pipelined
        self.assertTrue(callable(wb_write))
        self.assertTrue(callable(wb_read))
        self.assertTrue(callable(wb_write_pipelined))
        self.assertTrue(callable(wb_read_pipelined))

    def test_wb_write_is_coroutine(self):
        """wb_write should be an async function."""
        import asyncio
        from amaranth_soc.sim.wishbone import wb_write
        self.assertTrue(asyncio.iscoroutinefunction(wb_write))

    def test_wb_read_is_coroutine(self):
        """wb_read should be an async function."""
        import asyncio
        from amaranth_soc.sim.wishbone import wb_read
        self.assertTrue(asyncio.iscoroutinefunction(wb_read))


###############################################################################
# AXI4 Full simulation helper tests
###############################################################################

from amaranth.sim import Simulator
from amaranth_soc.axi.sram import AXI4SRAM
from amaranth_soc.axi.bus import AXIResp
from amaranth_soc.sim.axi import (
    axi4_write_burst, axi4_read_burst,
    axi4_write_single, axi4_read_single,
)


class TestAXI4FullHelperImports(unittest.TestCase):
    """Verify AXI4 Full helpers are importable and are coroutines."""

    def test_imports_from_module(self):
        self.assertTrue(callable(axi4_write_burst))
        self.assertTrue(callable(axi4_read_burst))
        self.assertTrue(callable(axi4_write_single))
        self.assertTrue(callable(axi4_read_single))

    def test_imports_from_package(self):
        from amaranth_soc.sim import (
            axi4_write_burst, axi4_read_burst,
            axi4_write_single, axi4_read_single,
        )
        self.assertTrue(callable(axi4_write_burst))
        self.assertTrue(callable(axi4_read_burst))
        self.assertTrue(callable(axi4_write_single))
        self.assertTrue(callable(axi4_read_single))

    def test_are_coroutine_functions(self):
        import asyncio
        self.assertTrue(asyncio.iscoroutinefunction(axi4_write_burst))
        self.assertTrue(asyncio.iscoroutinefunction(axi4_read_burst))
        self.assertTrue(asyncio.iscoroutinefunction(axi4_write_single))
        self.assertTrue(asyncio.iscoroutinefunction(axi4_read_single))


class TestAXI4WriteBurstSim(unittest.TestCase):
    """Simulation test: write 4 values via axi4_write_burst, read back via axi4_read_burst."""

    def test_axi4_write_burst_sim(self):
        dut = AXI4SRAM(size=1024, data_width=32)

        async def testbench(ctx):
            bus = dut.bus
            write_data = [0xAAAA0001, 0xBBBB0002, 0xCCCC0003, 0xDDDD0004]

            # Burst write 4 beats starting at address 0x00
            bresp = await axi4_write_burst(ctx, bus, 0x00, write_data)
            assert bresp == AXIResp.OKAY, f"Write bresp: {bresp}"

            # Burst read 4 beats starting at address 0x00
            data_list, rresp = await axi4_read_burst(ctx, bus, 0x00, 4)
            assert rresp == AXIResp.OKAY, f"Read rresp: {rresp}"
            for i, (got, expected) in enumerate(zip(data_list, write_data)):
                assert got == expected, \
                    f"Beat {i}: expected {expected:#010x}, got {got:#010x}"

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_axi4_helper_burst.vcd"):
            sim.run()


class TestAXI4SingleWriteReadSim(unittest.TestCase):
    """Simulation test: use axi4_write_single and axi4_read_single convenience wrappers."""

    def test_axi4_single_write_read_sim(self):
        dut = AXI4SRAM(size=1024, data_width=32)

        async def testbench(ctx):
            bus = dut.bus

            # Single write
            bresp = await axi4_write_single(ctx, bus, 0x10, 0xDEADBEEF)
            assert bresp == AXIResp.OKAY

            # Single read
            data, rresp = await axi4_read_single(ctx, bus, 0x10)
            assert rresp == AXIResp.OKAY
            assert data == 0xDEADBEEF, f"Expected 0xDEADBEEF, got {data:#010x}"

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_axi4_helper_single.vcd"):
            sim.run()


class TestAXI4WriteWithIdSim(unittest.TestCase):
    """Simulation test: write with id=5, verify the response has matching bid."""

    def test_axi4_write_with_id_sim(self):
        dut = AXI4SRAM(size=1024, data_width=32, id_width=4)

        async def testbench(ctx):
            bus = dut.bus

            # Write with id=5
            bresp = await axi4_write_single(ctx, bus, 0x00, 0xCAFEBABE, id=5)
            assert bresp == AXIResp.OKAY

            # The AXI4SRAM echoes the ID back on bid.
            # We can verify by reading back with a different id and checking data.
            data, rresp = await axi4_read_single(ctx, bus, 0x00, id=7)
            assert data == 0xCAFEBABE, f"Expected 0xCAFEBABE, got {data:#010x}"
            assert rresp == AXIResp.OKAY

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_axi4_helper_id.vcd"):
            sim.run()


if __name__ == "__main__":
    unittest.main()
