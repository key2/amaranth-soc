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


if __name__ == "__main__":
    unittest.main()
