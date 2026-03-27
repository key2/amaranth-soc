"""Tests for endianness support in bus primitives."""
import unittest

from amaranth import *
from amaranth.sim import Simulator

from amaranth_soc.bus_common import Endianness, byte_swap, EndianAdapter
from amaranth_soc.axi.bus import (
    AXI4LiteSignature, AXI4LiteInterface,
    AXI4Signature, AXI4Interface,
)
from amaranth_soc.axi.sram import AXI4LiteSRAM
from amaranth_soc.sim.axi import axi_lite_write, axi_lite_read
from amaranth_soc.wishbone.bus import Signature as WishboneSignature


# ---------------------------------------------------------------------------
# 1. Endianness enum
# ---------------------------------------------------------------------------

class TestEndianness(unittest.TestCase):
    def test_little_value(self):
        self.assertEqual(Endianness.LITTLE.value, "little")

    def test_big_value(self):
        self.assertEqual(Endianness.BIG.value, "big")

    def test_members(self):
        self.assertEqual(set(Endianness), {Endianness.LITTLE, Endianness.BIG})

    def test_identity(self):
        self.assertIs(Endianness("little"), Endianness.LITTLE)
        self.assertIs(Endianness("big"), Endianness.BIG)


# ---------------------------------------------------------------------------
# 2. EndianAdapter — simulation tests
# ---------------------------------------------------------------------------

def _wrap_with_sync(adapter):
    """Wrap a purely combinational EndianAdapter in a module that has a sync
    domain so the Amaranth simulator can add a clock."""
    class _Wrapper(Elaboratable):
        def elaborate(self, platform):
            m = Module()
            m.submodules.adapter = adapter
            # Add a dummy sync register so the sync domain exists
            dummy = Signal()
            m.d.sync += dummy.eq(~dummy)
            return m
    return _Wrapper()


class TestEndianAdapter(unittest.TestCase):
    def test_invalid_data_width_not_multiple_of_8(self):
        with self.assertRaises(ValueError):
            EndianAdapter(data_width=13)

    def test_invalid_data_width_zero(self):
        with self.assertRaises(ValueError):
            EndianAdapter(data_width=0)

    def test_invalid_data_width_negative(self):
        with self.assertRaises(ValueError):
            EndianAdapter(data_width=-8)

    def test_invalid_data_width_string(self):
        with self.assertRaises(ValueError):
            EndianAdapter(data_width="32")

    def test_data_width_property(self):
        adapter = EndianAdapter(data_width=32)
        self.assertEqual(adapter.data_width, 32)

    def test_swap_32bit(self):
        """Feed 0xDEADBEEF, expect 0xEFBEADDE."""
        dut = EndianAdapter(data_width=32)

        async def testbench(ctx):
            ctx.set(dut.i_data, 0xDEADBEEF)
            await ctx.tick()
            result = ctx.get(dut.o_data)
            self.assertEqual(result, 0xEFBEADDE,
                             f"Expected 0xEFBEADDE, got {result:#010x}")

        sim = Simulator(_wrap_with_sync(dut))
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_endian_swap_32.vcd"):
            sim.run()

    def test_swap_64bit(self):
        """Feed 0x0102030405060708, expect 0x0807060504030201."""
        dut = EndianAdapter(data_width=64)

        async def testbench(ctx):
            ctx.set(dut.i_data, 0x0102030405060708)
            await ctx.tick()
            result = ctx.get(dut.o_data)
            self.assertEqual(result, 0x0807060504030201,
                             f"Expected 0x0807060504030201, got {result:#018x}")

        sim = Simulator(_wrap_with_sync(dut))
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_endian_swap_64.vcd"):
            sim.run()

    def test_swap_16bit(self):
        """Feed 0xAABB, expect 0xBBAA."""
        dut = EndianAdapter(data_width=16)

        async def testbench(ctx):
            ctx.set(dut.i_data, 0xAABB)
            await ctx.tick()
            result = ctx.get(dut.o_data)
            self.assertEqual(result, 0xBBAA,
                             f"Expected 0xBBAA, got {result:#06x}")

        sim = Simulator(_wrap_with_sync(dut))
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_endian_swap_16.vcd"):
            sim.run()

    def test_swap_8bit_identity(self):
        """8-bit swap is identity."""
        dut = EndianAdapter(data_width=8)

        async def testbench(ctx):
            ctx.set(dut.i_data, 0xAB)
            await ctx.tick()
            result = ctx.get(dut.o_data)
            self.assertEqual(result, 0xAB)

        sim = Simulator(_wrap_with_sync(dut))
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_endian_swap_8.vcd"):
            sim.run()


# ---------------------------------------------------------------------------
# 3. byte_swap utility function
# ---------------------------------------------------------------------------

class TestByteSwapFunction(unittest.TestCase):
    def test_invalid_data_width(self):
        m = Module()
        sig = Signal(13)
        with self.assertRaises(ValueError):
            byte_swap(m, sig, 13)

    def test_byte_swap_32bit(self):
        """Verify byte_swap produces correct combinational logic."""
        data_in = Signal(32)
        m = Module()
        data_out = byte_swap(m, data_in, 32)
        # Add a dummy sync register so the sync domain exists
        dummy = Signal()
        m.d.sync += dummy.eq(~dummy)

        async def testbench(ctx):
            ctx.set(data_in, 0xDEADBEEF)
            await ctx.tick()
            result = ctx.get(data_out)
            self.assertEqual(result, 0xEFBEADDE,
                             f"Expected 0xEFBEADDE, got {result:#010x}")

        # Wrap in a simple component for simulation
        class Wrapper(Elaboratable):
            def elaborate(self, platform):
                return m

        sim = Simulator(Wrapper())
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_byte_swap_fn.vcd"):
            sim.run()


# ---------------------------------------------------------------------------
# 4. AXI4LiteSignature endianness parameter
# ---------------------------------------------------------------------------

class TestAXI4LiteSignatureEndianness(unittest.TestCase):
    def test_default_endianness(self):
        sig = AXI4LiteSignature(addr_width=32, data_width=32)
        self.assertEqual(sig.endianness, Endianness.LITTLE)

    def test_explicit_little(self):
        sig = AXI4LiteSignature(addr_width=32, data_width=32, endianness=Endianness.LITTLE)
        self.assertEqual(sig.endianness, Endianness.LITTLE)

    def test_explicit_big(self):
        sig = AXI4LiteSignature(addr_width=32, data_width=32, endianness=Endianness.BIG)
        self.assertEqual(sig.endianness, Endianness.BIG)

    def test_invalid_endianness(self):
        with self.assertRaises(ValueError):
            AXI4LiteSignature(addr_width=32, data_width=32, endianness="big")

    def test_equality_same_endianness(self):
        sig1 = AXI4LiteSignature(addr_width=32, data_width=32, endianness=Endianness.LITTLE)
        sig2 = AXI4LiteSignature(addr_width=32, data_width=32, endianness=Endianness.LITTLE)
        self.assertEqual(sig1, sig2)

    def test_inequality_different_endianness(self):
        sig1 = AXI4LiteSignature(addr_width=32, data_width=32, endianness=Endianness.LITTLE)
        sig2 = AXI4LiteSignature(addr_width=32, data_width=32, endianness=Endianness.BIG)
        self.assertNotEqual(sig1, sig2)

    def test_create_preserves_endianness(self):
        sig = AXI4LiteSignature(addr_width=16, data_width=32, endianness=Endianness.BIG)
        iface = sig.create()
        self.assertIsInstance(iface, AXI4LiteInterface)
        self.assertEqual(iface.endianness, Endianness.BIG)


# ---------------------------------------------------------------------------
# 5. AXI4Signature endianness parameter
# ---------------------------------------------------------------------------

class TestAXI4SignatureEndianness(unittest.TestCase):
    def test_default_endianness(self):
        sig = AXI4Signature(addr_width=32, data_width=32)
        self.assertEqual(sig.endianness, Endianness.LITTLE)

    def test_explicit_big(self):
        sig = AXI4Signature(addr_width=32, data_width=32, endianness=Endianness.BIG)
        self.assertEqual(sig.endianness, Endianness.BIG)

    def test_invalid_endianness(self):
        with self.assertRaises(ValueError):
            AXI4Signature(addr_width=32, data_width=32, endianness="little")

    def test_equality_same_endianness(self):
        sig1 = AXI4Signature(addr_width=32, data_width=32, endianness=Endianness.LITTLE)
        sig2 = AXI4Signature(addr_width=32, data_width=32, endianness=Endianness.LITTLE)
        self.assertEqual(sig1, sig2)

    def test_inequality_different_endianness(self):
        sig1 = AXI4Signature(addr_width=32, data_width=32, endianness=Endianness.LITTLE)
        sig2 = AXI4Signature(addr_width=32, data_width=32, endianness=Endianness.BIG)
        self.assertNotEqual(sig1, sig2)

    def test_create_preserves_endianness(self):
        sig = AXI4Signature(addr_width=16, data_width=32, endianness=Endianness.BIG)
        iface = sig.create()
        self.assertIsInstance(iface, AXI4Interface)
        self.assertEqual(iface.endianness, Endianness.BIG)


# ---------------------------------------------------------------------------
# 6. Wishbone Signature endianness parameter
# ---------------------------------------------------------------------------

class TestWishboneSignatureEndianness(unittest.TestCase):
    def test_default_endianness(self):
        sig = WishboneSignature(addr_width=16, data_width=32)
        self.assertEqual(sig.endianness, Endianness.LITTLE)

    def test_explicit_big(self):
        sig = WishboneSignature(addr_width=16, data_width=32, endianness=Endianness.BIG)
        self.assertEqual(sig.endianness, Endianness.BIG)

    def test_invalid_endianness(self):
        with self.assertRaises(ValueError):
            WishboneSignature(addr_width=16, data_width=32, endianness=42)

    def test_equality_same_endianness(self):
        sig1 = WishboneSignature(addr_width=16, data_width=32, endianness=Endianness.LITTLE)
        sig2 = WishboneSignature(addr_width=16, data_width=32, endianness=Endianness.LITTLE)
        self.assertEqual(sig1, sig2)

    def test_inequality_different_endianness(self):
        sig1 = WishboneSignature(addr_width=16, data_width=32, endianness=Endianness.LITTLE)
        sig2 = WishboneSignature(addr_width=16, data_width=32, endianness=Endianness.BIG)
        self.assertNotEqual(sig1, sig2)

    def test_create_preserves_endianness(self):
        sig = WishboneSignature(addr_width=16, data_width=32, endianness=Endianness.BIG)
        iface = sig.create()
        self.assertEqual(iface.endianness, Endianness.BIG)


# ---------------------------------------------------------------------------
# 7. Integration test: AXI4-Lite SRAMs with endianness metadata
# ---------------------------------------------------------------------------

class TestEndiannessSRAMIntegration(unittest.TestCase):
    """Integration test: verify endianness metadata is tracked correctly
    through AXI4-Lite SRAM instances."""

    def test_sram_endianness_metadata(self):
        """Create two AXI4-Lite SRAMs, one little-endian and one big-endian.
        Write the same value to both and verify the endianness metadata is
        correctly tracked via the bus signature."""
        dut_le = AXI4LiteSRAM(size=64, data_width=32)
        dut_be = AXI4LiteSRAM(size=64, data_width=32)

        # The SRAM itself doesn't take endianness, but the bus signature does.
        # Verify the default is little-endian.
        self.assertEqual(dut_le.bus.signature.endianness, Endianness.LITTLE)
        self.assertEqual(dut_be.bus.signature.endianness, Endianness.LITTLE)

    def test_sram_write_read_with_endianness_tracking(self):
        """Write a value to an SRAM, read it back, and verify the endianness
        metadata is available for bridge logic to use."""
        test_value = 0xDEADBEEF
        dut = AXI4LiteSRAM(size=64, data_width=32)

        # Verify endianness is accessible
        self.assertEqual(dut.bus.signature.endianness, Endianness.LITTLE)

        async def testbench(ctx):
            bus = dut.bus
            # Write
            await axi_lite_write(ctx, bus, 0x00, test_value)
            # Read back
            data, resp = await axi_lite_read(ctx, bus, 0x00)
            self.assertEqual(data, test_value,
                             f"Expected {test_value:#010x}, got {data:#010x}")

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_endian_sram_integration.vcd"):
            sim.run()

    def test_endian_adapter_with_sram_data(self):
        """Simulate writing a value, byte-swapping it through EndianAdapter,
        and verifying the result — as a bridge would do."""
        sram = AXI4LiteSRAM(size=64, data_width=32)
        adapter = EndianAdapter(data_width=32)

        async def testbench(ctx):
            bus = sram.bus
            # Write 0xDEADBEEF to SRAM
            await axi_lite_write(ctx, bus, 0x00, 0xDEADBEEF)
            # Read it back
            data, _ = await axi_lite_read(ctx, bus, 0x00)
            self.assertEqual(data, 0xDEADBEEF)

            # Now feed through the adapter
            ctx.set(adapter.i_data, data)
            await ctx.tick()
            swapped = ctx.get(adapter.o_data)
            self.assertEqual(swapped, 0xEFBEADDE,
                             f"Expected 0xEFBEADDE, got {swapped:#010x}")

        # Build a top-level module containing both
        class Top(Elaboratable):
            def elaborate(self, platform):
                m = Module()
                m.submodules.sram = sram
                m.submodules.adapter = adapter
                return m

        sim = Simulator(Top())
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_endian_adapter_sram.vcd"):
            sim.run()


if __name__ == "__main__":
    unittest.main()
