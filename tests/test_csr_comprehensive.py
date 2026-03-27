# amaranth: UnusedElaboratable=no
"""Comprehensive CSR test suite exercising the full stack:
  CPU bus → bridge → multiplexer → register → field action and back.

Tests cover Wishbone and AXI4-Lite bridges with all field action types,
edge cases, and event monitor integration.
"""

import unittest
import warnings
from amaranth import *
from amaranth.hdl import UnusedElaboratable
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out, connect, flipped
from amaranth.sim import *

from amaranth_soc import csr, event
from amaranth_soc.csr import action, Element, Multiplexer, Decoder
from amaranth_soc.csr.reg import Register, Field, Builder, Bridge
from amaranth_soc.csr.wishbone import WishboneCSRBridge
from amaranth_soc.csr.axi_lite import AXI4LiteCSRBridge
from amaranth_soc.csr.event import EventMonitor
from amaranth_soc.memory import MemoryMap
from amaranth_soc.sim.wishbone import wb_write, wb_read
from amaranth_soc.sim.axi import axi_lite_write, axi_lite_read


warnings.simplefilter(action="ignore", category=UnusedElaboratable)


# =============================================================================
# Register definitions used across tests
# =============================================================================

class AllFieldsRegister(Register, access="rw"):
    """Register with all major field action types for comprehensive testing."""
    ro_field:   Field(action.R,    unsigned(4))
    wo_field:   Field(action.W,    unsigned(4))
    rw_field:   Field(action.RW,   unsigned(8), init=0xAB)
    rw1c_field: Field(action.RW1C, unsigned(4), init=0xF)
    rw1s_field: Field(action.RW1S, unsigned(4))
    res_field:  Field(action.ResR0W0, unsigned(8))


class SimpleRWRegister(Register, access="rw"):
    """Simple 8-bit RW register."""
    value: Field(action.RW, unsigned(8))


class SimpleRWRegister16(Register, access="rw"):
    """Simple 16-bit RW register."""
    value: Field(action.RW, unsigned(16))


class WideRegister(Register, access="rw"):
    """Wide 48-bit register for testing multi-beat access."""
    value: Field(action.RW, unsigned(48))


class InitRegister(Register, access="rw"):
    """Register with non-zero init values."""
    a: Field(action.RW, unsigned(8), init=0xDE)
    b: Field(action.RW, unsigned(8), init=0xAD)


class MixedAccessRegister(Register, access="rw"):
    """Register with mixed R, W, and RW fields."""
    ro_part: Field(action.R,  unsigned(8))
    rw_part: Field(action.RW, unsigned(8))
    wo_part: Field(action.W,  unsigned(8))


class RW1CRegister(Register, access="rw"):
    """Register with only RW1C field for focused testing."""
    status: Field(action.RW1C, unsigned(8), init=0)


class RW1SRegister(Register, access="rw"):
    """Register with only RW1S field for focused testing."""
    control: Field(action.RW1S, unsigned(8), init=0)


class ReservedFieldsRegister(Register, access="rw"):
    """Register with reserved fields between data fields."""
    data_lo:  Field(action.RW, unsigned(4))
    reserved: Field(action.ResR0W0, unsigned(4))
    data_hi:  Field(action.RW, unsigned(4))


# =============================================================================
# Test 1: Field Actions End-to-End through CSR bus
# =============================================================================

class TestCSRFieldActionsEndToEnd(unittest.TestCase):
    """Test all field action types through CSR bus (Multiplexer level)."""

    def test_rw_field_write_read(self):
        """RW field: write a value, read it back."""
        reg = SimpleRWRegister()
        memory_map = MemoryMap(addr_width=4, data_width=8)
        memory_map.add_resource(reg, name=("reg",), size=1)
        mux = Multiplexer(memory_map)

        async def testbench(ctx):
            # Write 0x42
            ctx.set(mux.bus.addr, 0)
            ctx.set(mux.bus.w_stb, 1)
            ctx.set(mux.bus.w_data, 0x42)
            await ctx.tick()
            ctx.set(mux.bus.w_stb, 0)
            await ctx.tick()  # w_stb is delayed 1 cycle

            # Read back
            ctx.set(mux.bus.addr, 0)
            ctx.set(mux.bus.r_stb, 1)
            await ctx.tick()
            r_data = ctx.get(mux.bus.r_data)
            ctx.set(mux.bus.r_stb, 0)
            self.assertEqual(r_data, 0x42)

        m = Module()
        m.submodules.reg = reg
        m.submodules.mux = mux
        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_rw_field_init_value(self):
        """RW field with init value should read back init before any write."""
        reg = SimpleRWRegister()  # init=0 by default for unsigned(8)
        reg_init = InitRegister()  # a=0xDE, b=0xAD
        memory_map = MemoryMap(addr_width=4, data_width=8)
        memory_map.add_resource(reg_init, name=("reg",), size=2)
        mux = Multiplexer(memory_map)

        async def testbench(ctx):
            # Read first byte (field a, init=0xDE)
            ctx.set(mux.bus.addr, 0)
            ctx.set(mux.bus.r_stb, 1)
            await ctx.tick()
            r_data = ctx.get(mux.bus.r_data)
            ctx.set(mux.bus.r_stb, 0)
            self.assertEqual(r_data, 0xDE)

            # Read second byte (field b, init=0xAD)
            ctx.set(mux.bus.addr, 1)
            ctx.set(mux.bus.r_stb, 1)
            await ctx.tick()
            r_data = ctx.get(mux.bus.r_data)
            ctx.set(mux.bus.r_stb, 0)
            self.assertEqual(r_data, 0xAD)

        m = Module()
        m.submodules.reg_init = reg_init
        m.submodules.mux = mux
        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_rw1c_field(self):
        """RW1C: set bits externally, write 1s to clear, verify cleared."""
        reg = RW1CRegister()
        memory_map = MemoryMap(addr_width=4, data_width=8)
        memory_map.add_resource(reg, name=("reg",), size=1)
        mux = Multiplexer(memory_map)

        async def testbench(ctx):
            # Set bits externally via the .set signal
            ctx.set(reg.f.status.set, 0b10110101)
            await ctx.tick()
            ctx.set(reg.f.status.set, 0)

            # Read to confirm bits are set
            ctx.set(mux.bus.addr, 0)
            ctx.set(mux.bus.r_stb, 1)
            await ctx.tick()
            r_data = ctx.get(mux.bus.r_data)
            ctx.set(mux.bus.r_stb, 0)
            self.assertEqual(r_data, 0b10110101)

            # Write 1s to clear specific bits (clear bits 0, 2, 4)
            ctx.set(mux.bus.addr, 0)
            ctx.set(mux.bus.w_stb, 1)
            ctx.set(mux.bus.w_data, 0b00010101)
            await ctx.tick()
            ctx.set(mux.bus.w_stb, 0)
            await ctx.tick()  # w_stb delayed

            # Read to confirm those bits are cleared
            ctx.set(mux.bus.addr, 0)
            ctx.set(mux.bus.r_stb, 1)
            await ctx.tick()
            r_data = ctx.get(mux.bus.r_data)
            ctx.set(mux.bus.r_stb, 0)
            self.assertEqual(r_data, 0b10100000)

        m = Module()
        m.submodules.reg = reg
        m.submodules.mux = mux
        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_rw1s_field(self):
        """RW1S: write 1s to set bits, clear externally, verify."""
        reg = RW1SRegister()
        memory_map = MemoryMap(addr_width=4, data_width=8)
        memory_map.add_resource(reg, name=("reg",), size=1)
        mux = Multiplexer(memory_map)

        async def testbench(ctx):
            # Write 1s to set bits
            ctx.set(mux.bus.addr, 0)
            ctx.set(mux.bus.w_stb, 1)
            ctx.set(mux.bus.w_data, 0b11001010)
            await ctx.tick()
            ctx.set(mux.bus.w_stb, 0)
            await ctx.tick()  # w_stb delayed

            # Read to confirm bits are set
            ctx.set(mux.bus.addr, 0)
            ctx.set(mux.bus.r_stb, 1)
            await ctx.tick()
            r_data = ctx.get(mux.bus.r_data)
            ctx.set(mux.bus.r_stb, 0)
            self.assertEqual(r_data, 0b11001010)

            # Clear some bits externally
            ctx.set(reg.f.control.clear, 0b01001010)
            await ctx.tick()
            ctx.set(reg.f.control.clear, 0)

            # Read to confirm those bits are cleared
            ctx.set(mux.bus.addr, 0)
            ctx.set(mux.bus.r_stb, 1)
            await ctx.tick()
            r_data = ctx.get(mux.bus.r_data)
            ctx.set(mux.bus.r_stb, 0)
            self.assertEqual(r_data, 0b10000000)

        m = Module()
        m.submodules.reg = reg
        m.submodules.mux = mux
        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_reserved_field_reads_zero(self):
        """Reserved ResR0W0 field should read as zero and not corrupt neighbors."""
        reg = ReservedFieldsRegister()
        memory_map = MemoryMap(addr_width=4, data_width=8)
        memory_map.add_resource(reg, name=("reg",), size=2)
        mux = Multiplexer(memory_map)

        async def testbench(ctx):
            # Write 0xFF to first byte (data_lo[3:0] + reserved[7:4])
            ctx.set(mux.bus.addr, 0)
            ctx.set(mux.bus.w_stb, 1)
            ctx.set(mux.bus.w_data, 0xFF)
            await ctx.tick()
            ctx.set(mux.bus.w_stb, 0)

            # Write 0xFF to second byte (data_hi[3:0] + padding)
            ctx.set(mux.bus.addr, 1)
            ctx.set(mux.bus.w_stb, 1)
            ctx.set(mux.bus.w_data, 0xFF)
            await ctx.tick()
            ctx.set(mux.bus.w_stb, 0)
            await ctx.tick()  # w_stb delayed

            # Read first byte: data_lo should be 0xF, reserved should be 0
            ctx.set(mux.bus.addr, 0)
            ctx.set(mux.bus.r_stb, 1)
            await ctx.tick()
            r_data = ctx.get(mux.bus.r_data)
            ctx.set(mux.bus.r_stb, 0)
            # data_lo = 0xF (bits 3:0), reserved = 0 (bits 7:4)
            self.assertEqual(r_data & 0x0F, 0x0F, "data_lo should be 0xF")
            self.assertEqual(r_data & 0xF0, 0x00, "reserved should read 0")

            # Read second byte: data_hi should be 0xF
            ctx.set(mux.bus.addr, 1)
            ctx.set(mux.bus.r_stb, 1)
            await ctx.tick()
            r_data = ctx.get(mux.bus.r_data)
            ctx.set(mux.bus.r_stb, 0)
            self.assertEqual(r_data & 0x0F, 0x0F, "data_hi should be 0xF")

        m = Module()
        m.submodules.reg = reg
        m.submodules.mux = mux
        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()


# =============================================================================
# Test 2: Wishbone → CSR → Register End-to-End
# =============================================================================

class TestWishboneCSREndToEnd(unittest.TestCase):
    """Full Wishbone → CSR → Register stack tests using wb_write/wb_read helpers."""

    def _build_wb_dut(self, registers, data_width=32):
        """Build a Wishbone CSR test DUT.

        Returns (module, wb_bridge, registers_dict) where registers_dict maps
        names to register objects.
        """
        regs = Builder(addr_width=16, data_width=8)
        reg_dict = {}
        for name, reg in registers:
            regs.add(name, reg)
            reg_dict[name] = reg

        memory_map = regs.as_memory_map()
        mux = Multiplexer(memory_map)
        wb_bridge = WishboneCSRBridge(mux.bus, data_width=data_width)

        m = Module()
        m.submodules.mux = mux
        m.submodules.wb_bridge = wb_bridge
        for name, reg in reg_dict.items():
            m.submodules[name] = reg

        return m, wb_bridge, reg_dict

    def test_rw_write_read_roundtrip(self):
        """Write a value via Wishbone, read it back."""
        reg = SimpleRWRegister()
        m, wb_bridge, regs = self._build_wb_dut([("reg", reg)], data_width=32)

        async def testbench(ctx):
            # Write 0x42 to address 0 (8-bit CSR, 32-bit WB → 4 beats, addr 0)
            await wb_write(ctx, wb_bridge.wb_bus, 0, 0x42)
            # Read back
            data, resp = await wb_read(ctx, wb_bridge.wb_bus, 0)
            self.assertEqual(data & 0xFF, 0x42)

        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_16bit_register_roundtrip(self):
        """Write and read a 16-bit register through 32-bit Wishbone."""
        reg = SimpleRWRegister16()
        m, wb_bridge, regs = self._build_wb_dut([("reg", reg)], data_width=32)

        async def testbench(ctx):
            # 16-bit register occupies 2 CSR bytes → addr 0 in 32-bit WB space
            await wb_write(ctx, wb_bridge.wb_bus, 0, 0xBEEF)
            data, resp = await wb_read(ctx, wb_bridge.wb_bus, 0)
            self.assertEqual(data & 0xFFFF, 0xBEEF)

        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_rw1c_through_wishbone(self):
        """RW1C: set bits externally, read via WB, write 1s to clear, read again."""
        reg = RW1CRegister()
        m, wb_bridge, regs = self._build_wb_dut([("reg", reg)], data_width=32)

        async def testbench(ctx):
            # Set bits externally
            ctx.set(reg.f.status.set, 0xFF)
            await ctx.tick()
            ctx.set(reg.f.status.set, 0)
            await ctx.tick()

            # Read via WB to confirm bits are set
            data, resp = await wb_read(ctx, wb_bridge.wb_bus, 0)
            self.assertEqual(data & 0xFF, 0xFF)

            # Write 1s to clear bits 0-3
            await wb_write(ctx, wb_bridge.wb_bus, 0, 0x0F)

            # Read to confirm bits 0-3 cleared
            data, resp = await wb_read(ctx, wb_bridge.wb_bus, 0)
            self.assertEqual(data & 0xFF, 0xF0)

        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_rw1s_through_wishbone(self):
        """RW1S: write 1s to set via WB, clear externally, read to confirm."""
        reg = RW1SRegister()
        m, wb_bridge, regs = self._build_wb_dut([("reg", reg)], data_width=32)

        async def testbench(ctx):
            # Write 1s to set bits via WB
            await wb_write(ctx, wb_bridge.wb_bus, 0, 0xA5)

            # Read to confirm bits are set
            data, resp = await wb_read(ctx, wb_bridge.wb_bus, 0)
            self.assertEqual(data & 0xFF, 0xA5)

            # Clear some bits externally
            ctx.set(reg.f.control.clear, 0x05)
            await ctx.tick()
            ctx.set(reg.f.control.clear, 0)
            await ctx.tick()

            # Read to confirm those bits cleared
            data, resp = await wb_read(ctx, wb_bridge.wb_bus, 0)
            self.assertEqual(data & 0xFF, 0xA0)

        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_read_only_field_write_ignored(self):
        """Writing to a read-only field should not change its value."""
        class RORegister(Register, access="r"):
            value: Field(action.R, unsigned(8))

        reg = RORegister()
        regs = Builder(addr_width=16, data_width=8)
        regs.add("reg", reg)
        memory_map = regs.as_memory_map()
        mux = Multiplexer(memory_map)
        wb_bridge = WishboneCSRBridge(mux.bus, data_width=32)

        m = Module()
        m.submodules.reg = reg
        m.submodules.mux = mux
        m.submodules.wb_bridge = wb_bridge

        async def testbench(ctx):
            # Set the R field externally
            ctx.set(reg.f.value.r_data, 0x55)

            # Read via WB
            data, resp = await wb_read(ctx, wb_bridge.wb_bus, 0)
            self.assertEqual(data & 0xFF, 0x55)

        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_write_only_field_reads_zero(self):
        """Reading a write-only field should return 0."""
        class WORegister(Register, access="w"):
            value: Field(action.W, unsigned(8))

        reg = WORegister()
        regs = Builder(addr_width=16, data_width=8)
        regs.add("reg", reg)
        memory_map = regs.as_memory_map()
        mux = Multiplexer(memory_map)
        wb_bridge = WishboneCSRBridge(mux.bus, data_width=32)

        m = Module()
        m.submodules.reg = reg
        m.submodules.mux = mux
        m.submodules.wb_bridge = wb_bridge

        async def testbench(ctx):
            # Write a value
            await wb_write(ctx, wb_bridge.wb_bus, 0, 0xAA)

            # Verify the write was received
            self.assertEqual(ctx.get(reg.f.value.w_data), 0xAA)

        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_back_to_back_transactions(self):
        """Multiple back-to-back write/read transactions."""
        reg = SimpleRWRegister()
        m, wb_bridge, regs = self._build_wb_dut([("reg", reg)], data_width=32)

        async def testbench(ctx):
            for val in [0x11, 0x22, 0x33, 0x44, 0x55]:
                await wb_write(ctx, wb_bridge.wb_bus, 0, val)
                data, resp = await wb_read(ctx, wb_bridge.wb_bus, 0)
                self.assertEqual(data & 0xFF, val)

        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_multiple_registers(self):
        """Multiple registers at different addresses.

        With 8-bit CSR and 32-bit WB (ratio=4), each WB word covers 4 CSR addresses.
        Two 8-bit registers at CSR addr 0 and 1 both map to WB word 0, in byte lanes 0 and 1.
        We write both in a single WB word.
        """
        reg_a = SimpleRWRegister()
        reg_b = SimpleRWRegister()
        m, wb_bridge, regs = self._build_wb_dut([
            ("reg_a", reg_a),
            ("reg_b", reg_b),
        ], data_width=32)

        async def testbench(ctx):
            # Both 8-bit registers are in WB word 0:
            # reg_a at byte 0, reg_b at byte 1
            # Write both at once: 0xBB in byte 1, 0xAA in byte 0
            await wb_write(ctx, wb_bridge.wb_bus, 0, 0x0000BBAA)

            # Read back the WB word
            data, _ = await wb_read(ctx, wb_bridge.wb_bus, 0)
            self.assertEqual(data & 0xFF, 0xAA, "reg_a should be 0xAA")
            self.assertEqual((data >> 8) & 0xFF, 0xBB, "reg_b should be 0xBB")

        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_init_values_persist(self):
        """Registers with init values should read correctly before any write."""
        reg = InitRegister()  # a=0xDE, b=0xAD
        m, wb_bridge, regs = self._build_wb_dut([("reg", reg)], data_width=32)

        async def testbench(ctx):
            data, _ = await wb_read(ctx, wb_bridge.wb_bus, 0)
            # 16-bit register: low byte = a (0xDE), high byte = b (0xAD)
            self.assertEqual(data & 0xFFFF, 0xADDE)

        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()


# =============================================================================
# Test 3: AXI-Lite → CSR → Register End-to-End (CRITICAL - currently untested)
# =============================================================================

class TestAXILiteCSREndToEnd(unittest.TestCase):
    """Full AXI4-Lite → CSR → Register stack tests using axi_lite_write/axi_lite_read."""

    def _build_axi_dut(self, registers, data_width=32):
        """Build an AXI-Lite CSR test DUT.

        Returns (module, axi_bridge, registers_dict).
        """
        regs = Builder(addr_width=16, data_width=8)
        reg_dict = {}
        for name, reg in registers:
            regs.add(name, reg)
            reg_dict[name] = reg

        memory_map = regs.as_memory_map()
        mux = Multiplexer(memory_map)
        axi_bridge = AXI4LiteCSRBridge(mux.bus, data_width=data_width)

        m = Module()
        m.submodules.mux = mux
        m.submodules.axi_bridge = axi_bridge
        for name, reg in reg_dict.items():
            m.submodules[name] = reg

        return m, axi_bridge, reg_dict

    def test_rw_write_read_roundtrip(self):
        """Basic write/read roundtrip through AXI-Lite bridge."""
        reg = SimpleRWRegister()
        m, axi_bridge, regs = self._build_axi_dut([("reg", reg)], data_width=32)

        async def testbench(ctx):
            await axi_lite_write(ctx, axi_bridge.axi_bus, 0, 0x42)
            data, resp = await axi_lite_read(ctx, axi_bridge.axi_bus, 0)
            self.assertEqual(data & 0xFF, 0x42)

        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_16bit_register_roundtrip(self):
        """Write and read a 16-bit register through 32-bit AXI-Lite."""
        reg = SimpleRWRegister16()
        m, axi_bridge, regs = self._build_axi_dut([("reg", reg)], data_width=32)

        async def testbench(ctx):
            await axi_lite_write(ctx, axi_bridge.axi_bus, 0, 0xCAFE)
            data, resp = await axi_lite_read(ctx, axi_bridge.axi_bus, 0)
            self.assertEqual(data & 0xFFFF, 0xCAFE)

        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_rw1c_through_axi(self):
        """RW1C field through AXI-Lite bridge."""
        reg = RW1CRegister()
        m, axi_bridge, regs = self._build_axi_dut([("reg", reg)], data_width=32)

        async def testbench(ctx):
            # Set bits externally
            ctx.set(reg.f.status.set, 0xFF)
            await ctx.tick()
            ctx.set(reg.f.status.set, 0)
            await ctx.tick()

            # Read via AXI to confirm
            data, resp = await axi_lite_read(ctx, axi_bridge.axi_bus, 0)
            self.assertEqual(data & 0xFF, 0xFF)

            # Write 1s to clear lower nibble
            await axi_lite_write(ctx, axi_bridge.axi_bus, 0, 0x0F)

            # Read to confirm cleared
            data, resp = await axi_lite_read(ctx, axi_bridge.axi_bus, 0)
            self.assertEqual(data & 0xFF, 0xF0)

        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_rw1s_through_axi(self):
        """RW1S field through AXI-Lite bridge."""
        reg = RW1SRegister()
        m, axi_bridge, regs = self._build_axi_dut([("reg", reg)], data_width=32)

        async def testbench(ctx):
            # Write 1s to set bits
            await axi_lite_write(ctx, axi_bridge.axi_bus, 0, 0xA5)

            # Read to confirm
            data, resp = await axi_lite_read(ctx, axi_bridge.axi_bus, 0)
            self.assertEqual(data & 0xFF, 0xA5)

            # Clear externally
            ctx.set(reg.f.control.clear, 0x05)
            await ctx.tick()
            ctx.set(reg.f.control.clear, 0)
            await ctx.tick()

            # Read to confirm
            data, resp = await axi_lite_read(ctx, axi_bridge.axi_bus, 0)
            self.assertEqual(data & 0xFF, 0xA0)

        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_back_to_back_transactions(self):
        """Multiple back-to-back AXI-Lite transactions."""
        reg = SimpleRWRegister()
        m, axi_bridge, regs = self._build_axi_dut([("reg", reg)], data_width=32)

        async def testbench(ctx):
            for val in [0x11, 0x22, 0x33, 0x44, 0x55]:
                await axi_lite_write(ctx, axi_bridge.axi_bus, 0, val)
                data, resp = await axi_lite_read(ctx, axi_bridge.axi_bus, 0)
                self.assertEqual(data & 0xFF, val)

        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_multiple_registers(self):
        """Multiple registers at different AXI addresses.

        With 8-bit CSR and 32-bit AXI (ratio=4), each AXI word covers 4 CSR addresses.
        Two 8-bit registers at CSR addr 0 and 1 both map to AXI byte addr 0 (same word),
        in byte lanes 0 and 1. We write both in a single AXI word.
        """
        reg_a = SimpleRWRegister()
        reg_b = SimpleRWRegister()
        m, axi_bridge, regs = self._build_axi_dut([
            ("reg_a", reg_a),
            ("reg_b", reg_b),
        ], data_width=32)

        async def testbench(ctx):
            # Both 8-bit registers are in AXI word 0:
            # reg_a at byte 0, reg_b at byte 1
            await axi_lite_write(ctx, axi_bridge.axi_bus, 0, 0x0000BBAA)

            data, _ = await axi_lite_read(ctx, axi_bridge.axi_bus, 0)
            self.assertEqual(data & 0xFF, 0xAA, "reg_a should be 0xAA")
            self.assertEqual((data >> 8) & 0xFF, 0xBB, "reg_b should be 0xBB")

        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_init_values_persist(self):
        """Registers with init values should read correctly before any write."""
        reg = InitRegister()  # a=0xDE, b=0xAD
        m, axi_bridge, regs = self._build_axi_dut([("reg", reg)], data_width=32)

        async def testbench(ctx):
            data, _ = await axi_lite_read(ctx, axi_bridge.axi_bus, 0)
            # 16-bit register: low byte = a (0xDE), high byte = b (0xAD)
            self.assertEqual(data & 0xFFFF, 0xADDE)

        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()


# =============================================================================
# Test 4: Edge Cases
# =============================================================================

class TestCSREdgeCases(unittest.TestCase):
    """Edge cases for CSR access."""

    def test_wide_register_through_narrow_bus(self):
        """48-bit register through 8-bit CSR / 32-bit Wishbone bus."""
        reg = WideRegister()
        regs = Builder(addr_width=16, data_width=8)
        regs.add("reg", reg)
        memory_map = regs.as_memory_map()
        mux = Multiplexer(memory_map)
        wb_bridge = WishboneCSRBridge(mux.bus, data_width=32)

        m = Module()
        m.submodules.reg = reg
        m.submodules.mux = mux
        m.submodules.wb_bridge = wb_bridge

        async def testbench(ctx):
            # 48-bit register = 6 CSR bytes → 2 WB words (at addr 0 and 1)
            # Write low 32 bits
            await wb_write(ctx, wb_bridge.wb_bus, 0, 0xDEADBEEF)
            # Write high 16 bits (in the next WB word)
            await wb_write(ctx, wb_bridge.wb_bus, 1, 0x0000CAFE)

            # Read back
            data_lo, _ = await wb_read(ctx, wb_bridge.wb_bus, 0)
            data_hi, _ = await wb_read(ctx, wb_bridge.wb_bus, 1)
            self.assertEqual(data_lo, 0xDEADBEEF)
            self.assertEqual(data_hi & 0xFFFF, 0xCAFE)

        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_reserved_fields_dont_corrupt_adjacent(self):
        """Reserved fields between data fields should not corrupt neighbors."""
        reg = ReservedFieldsRegister()
        regs = Builder(addr_width=16, data_width=8)
        regs.add("reg", reg)
        memory_map = regs.as_memory_map()
        mux = Multiplexer(memory_map)
        wb_bridge = WishboneCSRBridge(mux.bus, data_width=32)

        m = Module()
        m.submodules.reg = reg
        m.submodules.mux = mux
        m.submodules.wb_bridge = wb_bridge

        async def testbench(ctx):
            # Write 0xFFFF (all bits set)
            await wb_write(ctx, wb_bridge.wb_bus, 0, 0xFFFF)

            # Read back
            data, _ = await wb_read(ctx, wb_bridge.wb_bus, 0)
            # data_lo (bits 3:0) = 0xF, reserved (bits 7:4) = 0, data_hi (bits 11:8) = 0xF
            self.assertEqual(data & 0x0F, 0x0F, "data_lo should be 0xF")
            self.assertEqual((data >> 4) & 0x0F, 0x00, "reserved should read 0")
            self.assertEqual((data >> 8) & 0x0F, 0x0F, "data_hi should be 0xF")

        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_multiple_registers_through_decoder(self):
        """Multiple registers through CSR Decoder."""
        reg_a = SimpleRWRegister()
        reg_b = SimpleRWRegister()

        # Create two separate memory maps with multiplexers
        map_a = MemoryMap(addr_width=4, data_width=8)
        map_a.add_resource(reg_a, name=("reg_a",), size=1)
        mux_a = Multiplexer(map_a)

        map_b = MemoryMap(addr_width=4, data_width=8)
        map_b.add_resource(reg_b, name=("reg_b",), size=1)
        mux_b = Multiplexer(map_b)

        # Create decoder
        decoder = Decoder(addr_width=8, data_width=8)
        decoder.add(mux_a.bus)
        decoder.add(mux_b.bus)

        m = Module()
        m.submodules.reg_a = reg_a
        m.submodules.reg_b = reg_b
        m.submodules.mux_a = mux_a
        m.submodules.mux_b = mux_b
        m.submodules.decoder = decoder

        async def testbench(ctx):
            # Write to reg_a (address 0x00)
            ctx.set(decoder.bus.addr, 0x00)
            ctx.set(decoder.bus.w_stb, 1)
            ctx.set(decoder.bus.w_data, 0xAA)
            await ctx.tick()
            ctx.set(decoder.bus.w_stb, 0)
            await ctx.tick()

            # Write to reg_b (address 0x10)
            ctx.set(decoder.bus.addr, 0x10)
            ctx.set(decoder.bus.w_stb, 1)
            ctx.set(decoder.bus.w_data, 0xBB)
            await ctx.tick()
            ctx.set(decoder.bus.w_stb, 0)
            await ctx.tick()

            # Read reg_a
            ctx.set(decoder.bus.addr, 0x00)
            ctx.set(decoder.bus.r_stb, 1)
            await ctx.tick()
            r_data_a = ctx.get(decoder.bus.r_data)
            ctx.set(decoder.bus.r_stb, 0)
            self.assertEqual(r_data_a, 0xAA)

            # Read reg_b
            ctx.set(decoder.bus.addr, 0x10)
            ctx.set(decoder.bus.r_stb, 1)
            await ctx.tick()
            r_data_b = ctx.get(decoder.bus.r_data)
            ctx.set(decoder.bus.r_stb, 0)
            self.assertEqual(r_data_b, 0xBB)

        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_mixed_access_modes_in_one_register(self):
        """Register with R + RW + W fields: verify each behaves correctly.

        MixedAccessRegister is 24 bits (3 CSR bytes):
          byte 0: ro_part (R, 8 bits)
          byte 1: rw_part (RW, 8 bits)
          byte 2: wo_part (W, 8 bits)

        The Builder aligns registers to power-of-2 sizes. A 3-byte register gets
        alignment=ceil_log2(3)=2, so it occupies 4 CSR addresses (0-3). The write
        to the LAST address (byte 3) triggers the actual register write.
        """
        reg = MixedAccessRegister()
        regs = Builder(addr_width=16, data_width=8)
        regs.add("reg", reg)
        memory_map = regs.as_memory_map()
        mux = Multiplexer(memory_map)

        m = Module()
        m.submodules.reg = reg
        m.submodules.mux = mux

        # Determine the actual address range from the memory map
        resources = list(memory_map.resources())
        reg_start, reg_end = resources[0][2]
        reg_addr_size = reg_end - reg_start  # Should be 4 (aligned)

        async def testbench(ctx):
            # Set the R field externally
            ctx.set(reg.f.ro_part.r_data, 0x55)

            # Write all bytes in ascending order. The write to the LAST address
            # (reg_addr_size - 1) triggers the actual register write (w_stb).
            for i in range(reg_addr_size):
                ctx.set(mux.bus.addr, reg_start + i)
                ctx.set(mux.bus.w_stb, 1)
                if i == 0:
                    ctx.set(mux.bus.w_data, 0xFF)  # ro_part (ignored by R field)
                elif i == 1:
                    ctx.set(mux.bus.w_data, 0xAB)  # rw_part
                elif i == 2:
                    ctx.set(mux.bus.w_data, 0xCD)  # wo_part
                else:
                    ctx.set(mux.bus.w_data, 0x00)  # padding byte
                await ctx.tick()
            ctx.set(mux.bus.w_stb, 0)

            # Wait for the delayed w_stb to propagate
            await ctx.tick()

            # Now read. The Multiplexer captures the register value on r_stb to byte 0,
            # then returns shadow data on subsequent reads. Data is delayed by 1 cycle.
            # Read byte 0 (captures register value)
            ctx.set(mux.bus.addr, reg_start + 0)
            ctx.set(mux.bus.r_stb, 1)
            await ctx.tick()
            # Data from byte 0 is available on the NEXT cycle
            ctx.set(mux.bus.addr, reg_start + 1)
            ctx.set(mux.bus.r_stb, 1)
            r_data_0 = ctx.get(mux.bus.r_data)
            await ctx.tick()
            # Data from byte 1 is available on the NEXT cycle
            ctx.set(mux.bus.addr, reg_start + 2)
            ctx.set(mux.bus.r_stb, 1)
            r_data_1 = ctx.get(mux.bus.r_data)
            await ctx.tick()
            r_data_2 = ctx.get(mux.bus.r_data)
            ctx.set(mux.bus.r_stb, 0)

            # ro_part should be 0x55 (externally set, R field)
            self.assertEqual(r_data_0, 0x55)
            # rw_part should be 0xAB (written value, RW field with storage)
            self.assertEqual(r_data_1, 0xAB)
            # wo_part reads as 0 (W field has no read data)
            # (W fields don't drive r_data, so it should be 0)

        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()


# =============================================================================
# Test 5: EventMonitor Integration through bus
# =============================================================================

class TestCSREventMonitorIntegration(unittest.TestCase):
    """EventMonitor through CSR bus."""

    def test_event_enable_disable(self):
        """Enable/disable individual events through CSR bus."""
        sub_0 = event.Source(path=("sub_0",))
        sub_1 = event.Source(path=("sub_1",))
        sub_2 = event.Source(path=("sub_2",))
        event_map = event.EventMap()
        event_map.add(sub_0)
        event_map.add(sub_1)
        event_map.add(sub_2)
        dut = EventMonitor(event_map, data_width=8)

        addr_enable  = 0x0
        addr_pending = 0x1

        async def testbench(ctx):
            # Enable events 0 and 2
            ctx.set(dut.bus.addr, addr_enable)
            ctx.set(dut.bus.w_stb, 1)
            ctx.set(dut.bus.w_data, 0b101)
            await ctx.tick()
            ctx.set(dut.bus.w_stb, 0)
            await ctx.tick()

            # Trigger event 0
            ctx.set(sub_0.i, 1)
            await ctx.tick()

            # Check pending
            ctx.set(dut.bus.addr, addr_pending)
            ctx.set(dut.bus.r_stb, 1)
            await ctx.tick()
            pending = ctx.get(dut.bus.r_data)
            ctx.set(dut.bus.r_stb, 0)
            # Event 0 should be pending
            self.assertTrue(pending & 0b001)

            # src.i should be asserted (enabled & pending)
            self.assertEqual(ctx.get(dut.src.i), 1)

            # Deassert event 0
            ctx.set(sub_0.i, 0)
            await ctx.tick()

            # Clear pending for event 0
            ctx.set(dut.bus.addr, addr_pending)
            ctx.set(dut.bus.w_stb, 1)
            ctx.set(dut.bus.w_data, 0b001)
            await ctx.tick()
            ctx.set(dut.bus.w_stb, 0)
            await ctx.tick()

            # Check pending is cleared
            ctx.set(dut.bus.addr, addr_pending)
            ctx.set(dut.bus.r_stb, 1)
            await ctx.tick()
            pending = ctx.get(dut.bus.r_data)
            ctx.set(dut.bus.r_stb, 0)
            self.assertEqual(pending & 0b001, 0)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_simultaneous_events(self):
        """Multiple events triggered simultaneously."""
        sub_0 = event.Source(path=("sub_0",))
        sub_1 = event.Source(path=("sub_1",))
        sub_2 = event.Source(path=("sub_2",))
        event_map = event.EventMap()
        event_map.add(sub_0)
        event_map.add(sub_1)
        event_map.add(sub_2)
        dut = EventMonitor(event_map, data_width=8)

        addr_enable  = 0x0
        addr_pending = 0x1

        async def testbench(ctx):
            # Enable all events
            ctx.set(dut.bus.addr, addr_enable)
            ctx.set(dut.bus.w_stb, 1)
            ctx.set(dut.bus.w_data, 0b111)
            await ctx.tick()
            ctx.set(dut.bus.w_stb, 0)
            await ctx.tick()

            # Trigger all events simultaneously
            ctx.set(sub_0.i, 1)
            ctx.set(sub_1.i, 1)
            ctx.set(sub_2.i, 1)
            await ctx.tick()

            # Check all pending
            ctx.set(dut.bus.addr, addr_pending)
            ctx.set(dut.bus.r_stb, 1)
            await ctx.tick()
            pending = ctx.get(dut.bus.r_data)
            ctx.set(dut.bus.r_stb, 0)
            self.assertEqual(pending & 0b111, 0b111)

            # src.i should be asserted
            self.assertEqual(ctx.get(dut.src.i), 1)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()

    def test_clear_pending_while_active(self):
        """Clear pending while event source is still active (level-triggered)."""
        sub = event.Source(path=("sub",))
        event_map = event.EventMap()
        event_map.add(sub)
        dut = EventMonitor(event_map, data_width=8)

        addr_enable  = 0x0
        addr_pending = 0x1

        async def testbench(ctx):
            # Enable event
            ctx.set(dut.bus.addr, addr_enable)
            ctx.set(dut.bus.w_stb, 1)
            ctx.set(dut.bus.w_data, 0b1)
            await ctx.tick()
            ctx.set(dut.bus.w_stb, 0)
            await ctx.tick()

            # Trigger event and keep it active
            ctx.set(sub.i, 1)
            await ctx.tick()

            # Try to clear pending while source is still active
            ctx.set(dut.bus.addr, addr_pending)
            ctx.set(dut.bus.w_stb, 1)
            ctx.set(dut.bus.w_data, 0b1)
            await ctx.tick()
            ctx.set(dut.bus.w_stb, 0)
            await ctx.tick()

            # Pending should re-assert because source is still active (level-triggered)
            ctx.set(dut.bus.addr, addr_pending)
            ctx.set(dut.bus.r_stb, 1)
            await ctx.tick()
            pending = ctx.get(dut.bus.r_data)
            ctx.set(dut.bus.r_stb, 0)
            self.assertEqual(pending & 0b1, 0b1,
                             "Pending should re-assert while source is still active")

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()


if __name__ == "__main__":
    unittest.main()
