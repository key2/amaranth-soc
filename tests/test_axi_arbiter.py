"""Tests for AXI4LiteArbiter."""
import unittest
from amaranth.back.rtlil import convert
from amaranth_soc.axi.arbiter import AXI4LiteArbiter
from amaranth_soc.axi.bus import AXI4LiteInterface
from amaranth_soc.memory import MemoryMap


class TestAXI4LiteArbiter(unittest.TestCase):
    def test_create(self):
        arb = AXI4LiteArbiter(addr_width=16, data_width=32)
        self.assertIsNotNone(arb)

    def test_create_invalid_addr_width(self):
        with self.assertRaises(TypeError):
            AXI4LiteArbiter(addr_width=-1, data_width=32)

    def test_create_invalid_data_width(self):
        with self.assertRaises(ValueError):
            AXI4LiteArbiter(addr_width=16, data_width=16)

    def test_add_master(self):
        arb = AXI4LiteArbiter(addr_width=16, data_width=32)
        m1 = AXI4LiteInterface(addr_width=16, data_width=32)
        m1.memory_map = MemoryMap(addr_width=16, data_width=8)
        arb.add(m1)

    def test_add_master_wrong_addr_width(self):
        arb = AXI4LiteArbiter(addr_width=16, data_width=32)
        m1 = AXI4LiteInterface(addr_width=12, data_width=32)
        m1.memory_map = MemoryMap(addr_width=12, data_width=8)
        with self.assertRaises(ValueError):
            arb.add(m1)

    def test_add_master_wrong_data_width(self):
        arb = AXI4LiteArbiter(addr_width=16, data_width=32)
        m1 = AXI4LiteInterface(addr_width=16, data_width=64)
        m1.memory_map = MemoryMap(addr_width=16, data_width=8)
        with self.assertRaises(ValueError):
            arb.add(m1)

    def test_add_master_wrong_type(self):
        arb = AXI4LiteArbiter(addr_width=16, data_width=32)
        with self.assertRaises(TypeError):
            arb.add("not a bus")

    def test_elaborate_single_master(self):
        arb = AXI4LiteArbiter(addr_width=16, data_width=32)
        m1 = AXI4LiteInterface(addr_width=16, data_width=32)
        m1.memory_map = MemoryMap(addr_width=16, data_width=8)
        arb.add(m1)
        rtlil = convert(arb)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_two_masters(self):
        arb = AXI4LiteArbiter(addr_width=16, data_width=32)
        m1 = AXI4LiteInterface(addr_width=16, data_width=32)
        m1.memory_map = MemoryMap(addr_width=16, data_width=8)
        arb.add(m1)
        m2 = AXI4LiteInterface(addr_width=16, data_width=32)
        m2.memory_map = MemoryMap(addr_width=16, data_width=8)
        arb.add(m2)
        rtlil = convert(arb)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_no_masters(self):
        """Arbiter with no masters should still elaborate (tie-off path)."""
        arb = AXI4LiteArbiter(addr_width=16, data_width=32)
        rtlil = convert(arb)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_three_masters(self):
        arb = AXI4LiteArbiter(addr_width=16, data_width=32)
        for _ in range(3):
            m = AXI4LiteInterface(addr_width=16, data_width=32)
            m.memory_map = MemoryMap(addr_width=16, data_width=8)
            arb.add(m)
        rtlil = convert(arb)
        self.assertGreater(len(rtlil), 0)


if __name__ == "__main__":
    unittest.main()
