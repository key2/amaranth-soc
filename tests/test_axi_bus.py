"""Tests for AXI bus signatures and interfaces."""
import unittest
from amaranth_soc.axi.bus import (
    AXIResp, AXIBurst, AXISize,
    AXI4LiteSignature, AXI4LiteInterface,
    AXI4Signature, AXI4Interface,
)
from amaranth_soc.memory import MemoryMap


class TestAXIEnums(unittest.TestCase):
    def test_axi_resp_values(self):
        self.assertEqual(AXIResp.OKAY, 0)
        self.assertEqual(AXIResp.EXOKAY, 1)
        self.assertEqual(AXIResp.SLVERR, 2)
        self.assertEqual(AXIResp.DECERR, 3)

    def test_axi_burst_values(self):
        self.assertEqual(AXIBurst.FIXED, 0)
        self.assertEqual(AXIBurst.INCR, 1)
        self.assertEqual(AXIBurst.WRAP, 2)

    def test_axi_size_values(self):
        self.assertEqual(AXISize.B1, 0)
        self.assertEqual(AXISize.B2, 1)
        self.assertEqual(AXISize.B4, 2)
        self.assertEqual(AXISize.B8, 3)
        self.assertEqual(AXISize.B16, 4)
        self.assertEqual(AXISize.B32, 5)
        self.assertEqual(AXISize.B64, 6)
        self.assertEqual(AXISize.B128, 7)


class TestAXI4LiteSignature(unittest.TestCase):
    def test_create_32bit(self):
        sig = AXI4LiteSignature(addr_width=32, data_width=32)
        self.assertEqual(sig.addr_width, 32)
        self.assertEqual(sig.data_width, 32)

    def test_create_64bit(self):
        sig = AXI4LiteSignature(addr_width=32, data_width=64)
        self.assertEqual(sig.data_width, 64)

    def test_invalid_data_width_16(self):
        with self.assertRaises(ValueError):
            AXI4LiteSignature(addr_width=32, data_width=16)

    def test_invalid_data_width_128(self):
        with self.assertRaises(ValueError):
            AXI4LiteSignature(addr_width=32, data_width=128)

    def test_invalid_addr_width_negative(self):
        with self.assertRaises(TypeError):
            AXI4LiteSignature(addr_width=-1, data_width=32)

    def test_invalid_addr_width_string(self):
        with self.assertRaises(TypeError):
            AXI4LiteSignature(addr_width="32", data_width=32)

    def test_members(self):
        sig = AXI4LiteSignature(addr_width=32, data_width=32)
        members = set(sig.members.keys())
        expected = {
            'awaddr', 'awprot', 'awvalid', 'awready',
            'wdata', 'wstrb', 'wvalid', 'wready',
            'bresp', 'bvalid', 'bready',
            'araddr', 'arprot', 'arvalid', 'arready',
            'rdata', 'rresp', 'rvalid', 'rready',
        }
        self.assertEqual(members, expected)

    def test_equality(self):
        sig1 = AXI4LiteSignature(addr_width=32, data_width=32)
        sig2 = AXI4LiteSignature(addr_width=32, data_width=32)
        sig3 = AXI4LiteSignature(addr_width=16, data_width=32)
        sig4 = AXI4LiteSignature(addr_width=32, data_width=64)
        self.assertEqual(sig1, sig2)
        self.assertNotEqual(sig1, sig3)
        self.assertNotEqual(sig1, sig4)

    def test_not_equal_to_non_signature(self):
        sig = AXI4LiteSignature(addr_width=32, data_width=32)
        self.assertNotEqual(sig, "not a signature")

    def test_create_interface(self):
        sig = AXI4LiteSignature(addr_width=32, data_width=32)
        iface = sig.create()
        self.assertIsInstance(iface, AXI4LiteInterface)

    def test_repr(self):
        sig = AXI4LiteSignature(addr_width=32, data_width=32)
        r = repr(sig)
        self.assertIn("AXI4LiteSignature", r)


class TestAXI4LiteInterface(unittest.TestCase):
    def test_create(self):
        iface = AXI4LiteInterface(addr_width=16, data_width=32)
        self.assertEqual(iface.addr_width, 16)
        self.assertEqual(iface.data_width, 32)

    def test_memory_map(self):
        iface = AXI4LiteInterface(addr_width=16, data_width=32)
        mm = MemoryMap(addr_width=16, data_width=8)
        iface.memory_map = mm
        self.assertIs(iface.memory_map, mm)

    def test_memory_map_word_addressed(self):
        """Memory map with data_width matching bus data_width is also valid."""
        iface = AXI4LiteInterface(addr_width=16, data_width=32)
        mm = MemoryMap(addr_width=16, data_width=32)
        iface.memory_map = mm
        self.assertIs(iface.memory_map, mm)

    def test_no_memory_map(self):
        iface = AXI4LiteInterface(addr_width=16, data_width=32)
        with self.assertRaises(AttributeError):
            _ = iface.memory_map

    def test_memory_map_wrong_type(self):
        iface = AXI4LiteInterface(addr_width=16, data_width=32)
        with self.assertRaises(TypeError):
            iface.memory_map = "not a memory map"

    def test_memory_map_wrong_data_width(self):
        iface = AXI4LiteInterface(addr_width=16, data_width=32)
        mm = MemoryMap(addr_width=16, data_width=16)
        with self.assertRaises(ValueError):
            iface.memory_map = mm

    def test_memory_map_wrong_addr_width(self):
        iface = AXI4LiteInterface(addr_width=16, data_width=32)
        mm = MemoryMap(addr_width=12, data_width=8)
        with self.assertRaises(ValueError):
            iface.memory_map = mm

    def test_repr(self):
        iface = AXI4LiteInterface(addr_width=16, data_width=32)
        r = repr(iface)
        self.assertIn("AXI4LiteInterface", r)


class TestAXI4Signature(unittest.TestCase):
    def test_create_basic(self):
        sig = AXI4Signature(addr_width=32, data_width=32)
        self.assertEqual(sig.addr_width, 32)
        self.assertEqual(sig.data_width, 32)
        self.assertEqual(sig.id_width, 0)

    def test_create_with_id(self):
        sig = AXI4Signature(addr_width=32, data_width=32, id_width=4)
        self.assertEqual(sig.id_width, 4)
        self.assertIn('awid', sig.members)
        self.assertIn('bid', sig.members)
        self.assertIn('arid', sig.members)
        self.assertIn('rid', sig.members)

    def test_no_id_signals_when_zero(self):
        sig = AXI4Signature(addr_width=32, data_width=32, id_width=0)
        self.assertNotIn('awid', sig.members)
        self.assertNotIn('bid', sig.members)
        self.assertNotIn('arid', sig.members)
        self.assertNotIn('rid', sig.members)

    def test_burst_signals(self):
        sig = AXI4Signature(addr_width=32, data_width=32)
        self.assertIn('awlen', sig.members)
        self.assertIn('awsize', sig.members)
        self.assertIn('awburst', sig.members)
        self.assertIn('wlast', sig.members)
        self.assertIn('rlast', sig.members)
        self.assertIn('arlen', sig.members)
        self.assertIn('arsize', sig.members)
        self.assertIn('arburst', sig.members)

    def test_cache_lock_qos_region_signals(self):
        sig = AXI4Signature(addr_width=32, data_width=32)
        self.assertIn('awlock', sig.members)
        self.assertIn('awcache', sig.members)
        self.assertIn('awqos', sig.members)
        self.assertIn('awregion', sig.members)
        self.assertIn('arlock', sig.members)
        self.assertIn('arcache', sig.members)
        self.assertIn('arqos', sig.members)
        self.assertIn('arregion', sig.members)

    def test_user_signals(self):
        sig = AXI4Signature(addr_width=32, data_width=32,
                            user_width={"aw": 4, "w": 2, "b": 1, "ar": 4, "r": 3})
        self.assertIn('awuser', sig.members)
        self.assertIn('aruser', sig.members)
        self.assertIn('buser', sig.members)
        self.assertIn('ruser', sig.members)

    def test_no_user_signals_when_zero(self):
        sig = AXI4Signature(addr_width=32, data_width=32)
        self.assertNotIn('awuser', sig.members)
        self.assertNotIn('aruser', sig.members)
        self.assertNotIn('buser', sig.members)
        self.assertNotIn('ruser', sig.members)

    def test_create_interface(self):
        sig = AXI4Signature(addr_width=32, data_width=32, id_width=4)
        iface = sig.create()
        self.assertIsInstance(iface, AXI4Interface)

    def test_equality(self):
        sig1 = AXI4Signature(addr_width=32, data_width=32, id_width=4)
        sig2 = AXI4Signature(addr_width=32, data_width=32, id_width=4)
        sig3 = AXI4Signature(addr_width=32, data_width=32, id_width=8)
        self.assertEqual(sig1, sig2)
        self.assertNotEqual(sig1, sig3)

    def test_invalid_data_width_too_small(self):
        with self.assertRaises(ValueError):
            AXI4Signature(addr_width=32, data_width=4)

    def test_invalid_data_width_not_power_of_2(self):
        with self.assertRaises(ValueError):
            AXI4Signature(addr_width=32, data_width=48)

    def test_invalid_id_width_negative(self):
        with self.assertRaises(TypeError):
            AXI4Signature(addr_width=32, data_width=32, id_width=-1)

    def test_repr(self):
        sig = AXI4Signature(addr_width=32, data_width=32)
        r = repr(sig)
        self.assertIn("AXI4Signature", r)


class TestAXI4Interface(unittest.TestCase):
    def test_create(self):
        iface = AXI4Interface(addr_width=32, data_width=32, id_width=4)
        self.assertEqual(iface.addr_width, 32)
        self.assertEqual(iface.data_width, 32)
        self.assertEqual(iface.id_width, 4)

    def test_user_width(self):
        uw = {"aw": 4, "w": 2, "b": 1, "ar": 4, "r": 3}
        iface = AXI4Interface(addr_width=32, data_width=32, user_width=uw)
        self.assertEqual(iface.user_width, uw)

    def test_memory_map(self):
        iface = AXI4Interface(addr_width=16, data_width=32)
        mm = MemoryMap(addr_width=16, data_width=32)
        iface.memory_map = mm
        self.assertIs(iface.memory_map, mm)

    def test_no_memory_map(self):
        iface = AXI4Interface(addr_width=16, data_width=32)
        with self.assertRaises(AttributeError):
            _ = iface.memory_map

    def test_memory_map_wrong_data_width(self):
        iface = AXI4Interface(addr_width=16, data_width=32)
        mm = MemoryMap(addr_width=16, data_width=8)
        with self.assertRaises(ValueError):
            iface.memory_map = mm

    def test_repr(self):
        iface = AXI4Interface(addr_width=32, data_width=32)
        r = repr(iface)
        self.assertIn("AXI4Interface", r)


if __name__ == "__main__":
    unittest.main()
