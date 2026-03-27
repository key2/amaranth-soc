"""Tests for cross-bus bridges: WishboneToAXI4Lite, AXI4LiteToWishbone, AXI4ToAXI4Lite."""
import unittest
from amaranth.back.rtlil import convert

from amaranth_soc.bridge.wb_to_axi import WishboneToAXI4Lite
from amaranth_soc.bridge.axi_to_wb import AXI4LiteToWishbone
from amaranth_soc.axi.adapter import AXI4ToAXI4Lite


# =============================================================================
# WishboneToAXI4Lite tests
# =============================================================================

class TestWishboneToAXI4LiteConstruction(unittest.TestCase):
    """Test WishboneToAXI4Lite construction and parameter validation."""

    def test_create_basic(self):
        """Construct with basic valid parameters."""
        bridge = WishboneToAXI4Lite(addr_width=30, data_width=32)
        self.assertIsNotNone(bridge)
        self.assertEqual(bridge.addr_width, 30)
        self.assertEqual(bridge.data_width, 32)
        self.assertEqual(bridge.granularity, 8)

    def test_create_64bit(self):
        """Construct with 64-bit data width."""
        bridge = WishboneToAXI4Lite(addr_width=30, data_width=64)
        self.assertEqual(bridge.data_width, 64)

    def test_create_custom_granularity(self):
        """Construct with non-default granularity."""
        bridge = WishboneToAXI4Lite(addr_width=30, data_width=32, granularity=16)
        self.assertEqual(bridge.granularity, 16)

    def test_create_granularity_32(self):
        """Construct with granularity=32."""
        bridge = WishboneToAXI4Lite(addr_width=30, data_width=32, granularity=32)
        self.assertEqual(bridge.granularity, 32)

    def test_create_zero_addr_width(self):
        """Construct with addr_width=0 (edge case)."""
        bridge = WishboneToAXI4Lite(addr_width=0, data_width=32)
        self.assertEqual(bridge.addr_width, 0)

    def test_invalid_addr_width_negative(self):
        """Negative address width should raise TypeError."""
        with self.assertRaises(TypeError):
            WishboneToAXI4Lite(addr_width=-1, data_width=32)

    def test_invalid_addr_width_string(self):
        """String address width should raise TypeError."""
        with self.assertRaises(TypeError):
            WishboneToAXI4Lite(addr_width="30", data_width=32)

    def test_invalid_data_width_16(self):
        """Data width 16 should raise ValueError."""
        with self.assertRaises(ValueError):
            WishboneToAXI4Lite(addr_width=30, data_width=16)

    def test_invalid_data_width_128(self):
        """Data width 128 raises ValueError because Wishbone limits to 8/16/32/64."""
        with self.assertRaises(ValueError):
            WishboneToAXI4Lite(addr_width=30, data_width=128)

    def test_invalid_data_width_not_power_of_2(self):
        """Data width 48 (not power of 2) should raise ValueError."""
        with self.assertRaises(ValueError):
            WishboneToAXI4Lite(addr_width=30, data_width=48)

    def test_invalid_granularity(self):
        """Invalid granularity should raise ValueError."""
        with self.assertRaises(ValueError):
            WishboneToAXI4Lite(addr_width=30, data_width=32, granularity=4)

    def test_granularity_exceeds_data_width(self):
        """Granularity > data_width should raise ValueError."""
        with self.assertRaises(ValueError):
            WishboneToAXI4Lite(addr_width=30, data_width=32, granularity=64)


class TestWishboneToAXI4LiteElaboration(unittest.TestCase):
    """Test WishboneToAXI4Lite RTLIL elaboration."""

    def test_elaborate_32bit(self):
        """Elaborate with 32-bit data width."""
        bridge = WishboneToAXI4Lite(addr_width=30, data_width=32)
        rtlil = convert(bridge)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_64bit(self):
        """Elaborate with 64-bit data width."""
        bridge = WishboneToAXI4Lite(addr_width=30, data_width=64)
        rtlil = convert(bridge)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_granularity_16(self):
        """Elaborate with granularity=16."""
        bridge = WishboneToAXI4Lite(addr_width=30, data_width=32, granularity=16)
        rtlil = convert(bridge)
        self.assertGreater(len(rtlil), 0)


# =============================================================================
# AXI4LiteToWishbone tests
# =============================================================================

class TestAXI4LiteToWishboneConstruction(unittest.TestCase):
    """Test AXI4LiteToWishbone construction and parameter validation."""

    def test_create_basic(self):
        """Construct with basic valid parameters."""
        bridge = AXI4LiteToWishbone(addr_width=32, data_width=32)
        self.assertIsNotNone(bridge)
        self.assertEqual(bridge.addr_width, 32)
        self.assertEqual(bridge.data_width, 32)
        self.assertEqual(bridge.granularity, 8)

    def test_create_64bit(self):
        """Construct with 64-bit data width."""
        bridge = AXI4LiteToWishbone(addr_width=32, data_width=64)
        self.assertEqual(bridge.data_width, 64)

    def test_create_custom_granularity(self):
        """Construct with non-default granularity."""
        bridge = AXI4LiteToWishbone(addr_width=32, data_width=32, granularity=16)
        self.assertEqual(bridge.granularity, 16)

    def test_create_zero_addr_width(self):
        """Construct with addr_width=0 (edge case)."""
        bridge = AXI4LiteToWishbone(addr_width=0, data_width=32)
        self.assertEqual(bridge.addr_width, 0)

    def test_invalid_addr_width_negative(self):
        """Negative address width should raise TypeError."""
        with self.assertRaises(TypeError):
            AXI4LiteToWishbone(addr_width=-1, data_width=32)

    def test_invalid_addr_width_string(self):
        """String address width should raise TypeError."""
        with self.assertRaises(TypeError):
            AXI4LiteToWishbone(addr_width="32", data_width=32)

    def test_invalid_data_width_16(self):
        """Data width 16 should raise ValueError."""
        with self.assertRaises(ValueError):
            AXI4LiteToWishbone(addr_width=32, data_width=16)

    def test_invalid_data_width_128(self):
        """Data width 128 raises ValueError because Wishbone limits to 8/16/32/64."""
        with self.assertRaises(ValueError):
            AXI4LiteToWishbone(addr_width=32, data_width=128)

    def test_invalid_data_width_not_power_of_2(self):
        """Data width 48 (not power of 2) should raise ValueError."""
        with self.assertRaises(ValueError):
            AXI4LiteToWishbone(addr_width=32, data_width=48)

    def test_invalid_granularity(self):
        """Invalid granularity should raise ValueError."""
        with self.assertRaises(ValueError):
            AXI4LiteToWishbone(addr_width=32, data_width=32, granularity=4)

    def test_granularity_exceeds_data_width(self):
        """Granularity > data_width should raise ValueError."""
        with self.assertRaises(ValueError):
            AXI4LiteToWishbone(addr_width=32, data_width=32, granularity=64)


class TestAXI4LiteToWishboneElaboration(unittest.TestCase):
    """Test AXI4LiteToWishbone RTLIL elaboration."""

    def test_elaborate_32bit(self):
        """Elaborate with 32-bit data width."""
        bridge = AXI4LiteToWishbone(addr_width=32, data_width=32)
        rtlil = convert(bridge)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_64bit(self):
        """Elaborate with 64-bit data width."""
        bridge = AXI4LiteToWishbone(addr_width=32, data_width=64)
        rtlil = convert(bridge)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_granularity_16(self):
        """Elaborate with granularity=16."""
        bridge = AXI4LiteToWishbone(addr_width=32, data_width=32, granularity=16)
        rtlil = convert(bridge)
        self.assertGreater(len(rtlil), 0)


# =============================================================================
# AXI4ToAXI4Lite tests
# =============================================================================

class TestAXI4ToAXI4LiteConstruction(unittest.TestCase):
    """Test AXI4ToAXI4Lite construction and parameter validation."""

    def test_create_basic(self):
        """Construct with basic valid parameters."""
        adapter = AXI4ToAXI4Lite(addr_width=32, data_width=32, id_width=4)
        self.assertIsNotNone(adapter)
        self.assertEqual(adapter.addr_width, 32)
        self.assertEqual(adapter.data_width, 32)
        self.assertEqual(adapter.id_width, 4)

    def test_create_64bit(self):
        """Construct with 64-bit data width."""
        adapter = AXI4ToAXI4Lite(addr_width=32, data_width=64, id_width=4)
        self.assertEqual(adapter.data_width, 64)

    def test_create_no_id(self):
        """Construct with id_width=0."""
        adapter = AXI4ToAXI4Lite(addr_width=32, data_width=32, id_width=0)
        self.assertEqual(adapter.id_width, 0)

    def test_create_wide_id(self):
        """Construct with wide ID width."""
        adapter = AXI4ToAXI4Lite(addr_width=32, data_width=32, id_width=8)
        self.assertEqual(adapter.id_width, 8)

    def test_create_default_id_width(self):
        """Default id_width is 4."""
        adapter = AXI4ToAXI4Lite(addr_width=32, data_width=32)
        self.assertEqual(adapter.id_width, 4)

    def test_create_default_data_width(self):
        """Default data_width is 32."""
        adapter = AXI4ToAXI4Lite(addr_width=32)
        self.assertEqual(adapter.data_width, 32)

    def test_invalid_addr_width_zero(self):
        """Address width of 0 should raise TypeError."""
        with self.assertRaises(TypeError):
            AXI4ToAXI4Lite(addr_width=0, data_width=32)

    def test_invalid_addr_width_negative(self):
        """Negative address width should raise TypeError."""
        with self.assertRaises(TypeError):
            AXI4ToAXI4Lite(addr_width=-1, data_width=32)

    def test_invalid_addr_width_string(self):
        """String address width should raise TypeError."""
        with self.assertRaises(TypeError):
            AXI4ToAXI4Lite(addr_width="32", data_width=32)

    def test_invalid_data_width_16(self):
        """Data width 16 should raise ValueError."""
        with self.assertRaises(ValueError):
            AXI4ToAXI4Lite(addr_width=32, data_width=16)

    def test_valid_data_width_128(self):
        """Data width 128 should now be accepted (power of 2 >= 32)."""
        adapter = AXI4ToAXI4Lite(addr_width=32, data_width=128)
        self.assertEqual(adapter.data_width, 128)

    def test_invalid_data_width_not_power_of_2(self):
        """Data width 48 (not power of 2) should raise ValueError."""
        with self.assertRaises(ValueError):
            AXI4ToAXI4Lite(addr_width=32, data_width=48)

    def test_invalid_id_width_negative(self):
        """Negative ID width should raise TypeError."""
        with self.assertRaises(TypeError):
            AXI4ToAXI4Lite(addr_width=32, data_width=32, id_width=-1)

    def test_invalid_id_width_string(self):
        """String ID width should raise TypeError."""
        with self.assertRaises(TypeError):
            AXI4ToAXI4Lite(addr_width=32, data_width=32, id_width="4")


class TestAXI4ToAXI4LiteElaboration(unittest.TestCase):
    """Test AXI4ToAXI4Lite RTLIL elaboration."""

    def test_elaborate_basic(self):
        """Elaborate with basic parameters."""
        adapter = AXI4ToAXI4Lite(addr_width=32, data_width=32, id_width=4)
        rtlil = convert(adapter)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_64bit(self):
        """Elaborate with 64-bit data width."""
        adapter = AXI4ToAXI4Lite(addr_width=32, data_width=64, id_width=4)
        rtlil = convert(adapter)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_no_id(self):
        """Elaborate with id_width=0."""
        adapter = AXI4ToAXI4Lite(addr_width=32, data_width=32, id_width=0)
        rtlil = convert(adapter)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_wide_id(self):
        """Elaborate with wide ID width."""
        adapter = AXI4ToAXI4Lite(addr_width=32, data_width=32, id_width=8)
        rtlil = convert(adapter)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_narrow_addr(self):
        """Elaborate with narrow address width."""
        adapter = AXI4ToAXI4Lite(addr_width=12, data_width=32, id_width=4)
        rtlil = convert(adapter)
        self.assertGreater(len(rtlil), 0)


if __name__ == "__main__":
    unittest.main()
