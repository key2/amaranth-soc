"""Tests for BusAdapter registry."""
import unittest

from amaranth_soc import BusStandard
from amaranth_soc.bridge.registry import BusAdapter
from amaranth_soc.bridge.wb_to_axi import WishboneToAXI4Lite
from amaranth_soc.bridge.axi_to_wb import AXI4LiteToWishbone
from amaranth_soc.axi.adapter import AXI4ToAXI4Lite


class TestBusAdapterSameStandard(unittest.TestCase):
    """Test BusAdapter with same source and target standard."""

    def test_wishbone_to_wishbone(self):
        """Same standard (WB→WB) should be adaptable with empty chain."""
        self.assertTrue(BusAdapter.can_adapt(BusStandard.WISHBONE, BusStandard.WISHBONE))
        chain = BusAdapter.get_bridge_chain(BusStandard.WISHBONE, BusStandard.WISHBONE)
        self.assertEqual(chain, [])

    def test_axi4lite_to_axi4lite(self):
        """Same standard (AXI4L→AXI4L) should be adaptable with empty chain."""
        self.assertTrue(BusAdapter.can_adapt(BusStandard.AXI4_LITE, BusStandard.AXI4_LITE))
        chain = BusAdapter.get_bridge_chain(BusStandard.AXI4_LITE, BusStandard.AXI4_LITE)
        self.assertEqual(chain, [])

    def test_axi4_to_axi4(self):
        """Same standard (AXI4→AXI4) should be adaptable with empty chain."""
        self.assertTrue(BusAdapter.can_adapt(BusStandard.AXI4, BusStandard.AXI4))
        chain = BusAdapter.get_bridge_chain(BusStandard.AXI4, BusStandard.AXI4)
        self.assertEqual(chain, [])


class TestBusAdapterDirectBridges(unittest.TestCase):
    """Test BusAdapter direct (single-hop) bridges."""

    def test_wb_to_axi4lite_can_adapt(self):
        """WB→AXI4L should be adaptable."""
        self.assertTrue(BusAdapter.can_adapt(BusStandard.WISHBONE, BusStandard.AXI4_LITE))

    def test_wb_to_axi4lite_chain(self):
        """WB→AXI4L chain should have one bridge."""
        chain = BusAdapter.get_bridge_chain(BusStandard.WISHBONE, BusStandard.AXI4_LITE)
        self.assertEqual(len(chain), 1)
        bridge_cls, from_std, to_std = chain[0]
        self.assertIs(bridge_cls, WishboneToAXI4Lite)
        self.assertEqual(from_std, BusStandard.WISHBONE)
        self.assertEqual(to_std, BusStandard.AXI4_LITE)

    def test_axi4lite_to_wb_can_adapt(self):
        """AXI4L→WB should be adaptable."""
        self.assertTrue(BusAdapter.can_adapt(BusStandard.AXI4_LITE, BusStandard.WISHBONE))

    def test_axi4lite_to_wb_chain(self):
        """AXI4L→WB chain should have one bridge."""
        chain = BusAdapter.get_bridge_chain(BusStandard.AXI4_LITE, BusStandard.WISHBONE)
        self.assertEqual(len(chain), 1)
        bridge_cls, from_std, to_std = chain[0]
        self.assertIs(bridge_cls, AXI4LiteToWishbone)
        self.assertEqual(from_std, BusStandard.AXI4_LITE)
        self.assertEqual(to_std, BusStandard.WISHBONE)

    def test_axi4_to_axi4lite_can_adapt(self):
        """AXI4→AXI4L should be adaptable."""
        self.assertTrue(BusAdapter.can_adapt(BusStandard.AXI4, BusStandard.AXI4_LITE))

    def test_axi4_to_axi4lite_chain(self):
        """AXI4→AXI4L chain should have one bridge."""
        chain = BusAdapter.get_bridge_chain(BusStandard.AXI4, BusStandard.AXI4_LITE)
        self.assertEqual(len(chain), 1)
        bridge_cls, from_std, to_std = chain[0]
        self.assertIs(bridge_cls, AXI4ToAXI4Lite)
        self.assertEqual(from_std, BusStandard.AXI4)
        self.assertEqual(to_std, BusStandard.AXI4_LITE)


class TestBusAdapterTwoHop(unittest.TestCase):
    """Test BusAdapter two-hop bridges (via AXI4-Lite hub)."""

    def test_axi4_to_wb_can_adapt(self):
        """AXI4→WB should be adaptable (two-hop via AXI4L)."""
        self.assertTrue(BusAdapter.can_adapt(BusStandard.AXI4, BusStandard.WISHBONE))

    def test_axi4_to_wb_chain(self):
        """AXI4→WB chain should have two bridges: AXI4→AXI4L, AXI4L→WB."""
        chain = BusAdapter.get_bridge_chain(BusStandard.AXI4, BusStandard.WISHBONE)
        self.assertEqual(len(chain), 2)

        # First hop: AXI4 → AXI4-Lite
        bridge_cls_1, from_std_1, to_std_1 = chain[0]
        self.assertIs(bridge_cls_1, AXI4ToAXI4Lite)
        self.assertEqual(from_std_1, BusStandard.AXI4)
        self.assertEqual(to_std_1, BusStandard.AXI4_LITE)

        # Second hop: AXI4-Lite → Wishbone
        bridge_cls_2, from_std_2, to_std_2 = chain[1]
        self.assertIs(bridge_cls_2, AXI4LiteToWishbone)
        self.assertEqual(from_std_2, BusStandard.AXI4_LITE)
        self.assertEqual(to_std_2, BusStandard.WISHBONE)


class TestBusAdapterNoPath(unittest.TestCase):
    """Test BusAdapter when no bridge path exists."""

    def test_wb_to_axi4_no_path(self):
        """WB→AXI4 should not be adaptable (no reverse AXI4L→AXI4 bridge)."""
        self.assertFalse(BusAdapter.can_adapt(BusStandard.WISHBONE, BusStandard.AXI4))

    def test_wb_to_axi4_raises(self):
        """WB→AXI4 get_bridge_chain should raise ValueError."""
        with self.assertRaises(ValueError):
            BusAdapter.get_bridge_chain(BusStandard.WISHBONE, BusStandard.AXI4)

    def test_axi4lite_to_axi4_no_path(self):
        """AXI4L→AXI4 should not be adaptable (no reverse bridge)."""
        self.assertFalse(BusAdapter.can_adapt(BusStandard.AXI4_LITE, BusStandard.AXI4))

    def test_axi4lite_to_axi4_raises(self):
        """AXI4L→AXI4 get_bridge_chain should raise ValueError."""
        with self.assertRaises(ValueError):
            BusAdapter.get_bridge_chain(BusStandard.AXI4_LITE, BusStandard.AXI4)


class TestBusAdapterListBridges(unittest.TestCase):
    """Test BusAdapter.list_bridges()."""

    def test_list_bridges_returns_dict(self):
        """list_bridges() should return a dict."""
        bridges = BusAdapter.list_bridges()
        self.assertIsInstance(bridges, dict)

    def test_list_bridges_contains_registered(self):
        """list_bridges() should contain all registered bridges."""
        bridges = BusAdapter.list_bridges()
        self.assertIn((BusStandard.WISHBONE, BusStandard.AXI4_LITE), bridges)
        self.assertIn((BusStandard.AXI4_LITE, BusStandard.WISHBONE), bridges)
        self.assertIn((BusStandard.AXI4, BusStandard.AXI4_LITE), bridges)

    def test_list_bridges_correct_classes(self):
        """list_bridges() should map to correct bridge classes."""
        bridges = BusAdapter.list_bridges()
        self.assertIs(bridges[(BusStandard.WISHBONE, BusStandard.AXI4_LITE)],
                      WishboneToAXI4Lite)
        self.assertIs(bridges[(BusStandard.AXI4_LITE, BusStandard.WISHBONE)],
                      AXI4LiteToWishbone)
        self.assertIs(bridges[(BusStandard.AXI4, BusStandard.AXI4_LITE)],
                      AXI4ToAXI4Lite)


if __name__ == "__main__":
    unittest.main()
