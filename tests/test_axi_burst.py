"""Tests for AXI burst-to-beat converter."""
import unittest
from amaranth.back.rtlil import convert

from amaranth_soc.axi.burst import AXIBurst2Beat


class TestAXIBurst2BeatConstruction(unittest.TestCase):
    """Test AXIBurst2Beat construction and parameter validation."""

    def test_create_basic(self):
        """Construct with basic valid parameters."""
        b2b = AXIBurst2Beat(addr_width=32, data_width=32)
        self.assertEqual(b2b.addr_width, 32)
        self.assertEqual(b2b.data_width, 32)

    def test_create_64bit_data(self):
        """Construct with 64-bit data width."""
        b2b = AXIBurst2Beat(addr_width=32, data_width=64)
        self.assertEqual(b2b.data_width, 64)

    def test_create_128bit_data(self):
        """Construct with 128-bit data width."""
        b2b = AXIBurst2Beat(addr_width=32, data_width=128)
        self.assertEqual(b2b.data_width, 128)

    def test_create_narrow_addr(self):
        """Construct with narrow address width."""
        b2b = AXIBurst2Beat(addr_width=12, data_width=32)
        self.assertEqual(b2b.addr_width, 12)

    def test_create_wide_addr(self):
        """Construct with wide address width."""
        b2b = AXIBurst2Beat(addr_width=48, data_width=32)
        self.assertEqual(b2b.addr_width, 48)

    def test_create_8bit_data(self):
        """Construct with minimum data width (8 bits)."""
        b2b = AXIBurst2Beat(addr_width=16, data_width=8)
        self.assertEqual(b2b.data_width, 8)

    def test_invalid_addr_width_zero(self):
        """Address width of 0 should raise TypeError."""
        with self.assertRaises(TypeError):
            AXIBurst2Beat(addr_width=0, data_width=32)

    def test_invalid_addr_width_negative(self):
        """Negative address width should raise TypeError."""
        with self.assertRaises(TypeError):
            AXIBurst2Beat(addr_width=-1, data_width=32)

    def test_invalid_addr_width_string(self):
        """String address width should raise TypeError."""
        with self.assertRaises(TypeError):
            AXIBurst2Beat(addr_width="32", data_width=32)

    def test_invalid_data_width_too_small(self):
        """Data width < 8 should raise ValueError."""
        with self.assertRaises(ValueError):
            AXIBurst2Beat(addr_width=32, data_width=4)

    def test_invalid_data_width_not_power_of_2(self):
        """Non-power-of-2 data width should raise ValueError."""
        with self.assertRaises(ValueError):
            AXIBurst2Beat(addr_width=32, data_width=48)

    def test_invalid_data_width_string(self):
        """String data width should raise ValueError."""
        with self.assertRaises((TypeError, ValueError)):
            AXIBurst2Beat(addr_width=32, data_width="32")


class TestAXIBurst2BeatProperties(unittest.TestCase):
    """Test AXIBurst2Beat property access."""

    def test_addr_width_property(self):
        b2b = AXIBurst2Beat(addr_width=24, data_width=32)
        self.assertEqual(b2b.addr_width, 24)

    def test_data_width_property(self):
        b2b = AXIBurst2Beat(addr_width=32, data_width=64)
        self.assertEqual(b2b.data_width, 64)

    def test_internal_addr_width(self):
        """Internal _addr_width matches property."""
        b2b = AXIBurst2Beat(addr_width=32, data_width=32)
        self.assertEqual(b2b._addr_width, b2b.addr_width)

    def test_internal_data_width(self):
        """Internal _data_width matches property."""
        b2b = AXIBurst2Beat(addr_width=32, data_width=32)
        self.assertEqual(b2b._data_width, b2b.data_width)


class TestAXIBurst2BeatElaboration(unittest.TestCase):
    """Test AXIBurst2Beat RTLIL elaboration."""

    def test_elaborate_32bit(self):
        """Elaborate with 32-bit data width."""
        b2b = AXIBurst2Beat(addr_width=32, data_width=32)
        rtlil = convert(b2b)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_64bit(self):
        """Elaborate with 64-bit data width."""
        b2b = AXIBurst2Beat(addr_width=32, data_width=64)
        rtlil = convert(b2b)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_128bit(self):
        """Elaborate with 128-bit data width."""
        b2b = AXIBurst2Beat(addr_width=32, data_width=128)
        rtlil = convert(b2b)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_narrow_addr(self):
        """Elaborate with narrow address width."""
        b2b = AXIBurst2Beat(addr_width=12, data_width=32)
        rtlil = convert(b2b)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_different_data_widths(self):
        """Elaborate with various valid data widths."""
        for dw in [8, 16, 32, 64, 128]:
            with self.subTest(data_width=dw):
                b2b = AXIBurst2Beat(addr_width=32, data_width=dw)
                rtlil = convert(b2b)
                self.assertGreater(len(rtlil), 0)


if __name__ == "__main__":
    unittest.main()
