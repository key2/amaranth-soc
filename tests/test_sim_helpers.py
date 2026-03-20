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


if __name__ == "__main__":
    unittest.main()
