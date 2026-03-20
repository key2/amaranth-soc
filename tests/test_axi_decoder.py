"""Tests for AXI4LiteDecoder."""
import unittest
from amaranth.back.rtlil import convert
from amaranth_soc.axi.decoder import AXI4LiteDecoder
from amaranth_soc.axi.bus import AXI4LiteInterface
from amaranth_soc.memory import MemoryMap


class TestAXI4LiteDecoder(unittest.TestCase):
    def test_create(self):
        dec = AXI4LiteDecoder(addr_width=16, data_width=32)
        self.assertIsNotNone(dec.memory_map)
        self.assertEqual(dec.memory_map.addr_width, 16)
        self.assertEqual(dec.memory_map.data_width, 8)

    def test_create_invalid_addr_width(self):
        with self.assertRaises(TypeError):
            AXI4LiteDecoder(addr_width=-1, data_width=32)

    def test_create_invalid_data_width(self):
        with self.assertRaises(ValueError):
            AXI4LiteDecoder(addr_width=16, data_width=16)

    def test_add_subordinate(self):
        dec = AXI4LiteDecoder(addr_width=16, data_width=32)
        sub = AXI4LiteInterface(addr_width=14, data_width=32)
        sub.memory_map = MemoryMap(addr_width=14, data_width=8)
        dec.add(sub, name='sub1', addr=0x0000)

    def test_add_subordinate_wrong_data_width(self):
        dec = AXI4LiteDecoder(addr_width=16, data_width=32)
        sub = AXI4LiteInterface(addr_width=14, data_width=64)
        sub.memory_map = MemoryMap(addr_width=14, data_width=8)
        with self.assertRaises(ValueError):
            dec.add(sub, name='sub1', addr=0x0000)

    def test_add_subordinate_wrong_type(self):
        dec = AXI4LiteDecoder(addr_width=16, data_width=32)
        with self.assertRaises(TypeError):
            dec.add("not a bus", name='sub1', addr=0x0000)

    def test_elaborate_single_sub(self):
        dec = AXI4LiteDecoder(addr_width=16, data_width=32)
        sub1 = AXI4LiteInterface(addr_width=14, data_width=32)
        sub1.memory_map = MemoryMap(addr_width=14, data_width=8)
        dec.add(sub1, name='sub1', addr=0x0000)
        # Should elaborate without error
        rtlil = convert(dec)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_two_subs(self):
        dec = AXI4LiteDecoder(addr_width=16, data_width=32)
        sub1 = AXI4LiteInterface(addr_width=14, data_width=32)
        sub1.memory_map = MemoryMap(addr_width=14, data_width=8)
        dec.add(sub1, name='sub1', addr=0x0000)
        sub2 = AXI4LiteInterface(addr_width=14, data_width=32)
        sub2.memory_map = MemoryMap(addr_width=14, data_width=8)
        dec.add(sub2, name='sub2', addr=0x4000)
        # Should elaborate without error
        rtlil = convert(dec)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_no_subs(self):
        """Decoder with no subordinates should still elaborate (DECERR path)."""
        dec = AXI4LiteDecoder(addr_width=16, data_width=32)
        rtlil = convert(dec)
        self.assertGreater(len(rtlil), 0)

    def test_align_to(self):
        dec = AXI4LiteDecoder(addr_width=16, data_width=32)
        dec.align_to(12)  # Align to 4096 bytes


if __name__ == "__main__":
    unittest.main()
