"""Tests for enhanced SoC builder features: bridges, DMA channels, interrupt controllers."""

import unittest

from amaranth_soc import BusStandard
from amaranth_soc.soc.builder import SoCBuilder


class TestSoCBuilderAddBridge(unittest.TestCase):
    """test_soc_builder_add_bridge — Test bridge creation between Wishbone and AXI4-Lite."""

    def test_add_bridge_wb_to_axi4lite(self):
        builder = SoCBuilder(
            bus_standard=BusStandard.WISHBONE,
            bus_addr_width=14,
            bus_data_width=32,
        )
        bridge = builder.add_bridge(src_type="wishbone", dst_type="axi4lite")
        # The bridge should be a WishboneToAXI4Lite instance
        from amaranth_soc.bridge.wb_to_axi import WishboneToAXI4Lite
        self.assertIsInstance(bridge, WishboneToAXI4Lite)

    def test_add_bridge_axi4lite_to_wb(self):
        builder = SoCBuilder(
            bus_standard=BusStandard.AXI4_LITE,
            bus_addr_width=16,
            bus_data_width=32,
        )
        bridge = builder.add_bridge(src_type="axi4lite", dst_type="wishbone")
        from amaranth_soc.bridge.axi_to_wb import AXI4LiteToWishbone
        self.assertIsInstance(bridge, AXI4LiteToWishbone)

    def test_add_bridge_same_type_returns_none(self):
        """Same-type bridge returns the original interface (None in this case)."""
        builder = SoCBuilder(
            bus_standard=BusStandard.WISHBONE,
            bus_addr_width=14,
            bus_data_width=32,
        )
        result = builder.add_bridge(src_type="wishbone", dst_type="wishbone")
        # Same standard → no bridge needed, returns None (the interface arg)
        self.assertIsNone(result)

    def test_add_bridge_custom_widths(self):
        builder = SoCBuilder(
            bus_standard=BusStandard.WISHBONE,
            bus_addr_width=14,
            bus_data_width=32,
        )
        bridge = builder.add_bridge(
            src_type="wishbone", dst_type="axi4lite",
            addr_width=20, data_width=64,
        )
        from amaranth_soc.bridge.wb_to_axi import WishboneToAXI4Lite
        self.assertIsInstance(bridge, WishboneToAXI4Lite)
        self.assertEqual(bridge.addr_width, 20)
        self.assertEqual(bridge.data_width, 64)

    def test_add_bridge_invalid_src_type(self):
        builder = SoCBuilder(
            bus_standard=BusStandard.WISHBONE,
            bus_addr_width=14,
            bus_data_width=32,
        )
        with self.assertRaisesRegex(ValueError, "Unknown source bus type"):
            builder.add_bridge(src_type="invalid", dst_type="axi4lite")

    def test_add_bridge_invalid_dst_type(self):
        builder = SoCBuilder(
            bus_standard=BusStandard.WISHBONE,
            bus_addr_width=14,
            bus_data_width=32,
        )
        with self.assertRaisesRegex(ValueError, "Unknown destination bus type"):
            builder.add_bridge(src_type="wishbone", dst_type="invalid")

    def test_bridges_property(self):
        builder = SoCBuilder(
            bus_standard=BusStandard.WISHBONE,
            bus_addr_width=14,
            bus_data_width=32,
        )
        self.assertEqual(builder.bridges, [])
        builder.add_bridge(src_type="wishbone", dst_type="axi4lite")
        self.assertEqual(len(builder.bridges), 1)
        self.assertEqual(builder.bridges[0]["src_type"], BusStandard.WISHBONE)
        self.assertEqual(builder.bridges[0]["dst_type"], BusStandard.AXI4_LITE)

    def test_add_bridge_axi4_hyphen_lite_alias(self):
        """The 'axi4-lite' alias should also work."""
        builder = SoCBuilder(
            bus_standard=BusStandard.WISHBONE,
            bus_addr_width=14,
            bus_data_width=32,
        )
        bridge = builder.add_bridge(src_type="wishbone", dst_type="axi4-lite")
        from amaranth_soc.bridge.wb_to_axi import WishboneToAXI4Lite
        self.assertIsInstance(bridge, WishboneToAXI4Lite)


class TestSoCBuilderAddDMAChannel(unittest.TestCase):
    """test_soc_builder_add_dma_channel — Test DMA channel registration."""

    def test_add_dma_channel_basic(self):
        builder = SoCBuilder(
            bus_standard=BusStandard.WISHBONE,
            bus_addr_width=14,
            bus_data_width=32,
        )
        result = builder.add_dma_channel(name="dma0")
        self.assertIs(result, builder)  # method chaining
        self.assertEqual(len(builder.dma_channels), 1)
        self.assertEqual(builder.dma_channels[0]["name"], "dma0")
        self.assertEqual(builder.dma_channels[0]["addr_width"], 32)
        self.assertEqual(builder.dma_channels[0]["data_width"], 32)
        self.assertEqual(builder.dma_channels[0]["max_burst_len"], 16)

    def test_add_dma_channel_custom_params(self):
        builder = SoCBuilder(
            bus_standard=BusStandard.AXI4_LITE,
            bus_addr_width=16,
            bus_data_width=32,
        )
        builder.add_dma_channel(
            name="dma_fast",
            addr_width=64,
            data_width=128,
            max_burst_len=256,
        )
        ch = builder.dma_channels[0]
        self.assertEqual(ch["addr_width"], 64)
        self.assertEqual(ch["data_width"], 128)
        self.assertEqual(ch["max_burst_len"], 256)

    def test_add_multiple_dma_channels(self):
        builder = SoCBuilder(
            bus_standard=BusStandard.WISHBONE,
            bus_addr_width=14,
            bus_data_width=32,
        )
        builder.add_dma_channel(name="dma0")
        builder.add_dma_channel(name="dma1")
        self.assertEqual(len(builder.dma_channels), 2)

    def test_add_dma_channel_duplicate_name(self):
        builder = SoCBuilder(
            bus_standard=BusStandard.WISHBONE,
            bus_addr_width=14,
            bus_data_width=32,
        )
        builder.add_dma_channel(name="dma0")
        with self.assertRaisesRegex(ValueError, "already registered"):
            builder.add_dma_channel(name="dma0")

    def test_add_dma_channel_empty_name(self):
        builder = SoCBuilder(
            bus_standard=BusStandard.WISHBONE,
            bus_addr_width=14,
            bus_data_width=32,
        )
        with self.assertRaisesRegex(ValueError, "non-empty string"):
            builder.add_dma_channel(name="")

    def test_add_dma_channel_invalid_addr_width(self):
        builder = SoCBuilder(
            bus_standard=BusStandard.WISHBONE,
            bus_addr_width=14,
            bus_data_width=32,
        )
        with self.assertRaisesRegex(ValueError, "addr_width must be a positive integer"):
            builder.add_dma_channel(name="dma0", addr_width=0)

    def test_dma_channels_empty_initially(self):
        builder = SoCBuilder(
            bus_standard=BusStandard.WISHBONE,
            bus_addr_width=14,
            bus_data_width=32,
        )
        self.assertEqual(builder.dma_channels, [])


class TestSoCBuilderAddInterruptController(unittest.TestCase):
    """test_soc_builder_add_interrupt_controller — Test interrupt controller registration."""

    def test_add_interrupt_controller_basic(self):
        builder = SoCBuilder(
            bus_standard=BusStandard.WISHBONE,
            bus_addr_width=14,
            bus_data_width=32,
        )
        result = builder.add_interrupt_controller(n_sources=16)
        self.assertIs(result, builder)  # method chaining
        self.assertEqual(len(builder.interrupt_controllers), 1)
        self.assertEqual(builder.interrupt_controllers[0]["n_sources"], 16)
        self.assertFalse(builder.interrupt_controllers[0]["edge_triggered"])

    def test_add_interrupt_controller_edge_triggered(self):
        builder = SoCBuilder(
            bus_standard=BusStandard.AXI4_LITE,
            bus_addr_width=16,
            bus_data_width=32,
        )
        builder.add_interrupt_controller(n_sources=32, edge_triggered=True)
        self.assertTrue(builder.interrupt_controllers[0]["edge_triggered"])

    def test_add_multiple_interrupt_controllers(self):
        builder = SoCBuilder(
            bus_standard=BusStandard.WISHBONE,
            bus_addr_width=14,
            bus_data_width=32,
        )
        builder.add_interrupt_controller(n_sources=8)
        builder.add_interrupt_controller(n_sources=16, edge_triggered=True)
        self.assertEqual(len(builder.interrupt_controllers), 2)

    def test_add_interrupt_controller_invalid_n_sources(self):
        builder = SoCBuilder(
            bus_standard=BusStandard.WISHBONE,
            bus_addr_width=14,
            bus_data_width=32,
        )
        with self.assertRaisesRegex(ValueError, "n_sources must be a positive integer"):
            builder.add_interrupt_controller(n_sources=0)

    def test_add_interrupt_controller_negative_n_sources(self):
        builder = SoCBuilder(
            bus_standard=BusStandard.WISHBONE,
            bus_addr_width=14,
            bus_data_width=32,
        )
        with self.assertRaisesRegex(ValueError, "n_sources must be a positive integer"):
            builder.add_interrupt_controller(n_sources=-1)

    def test_interrupt_controllers_empty_initially(self):
        builder = SoCBuilder(
            bus_standard=BusStandard.WISHBONE,
            bus_addr_width=14,
            bus_data_width=32,
        )
        self.assertEqual(builder.interrupt_controllers, [])


class TestSoCBuilderEnhancedBuildRegression(unittest.TestCase):
    """Verify that adding bridges/DMA/intc doesn't break the existing build flow."""

    def test_build_still_works_after_add_bridge(self):
        builder = SoCBuilder(
            bus_standard=BusStandard.WISHBONE,
            bus_addr_width=14,
            bus_data_width=32,
        )
        builder.add_rom(size=1024, init=[0] * 256)
        builder.add_bridge(src_type="wishbone", dst_type="axi4lite")
        soc = builder.build()

        from amaranth.back.rtlil import convert
        convert(soc)

    def test_build_still_works_after_add_dma(self):
        builder = SoCBuilder(
            bus_standard=BusStandard.AXI4_LITE,
            bus_addr_width=16,
            bus_data_width=32,
        )
        builder.add_rom(size=1024, init=[0] * 256)
        builder.add_dma_channel(name="dma0")
        soc = builder.build()

        from amaranth.back.rtlil import convert
        convert(soc)

    def test_build_still_works_after_add_intc(self):
        builder = SoCBuilder(
            bus_standard=BusStandard.WISHBONE,
            bus_addr_width=14,
            bus_data_width=32,
        )
        builder.add_rom(size=1024, init=[0] * 256)
        builder.add_interrupt_controller(n_sources=8)
        soc = builder.build()

        from amaranth.back.rtlil import convert
        convert(soc)


if __name__ == "__main__":
    unittest.main()
