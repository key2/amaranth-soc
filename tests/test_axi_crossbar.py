"""Tests for AXI4-Lite NxM crossbar interconnect."""
import unittest
from amaranth.back.rtlil import convert

from amaranth_soc.axi.crossbar import AXI4LiteCrossbar
from amaranth_soc.axi.bus import AXI4LiteInterface
from amaranth_soc.memory import MemoryMap


class TestAXI4LiteCrossbarConstruction(unittest.TestCase):
    """Test AXI4LiteCrossbar construction and parameter validation."""

    def test_create_basic(self):
        """Construct with basic valid parameters."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        self.assertEqual(xbar.addr_width, 16)
        self.assertEqual(xbar.data_width, 32)

    def test_create_64bit(self):
        """Construct with 64-bit data width."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=64)
        self.assertEqual(xbar.data_width, 64)

    def test_create_wide_addr(self):
        """Construct with wide address width."""
        xbar = AXI4LiteCrossbar(addr_width=32, data_width=32)
        self.assertEqual(xbar.addr_width, 32)

    def test_create_zero_addr_width(self):
        """Construct with addr_width=0 (edge case)."""
        xbar = AXI4LiteCrossbar(addr_width=0, data_width=32)
        self.assertEqual(xbar.addr_width, 0)

    def test_invalid_addr_width_negative(self):
        """Negative address width should raise TypeError."""
        with self.assertRaises(TypeError):
            AXI4LiteCrossbar(addr_width=-1, data_width=32)

    def test_invalid_addr_width_string(self):
        """String address width should raise TypeError."""
        with self.assertRaises(TypeError):
            AXI4LiteCrossbar(addr_width="16", data_width=32)

    def test_invalid_data_width_16(self):
        """Data width 16 should raise ValueError."""
        with self.assertRaises(ValueError):
            AXI4LiteCrossbar(addr_width=16, data_width=16)

    def test_invalid_data_width_128(self):
        """Data width 128 should raise ValueError."""
        with self.assertRaises(ValueError):
            AXI4LiteCrossbar(addr_width=16, data_width=128)


class TestAXI4LiteCrossbarConfiguration(unittest.TestCase):
    """Test AXI4LiteCrossbar add_master/add_slave configuration."""

    def _make_master(self, addr_width=16, data_width=32):
        """Helper to create a master bus interface."""
        return AXI4LiteInterface(addr_width=addr_width, data_width=data_width)

    def _make_slave(self, addr_width=14, data_width=32):
        """Helper to create a slave bus interface with memory map."""
        iface = AXI4LiteInterface(addr_width=addr_width, data_width=data_width)
        iface.memory_map = MemoryMap(addr_width=addr_width, data_width=8)
        return iface

    def test_add_master(self):
        """Add a single master."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        master = self._make_master()
        xbar.add_master(master, name="cpu")

    def test_add_slave(self):
        """Add a single slave."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        slave = self._make_slave()
        xbar.add_slave(slave, name="sram", addr=0x0000)

    def test_add_multiple_masters(self):
        """Add multiple masters."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        m1 = self._make_master()
        m2 = self._make_master()
        xbar.add_master(m1, name="cpu")
        xbar.add_master(m2, name="dma")

    def test_add_multiple_slaves(self):
        """Add multiple slaves at different addresses."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        s1 = self._make_slave()
        s2 = self._make_slave()
        xbar.add_slave(s1, name="sram", addr=0x0000)
        xbar.add_slave(s2, name="uart", addr=0x4000)

    def test_add_master_wrong_data_width(self):
        """Master with wrong data width should raise ValueError."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        master = self._make_master(data_width=64)
        with self.assertRaises(ValueError):
            xbar.add_master(master)

    def test_add_slave_wrong_data_width(self):
        """Slave with wrong data width should raise ValueError."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        slave = self._make_slave(data_width=64)
        with self.assertRaises(ValueError):
            xbar.add_slave(slave, name="bad")

    def test_add_master_wrong_type(self):
        """Non-AXI4LiteInterface master should raise TypeError."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        with self.assertRaises(TypeError):
            xbar.add_master("not a bus")

    def test_add_slave_wrong_type(self):
        """Non-AXI4LiteInterface slave should raise TypeError."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        with self.assertRaises(TypeError):
            xbar.add_slave("not a bus", name="bad")

    def test_auto_name_master(self):
        """Masters without explicit name get auto-named."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        m1 = self._make_master()
        m2 = self._make_master()
        xbar.add_master(m1)
        xbar.add_master(m2)

    def test_auto_name_slave(self):
        """Slaves without explicit name get auto-named."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        s1 = self._make_slave()
        xbar.add_slave(s1, addr=0x0000)


class TestAXI4LiteCrossbarElaboration(unittest.TestCase):
    """Test AXI4LiteCrossbar RTLIL elaboration."""

    def _make_master(self, addr_width=16, data_width=32):
        return AXI4LiteInterface(addr_width=addr_width, data_width=data_width)

    def _make_slave(self, addr_width=14, data_width=32):
        """Create a slave with memory map."""
        iface = AXI4LiteInterface(addr_width=addr_width, data_width=data_width)
        iface.memory_map = MemoryMap(addr_width=addr_width, data_width=8)
        return iface

    def test_elaborate_empty(self):
        """Crossbar with no masters/slaves should elaborate (empty module)."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        rtlil = convert(xbar)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_1x1(self):
        """Elaborate 1 master × 1 slave crossbar."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        m = self._make_master()
        s = self._make_slave()
        xbar.add_master(m, name="cpu")
        xbar.add_slave(s, name="sram", addr=0x0000)
        rtlil = convert(xbar)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_2x1(self):
        """Elaborate 2 masters × 1 slave crossbar."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        m1 = self._make_master()
        m2 = self._make_master()
        s = self._make_slave()
        xbar.add_master(m1, name="cpu")
        xbar.add_master(m2, name="dma")
        xbar.add_slave(s, name="sram", addr=0x0000)
        rtlil = convert(xbar)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_1x2(self):
        """Elaborate 1 master × 2 slaves crossbar."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        m = self._make_master()
        s1 = self._make_slave()
        s2 = self._make_slave()
        xbar.add_master(m, name="cpu")
        xbar.add_slave(s1, name="sram", addr=0x0000)
        xbar.add_slave(s2, name="uart", addr=0x4000)
        rtlil = convert(xbar)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_2x2(self):
        """Elaborate 2 masters × 2 slaves crossbar."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        m1 = self._make_master()
        m2 = self._make_master()
        s1 = self._make_slave()
        s2 = self._make_slave()
        xbar.add_master(m1, name="cpu")
        xbar.add_master(m2, name="dma")
        xbar.add_slave(s1, name="sram", addr=0x0000)
        xbar.add_slave(s2, name="uart", addr=0x4000)
        rtlil = convert(xbar)
        self.assertGreater(len(rtlil), 0)

    def test_cannot_add_after_elaborate(self):
        """Adding masters/slaves after elaborate() should raise RuntimeError."""
        xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)
        m = self._make_master()
        s = self._make_slave()
        xbar.add_master(m, name="cpu")
        xbar.add_slave(s, name="sram", addr=0x0000)
        # Elaborate to lock the crossbar
        convert(xbar)
        # Now adding should fail
        m2 = self._make_master()
        with self.assertRaises(RuntimeError):
            xbar.add_master(m2, name="dma")
        s2 = self._make_slave()
        with self.assertRaises(RuntimeError):
            xbar.add_slave(s2, name="uart", addr=0x4000)


if __name__ == "__main__":
    unittest.main()
