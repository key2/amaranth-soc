"""Simulation-based integration tests for Wishbone sim helpers with WishboneSRAM."""
import unittest
from amaranth.sim import Simulator
from amaranth_soc.wishbone.sram import WishboneSRAM
from amaranth_soc.sim.wishbone import wb_write, wb_read


class TestWishboneSRAMIntegration(unittest.TestCase):
    """Integration tests using WishboneSRAM as a real Wishbone target."""

    def test_wb_write_read_basic(self):
        """Write 0xDEADBEEF to address 0, read it back, verify match."""
        dut = WishboneSRAM(size=256, data_width=32)

        async def testbench(ctx):
            bus = dut.wb_bus
            await wb_write(ctx, bus, 0, 0xDEADBEEF)
            data, resp = await wb_read(ctx, bus, 0)
            assert data == 0xDEADBEEF, f"Expected 0xDEADBEEF, got {data:#010x}"
            assert resp == "ack"

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("test_wb_write_read_basic.vcd"):
            sim.run()

    def test_wb_write_read_multiple(self):
        """Write to addresses 0, 1, 2, read all back."""
        dut = WishboneSRAM(size=256, data_width=32)

        async def testbench(ctx):
            bus = dut.wb_bus
            test_data = {0: 0x11111111, 1: 0x22222222, 2: 0x33333333}
            # Write all
            for addr, data in test_data.items():
                await wb_write(ctx, bus, addr, data)
            # Read all back
            for addr, expected in test_data.items():
                data, resp = await wb_read(ctx, bus, addr)
                assert data == expected, \
                    f"At addr {addr}: expected {expected:#010x}, got {data:#010x}"
                assert resp == "ack"

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("test_wb_write_read_multiple.vcd"):
            sim.run()

    def test_wb_read_initial_zero(self):
        """Read from uninitialized SRAM, verify 0."""
        dut = WishboneSRAM(size=256, data_width=32)

        async def testbench(ctx):
            bus = dut.wb_bus
            data, resp = await wb_read(ctx, bus, 0)
            assert data == 0, f"Expected 0x00000000, got {data:#010x}"
            assert resp == "ack"

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("test_wb_read_initial_zero.vcd"):
            sim.run()


if __name__ == "__main__":
    unittest.main()
