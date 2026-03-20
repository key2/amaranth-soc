"""Tests for SoC handler classes and builder regression."""

import unittest

from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out

from amaranth_soc import BusStandard
from amaranth_soc.soc.bus_handler import (
    BusHandler, AXI4LiteBusHandler, WishboneBusHandler,
)
from amaranth_soc.soc.csr_handler import CSRHandler
from amaranth_soc.soc.irq_handler import IRQHandler
from amaranth_soc.soc.builder import SoCBuilder, SoC


class TestBusHandlerBase(unittest.TestCase):
    """Test BusHandler ABC validation."""

    def test_addr_width_must_be_positive(self):
        with self.assertRaisesRegex(ValueError, "addr_width must be a positive integer"):
            AXI4LiteBusHandler(addr_width=0, data_width=32)

    def test_data_width_must_be_positive(self):
        with self.assertRaisesRegex(ValueError, "data_width must be a positive integer"):
            AXI4LiteBusHandler(addr_width=16, data_width=0)

    def test_cannot_instantiate_abc(self):
        with self.assertRaises(TypeError):
            BusHandler(addr_width=16, data_width=32)


class TestAXI4LiteBusHandler(unittest.TestCase):
    """Test AXI4LiteBusHandler."""

    def test_construction(self):
        handler = AXI4LiteBusHandler(addr_width=16, data_width=32)
        self.assertEqual(handler.addr_width, 16)
        self.assertEqual(handler.data_width, 32)

    def test_bus_signature(self):
        from amaranth_soc.axi.bus import AXI4LiteSignature
        handler = AXI4LiteBusHandler(addr_width=16, data_width=32)
        sig = handler.bus_signature()
        self.assertIsInstance(sig, AXI4LiteSignature)
        self.assertEqual(sig.addr_width, 16)
        self.assertEqual(sig.data_width, 32)

    def test_create_decoder(self):
        from amaranth_soc.axi.decoder import AXI4LiteDecoder
        handler = AXI4LiteBusHandler(addr_width=16, data_width=32)
        decoder = handler.create_decoder()
        self.assertIsInstance(decoder, AXI4LiteDecoder)

    def test_create_sram_readonly(self):
        from amaranth_soc.axi.sram import AXI4LiteSRAM
        handler = AXI4LiteBusHandler(addr_width=16, data_width=32)
        sram = handler.create_sram(size=1024, writable=False)
        self.assertIsInstance(sram, AXI4LiteSRAM)
        self.assertEqual(sram.size, 1024)
        self.assertFalse(sram.writable)

    def test_create_sram_writable(self):
        from amaranth_soc.axi.sram import AXI4LiteSRAM
        handler = AXI4LiteBusHandler(addr_width=16, data_width=32)
        sram = handler.create_sram(size=256, writable=True)
        self.assertIsInstance(sram, AXI4LiteSRAM)
        self.assertTrue(sram.writable)

    def test_get_sram_bus(self):
        handler = AXI4LiteBusHandler(addr_width=16, data_width=32)
        sram = handler.create_sram(size=256, writable=True)
        bus = handler.get_sram_bus(sram)
        self.assertIs(bus, sram.bus)


class TestWishboneBusHandler(unittest.TestCase):
    """Test WishboneBusHandler."""

    def test_construction(self):
        handler = WishboneBusHandler(addr_width=14, data_width=32)
        self.assertEqual(handler.addr_width, 14)
        self.assertEqual(handler.data_width, 32)
        self.assertIsNone(handler.granularity)
        self.assertEqual(handler.features, frozenset())

    def test_construction_with_granularity(self):
        handler = WishboneBusHandler(addr_width=14, data_width=32, granularity=8)
        self.assertEqual(handler.granularity, 8)

    def test_bus_signature(self):
        from amaranth_soc.wishbone.bus import Signature as WBSignature
        handler = WishboneBusHandler(addr_width=14, data_width=32)
        sig = handler.bus_signature()
        self.assertIsInstance(sig, WBSignature)
        self.assertEqual(sig.addr_width, 14)
        self.assertEqual(sig.data_width, 32)

    def test_create_decoder(self):
        from amaranth_soc.wishbone.bus import Decoder as WBDecoder
        handler = WishboneBusHandler(addr_width=14, data_width=32)
        decoder = handler.create_decoder()
        self.assertIsInstance(decoder, WBDecoder)

    def test_create_sram(self):
        from amaranth_soc.wishbone.sram import WishboneSRAM
        handler = WishboneBusHandler(addr_width=14, data_width=32)
        sram = handler.create_sram(size=1024, writable=True)
        self.assertIsInstance(sram, WishboneSRAM)
        self.assertEqual(sram.size, 1024)
        self.assertTrue(sram.writable)

    def test_get_sram_bus(self):
        handler = WishboneBusHandler(addr_width=14, data_width=32)
        sram = handler.create_sram(size=256, writable=True)
        bus = handler.get_sram_bus(sram)
        self.assertIs(bus, sram.wb_bus)


class TestCSRHandler(unittest.TestCase):
    """Test CSRHandler."""

    def test_no_peripherals_initially(self):
        handler = CSRHandler(
            csr_addr_width=14,
            csr_data_width=8,
            bus_standard=BusStandard.AXI4_LITE,
            bus_data_width=32,
        )
        self.assertFalse(handler.has_peripherals)

    def test_add_peripheral(self):
        handler = CSRHandler(
            csr_addr_width=14,
            csr_data_width=8,
            bus_standard=BusStandard.AXI4_LITE,
            bus_data_width=32,
        )
        # Use a mock-like object
        class FakePeripheral:
            bus = None
        periph = FakePeripheral()
        handler.add_peripheral(periph, name="test")
        self.assertTrue(handler.has_peripherals)

    def test_has_peripherals_after_multiple_adds(self):
        handler = CSRHandler(
            csr_addr_width=14,
            csr_data_width=8,
            bus_standard=BusStandard.WISHBONE,
            bus_data_width=32,
        )
        class FakePeripheral:
            bus = None
        handler.add_peripheral(FakePeripheral(), name="a")
        handler.add_peripheral(FakePeripheral(), name="b")
        self.assertTrue(handler.has_peripherals)


class TestIRQHandler(unittest.TestCase):
    """Test IRQHandler."""

    def test_construction(self):
        handler = IRQHandler(n_irqs=16)
        self.assertEqual(handler.n_irqs, 16)

    def test_n_irqs_must_be_positive(self):
        with self.assertRaisesRegex(ValueError, "n_irqs must be a positive integer"):
            IRQHandler(n_irqs=0)

    def test_n_irqs_must_be_int(self):
        with self.assertRaisesRegex(ValueError, "n_irqs must be a positive integer"):
            IRQHandler(n_irqs="foo")

    def test_assign_irq_valid(self):
        handler = IRQHandler(n_irqs=8)
        class FakePeripheral:
            irq = Signal()
        handler.assign_irq(FakePeripheral(), irq_num=0)
        handler.assign_irq(FakePeripheral(), irq_num=7)

    def test_assign_irq_out_of_range_high(self):
        handler = IRQHandler(n_irqs=8)
        class FakePeripheral:
            irq = Signal()
        with self.assertRaisesRegex(ValueError, r"IRQ number must be in range \[0, 8\)"):
            handler.assign_irq(FakePeripheral(), irq_num=8)

    def test_assign_irq_out_of_range_negative(self):
        handler = IRQHandler(n_irqs=8)
        class FakePeripheral:
            irq = Signal()
        with self.assertRaisesRegex(ValueError, r"IRQ number must be in range \[0, 8\)"):
            handler.assign_irq(FakePeripheral(), irq_num=-1)

    def test_assign_irq_not_int(self):
        handler = IRQHandler(n_irqs=8)
        class FakePeripheral:
            irq = Signal()
        with self.assertRaisesRegex(ValueError, r"IRQ number must be in range"):
            handler.assign_irq(FakePeripheral(), irq_num="foo")


class TestSoCBuilderRegression(unittest.TestCase):
    """Verify the existing AXI4-Lite SoC builder still works after refactoring."""

    def test_builder_basic_construction(self):
        builder = SoCBuilder(
            bus_standard=BusStandard.AXI4_LITE,
            bus_addr_width=16,
            bus_data_width=32,
        )
        self.assertEqual(builder.bus_standard, BusStandard.AXI4_LITE)
        self.assertEqual(builder.bus_addr_width, 16)
        self.assertEqual(builder.bus_data_width, 32)
        self.assertEqual(builder.csr_data_width, 8)
        self.assertEqual(builder.csr_addr_width, 14)
        self.assertEqual(builder.n_irqs, 32)

    def test_builder_invalid_bus_standard(self):
        with self.assertRaisesRegex(TypeError, "bus_standard must be a BusStandard"):
            SoCBuilder(
                bus_standard="invalid",
                bus_addr_width=16,
                bus_data_width=32,
            )

    def test_build_axi4_lite_rom_only(self):
        """Build an AXI4-Lite SoC with ROM only and verify it elaborates."""
        builder = SoCBuilder(
            bus_standard=BusStandard.AXI4_LITE,
            bus_addr_width=16,
            bus_data_width=32,
        )
        builder.add_rom(size=1024, init=[0] * 256)
        soc = builder.build()

        self.assertIsInstance(soc, SoC)
        self.assertEqual(soc.bus_standard, BusStandard.AXI4_LITE)

        # Verify it can elaborate without errors
        from amaranth.back.rtlil import convert
        convert(soc)

    def test_build_axi4_lite_rom_and_ram(self):
        """Build an AXI4-Lite SoC with ROM and RAM."""
        builder = SoCBuilder(
            bus_standard=BusStandard.AXI4_LITE,
            bus_addr_width=16,
            bus_data_width=32,
        )
        builder.add_rom(size=1024, init=[0] * 256)
        builder.add_ram(size=2048)
        soc = builder.build()

        from amaranth.back.rtlil import convert
        convert(soc)

    def test_soc_has_handler_properties(self):
        """Verify the SoC exposes handler properties."""
        builder = SoCBuilder(
            bus_standard=BusStandard.AXI4_LITE,
            bus_addr_width=16,
            bus_data_width=32,
        )
        soc = builder.build()

        self.assertIsInstance(soc.bus_handler, AXI4LiteBusHandler)
        self.assertIsInstance(soc.csr_handler, CSRHandler)
        self.assertIsInstance(soc.irq_handler, IRQHandler)

    def test_build_wishbone_soc(self):
        """Build a Wishbone SoC with ROM and RAM."""
        builder = SoCBuilder(
            bus_standard=BusStandard.WISHBONE,
            bus_addr_width=14,
            bus_data_width=32,
        )
        builder.add_rom(size=1024, init=[0] * 256)
        builder.add_ram(size=2048)
        soc = builder.build()

        self.assertIsInstance(soc, SoC)
        self.assertEqual(soc.bus_standard, BusStandard.WISHBONE)
        self.assertIsInstance(soc.bus_handler, WishboneBusHandler)

        from amaranth.back.rtlil import convert
        convert(soc)


if __name__ == "__main__":
    unittest.main()
