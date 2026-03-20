"""Tests for AXI4-Lite timeout watchdog."""
import unittest
from amaranth.back.rtlil import convert

from amaranth_soc.axi.timeout import AXI4Timeout


class TestAXI4TimeoutConstruction(unittest.TestCase):
    """Test AXI4Timeout construction and parameter validation."""

    def test_create_basic(self):
        """Construct with basic valid parameters."""
        to = AXI4Timeout(addr_width=32, data_width=32)
        self.assertEqual(to.addr_width, 32)
        self.assertEqual(to.data_width, 32)
        self.assertEqual(to.timeout, 1024)  # default

    def test_create_custom_timeout(self):
        """Construct with custom timeout value."""
        to = AXI4Timeout(addr_width=32, data_width=32, timeout=256)
        self.assertEqual(to.timeout, 256)

    def test_create_64bit(self):
        """Construct with 64-bit data width."""
        to = AXI4Timeout(addr_width=32, data_width=64)
        self.assertEqual(to.data_width, 64)

    def test_create_small_timeout(self):
        """Construct with minimum timeout (1)."""
        to = AXI4Timeout(addr_width=32, data_width=32, timeout=1)
        self.assertEqual(to.timeout, 1)

    def test_create_large_timeout(self):
        """Construct with large timeout value."""
        to = AXI4Timeout(addr_width=32, data_width=32, timeout=65536)
        self.assertEqual(to.timeout, 65536)

    def test_create_zero_addr_width(self):
        """Construct with addr_width=0 (edge case)."""
        to = AXI4Timeout(addr_width=0, data_width=32)
        self.assertEqual(to.addr_width, 0)

    def test_invalid_addr_width_negative(self):
        """Negative address width should raise TypeError."""
        with self.assertRaises(TypeError):
            AXI4Timeout(addr_width=-1, data_width=32)

    def test_invalid_addr_width_string(self):
        """String address width should raise TypeError."""
        with self.assertRaises(TypeError):
            AXI4Timeout(addr_width="32", data_width=32)

    def test_invalid_data_width_16(self):
        """Data width 16 should raise ValueError."""
        with self.assertRaises(ValueError):
            AXI4Timeout(addr_width=32, data_width=16)

    def test_invalid_data_width_128(self):
        """Data width 128 should raise ValueError."""
        with self.assertRaises(ValueError):
            AXI4Timeout(addr_width=32, data_width=128)

    def test_invalid_timeout_zero(self):
        """Timeout of 0 should raise ValueError."""
        with self.assertRaises(ValueError):
            AXI4Timeout(addr_width=32, data_width=32, timeout=0)

    def test_invalid_timeout_negative(self):
        """Negative timeout should raise ValueError."""
        with self.assertRaises(ValueError):
            AXI4Timeout(addr_width=32, data_width=32, timeout=-1)

    def test_invalid_timeout_string(self):
        """String timeout should raise ValueError."""
        with self.assertRaises((TypeError, ValueError)):
            AXI4Timeout(addr_width=32, data_width=32, timeout="1024")


class TestAXI4TimeoutProperties(unittest.TestCase):
    """Test AXI4Timeout property access."""

    def test_addr_width_property(self):
        to = AXI4Timeout(addr_width=24, data_width=32)
        self.assertEqual(to.addr_width, 24)

    def test_data_width_property(self):
        to = AXI4Timeout(addr_width=32, data_width=64)
        self.assertEqual(to.data_width, 64)

    def test_timeout_property(self):
        to = AXI4Timeout(addr_width=32, data_width=32, timeout=512)
        self.assertEqual(to.timeout, 512)

    def test_timeout_default_property(self):
        to = AXI4Timeout(addr_width=32, data_width=32)
        self.assertEqual(to.timeout, 1024)


class TestAXI4TimeoutElaboration(unittest.TestCase):
    """Test AXI4Timeout RTLIL elaboration."""

    def test_elaborate_32bit(self):
        """Elaborate with 32-bit data width."""
        to = AXI4Timeout(addr_width=32, data_width=32)
        rtlil = convert(to)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_64bit(self):
        """Elaborate with 64-bit data width."""
        to = AXI4Timeout(addr_width=32, data_width=64)
        rtlil = convert(to)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_custom_timeout(self):
        """Elaborate with custom timeout."""
        to = AXI4Timeout(addr_width=32, data_width=32, timeout=256)
        rtlil = convert(to)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_small_timeout(self):
        """Elaborate with minimum timeout."""
        to = AXI4Timeout(addr_width=32, data_width=32, timeout=1)
        rtlil = convert(to)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_narrow_addr(self):
        """Elaborate with narrow address width."""
        to = AXI4Timeout(addr_width=12, data_width=32)
        rtlil = convert(to)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_various_timeouts(self):
        """Elaborate with various timeout values."""
        for timeout in [1, 16, 256, 1024, 4096]:
            with self.subTest(timeout=timeout):
                to = AXI4Timeout(addr_width=32, data_width=32, timeout=timeout)
                rtlil = convert(to)
                self.assertGreater(len(rtlil), 0)


if __name__ == "__main__":
    unittest.main()
