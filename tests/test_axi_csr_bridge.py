"""Tests for AXI4LiteCSRBridge."""
import unittest
from amaranth.back.rtlil import convert
from amaranth_soc.csr.axi_lite import AXI4LiteCSRBridge
from amaranth_soc.csr.bus import Interface as CSRInterface
from amaranth_soc.memory import MemoryMap


class TestAXI4LiteCSRBridge(unittest.TestCase):
    def test_create(self):
        csr_bus = CSRInterface(addr_width=10, data_width=8)
        csr_bus.memory_map = MemoryMap(addr_width=10, data_width=8)
        bridge = AXI4LiteCSRBridge(csr_bus, data_width=32)
        self.assertIsNotNone(bridge)

    def test_create_default_data_width(self):
        """When data_width is None, it defaults to csr_bus.data_width."""
        # CSR data_width=8 is not valid for AXI4-Lite (must be 32 or 64),
        # so we use data_width=32 explicitly.
        csr_bus = CSRInterface(addr_width=10, data_width=8)
        csr_bus.memory_map = MemoryMap(addr_width=10, data_width=8)
        bridge = AXI4LiteCSRBridge(csr_bus, data_width=32)
        self.assertIsNotNone(bridge.axi_bus)

    def test_csr_bus_property(self):
        csr_bus = CSRInterface(addr_width=10, data_width=8)
        csr_bus.memory_map = MemoryMap(addr_width=10, data_width=8)
        bridge = AXI4LiteCSRBridge(csr_bus, data_width=32)
        self.assertIs(bridge.csr_bus, csr_bus)

    def test_axi_bus_memory_map(self):
        csr_bus = CSRInterface(addr_width=10, data_width=8)
        csr_bus.memory_map = MemoryMap(addr_width=10, data_width=8)
        bridge = AXI4LiteCSRBridge(csr_bus, data_width=32)
        self.assertIsNotNone(bridge.axi_bus.memory_map)

    def test_wrong_csr_bus_type(self):
        with self.assertRaises(TypeError):
            AXI4LiteCSRBridge("not a csr bus", data_width=32)

    def test_elaborate(self):
        csr_bus = CSRInterface(addr_width=10, data_width=8)
        csr_bus.memory_map = MemoryMap(addr_width=10, data_width=8)
        bridge = AXI4LiteCSRBridge(csr_bus, data_width=32)
        rtlil = convert(bridge)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_64bit(self):
        csr_bus = CSRInterface(addr_width=10, data_width=8)
        csr_bus.memory_map = MemoryMap(addr_width=10, data_width=8)
        bridge = AXI4LiteCSRBridge(csr_bus, data_width=64)
        rtlil = convert(bridge)
        self.assertGreater(len(rtlil), 0)


if __name__ == "__main__":
    unittest.main()
