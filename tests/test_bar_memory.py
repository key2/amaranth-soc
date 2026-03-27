# amaranth: UnusedElaboratable=no

import unittest
from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import Out

from amaranth_soc.memory import BARMemoryMap
from amaranth_soc.export.c_header import generate_bar_header


class _MockResource(wiring.Component):
    foo : Out(unsigned(1))

    def __init__(self, name):
        self._name = name

    def __repr__(self):
        return f"_MockResource('{self._name}')"


class TestBARCreate(unittest.TestCase):
    """test_bar_create — Constructor with valid params."""

    def test_bar_create(self):
        bar = BARMemoryMap(bar_index=0, size=0x10000)
        self.assertEqual(bar.bar_index, 0)
        self.assertEqual(bar.size, 0x10000)
        self.assertEqual(bar.name, "BAR0")
        self.assertEqual(bar.base_addr, 0)
        self.assertIsNotNone(bar.memory_map)
        self.assertEqual(bar.memory_map.addr_width, 16)  # (0x10000-1).bit_length() == 16
        self.assertEqual(bar.memory_map.data_width, 8)

    def test_bar_create_custom_name(self):
        bar = BARMemoryMap(bar_index=2, size=4096, data_width=32, name="MyBAR")
        self.assertEqual(bar.bar_index, 2)
        self.assertEqual(bar.size, 4096)
        self.assertEqual(bar.name, "MyBAR")
        self.assertEqual(bar.memory_map.data_width, 32)


class TestBARCreateInvalidIndex(unittest.TestCase):
    """test_bar_create_invalid_index — Reject negative bar_index."""

    def test_bar_create_invalid_index_negative(self):
        with self.assertRaisesRegex(ValueError,
                r"BAR index must be a non-negative integer, not -1"):
            BARMemoryMap(bar_index=-1, size=0x10000)

    def test_bar_create_invalid_index_type(self):
        with self.assertRaisesRegex(ValueError,
                r"BAR index must be a non-negative integer, not 'foo'"):
            BARMemoryMap(bar_index="foo", size=0x10000)


class TestBARCreateInvalidSize(unittest.TestCase):
    """test_bar_create_invalid_size — Reject non-power-of-2 size."""

    def test_bar_create_invalid_size_not_power_of_2(self):
        with self.assertRaisesRegex(ValueError,
                r"Size must be a power of 2, not 100"):
            BARMemoryMap(bar_index=0, size=100)

    def test_bar_create_invalid_size_zero(self):
        with self.assertRaisesRegex(ValueError,
                r"Size must be a positive integer, not 0"):
            BARMemoryMap(bar_index=0, size=0)

    def test_bar_create_invalid_size_negative(self):
        with self.assertRaisesRegex(ValueError,
                r"Size must be a positive integer, not -1"):
            BARMemoryMap(bar_index=0, size=-1)


class TestBARAddResource(unittest.TestCase):
    """test_bar_add_resource — Add resources at offsets."""

    def test_bar_add_resource(self):
        bar = BARMemoryMap(bar_index=0, size=0x10000)
        res = _MockResource("ctrl")
        start, end = bar.add_resource(res, name="control", size=4)
        self.assertEqual(start, 0)
        self.assertEqual(end, 4)

    def test_bar_add_resource_explicit_addr(self):
        bar = BARMemoryMap(bar_index=0, size=0x10000)
        res = _MockResource("ctrl")
        start, end = bar.add_resource(res, name="control", size=4, addr=0x100)
        self.assertEqual(start, 0x100)
        self.assertEqual(end, 0x104)

    def test_bar_add_multiple_resources(self):
        bar = BARMemoryMap(bar_index=0, size=0x10000)
        res1 = _MockResource("ctrl")
        res2 = _MockResource("status")
        res3 = _MockResource("data")
        bar.add_resource(res1, name="control", size=4, addr=0x0000)
        bar.add_resource(res2, name="status", size=4, addr=0x0004)
        bar.add_resource(res3, name="data", size=4, addr=0x0008)
        resources = list(bar.resources())
        self.assertEqual(len(resources), 3)


class TestBARBaseAddr(unittest.TestCase):
    """test_bar_base_addr — Set and get base_addr."""

    def test_bar_base_addr_default(self):
        bar = BARMemoryMap(bar_index=0, size=0x10000)
        self.assertEqual(bar.base_addr, 0)

    def test_bar_base_addr_set(self):
        bar = BARMemoryMap(bar_index=0, size=0x10000)
        bar.base_addr = 0xFE000000
        self.assertEqual(bar.base_addr, 0xFE000000)

    def test_bar_base_addr_invalid(self):
        bar = BARMemoryMap(bar_index=0, size=0x10000)
        with self.assertRaisesRegex(ValueError,
                r"Base address must be a non-negative integer, not -1"):
            bar.base_addr = -1

    def test_bar_base_addr_invalid_type(self):
        bar = BARMemoryMap(bar_index=0, size=0x10000)
        with self.assertRaisesRegex(ValueError,
                r"Base address must be a non-negative integer, not 'bad'"):
            bar.base_addr = "bad"


class TestBARAbsoluteAddr(unittest.TestCase):
    """test_bar_absolute_addr — Convert relative to absolute."""

    def test_bar_absolute_addr(self):
        bar = BARMemoryMap(bar_index=0, size=0x10000)
        bar.base_addr = 0xFE000000
        self.assertEqual(bar.absolute_addr(0x0000), 0xFE000000)
        self.assertEqual(bar.absolute_addr(0x0004), 0xFE000004)
        self.assertEqual(bar.absolute_addr(0x1000), 0xFE001000)

    def test_bar_absolute_addr_zero_base(self):
        bar = BARMemoryMap(bar_index=0, size=0x10000)
        self.assertEqual(bar.absolute_addr(0x100), 0x100)


class TestBARRelativeAddr(unittest.TestCase):
    """test_bar_relative_addr — Convert absolute to relative."""

    def test_bar_relative_addr(self):
        bar = BARMemoryMap(bar_index=0, size=0x10000)
        bar.base_addr = 0xFE000000
        self.assertEqual(bar.relative_addr(0xFE000000), 0x0000)
        self.assertEqual(bar.relative_addr(0xFE000004), 0x0004)
        self.assertEqual(bar.relative_addr(0xFE00FFFF), 0xFFFF)


class TestBARRelativeAddrOutOfRange(unittest.TestCase):
    """test_bar_relative_addr_out_of_range — Reject out-of-range absolute address."""

    def test_bar_relative_addr_below_range(self):
        bar = BARMemoryMap(bar_index=0, size=0x10000)
        bar.base_addr = 0xFE000000
        with self.assertRaisesRegex(ValueError,
                r"Address 0xfdff0000 is outside BAR0 "
                r"range \[0xfe000000, 0xfe010000\)"):
            bar.relative_addr(0xFDFF0000)

    def test_bar_relative_addr_above_range(self):
        bar = BARMemoryMap(bar_index=0, size=0x10000)
        bar.base_addr = 0xFE000000
        with self.assertRaisesRegex(ValueError,
                r"Address 0xfe010000 is outside BAR0 "
                r"range \[0xfe000000, 0xfe010000\)"):
            bar.relative_addr(0xFE010000)


class TestBARResourcesIteration(unittest.TestCase):
    """test_bar_resources_iteration — Iterate resources."""

    def test_bar_resources_iteration(self):
        bar = BARMemoryMap(bar_index=0, size=0x10000)
        res1 = _MockResource("ctrl")
        res2 = _MockResource("status")
        res3 = _MockResource("data")
        bar.add_resource(res1, name="control", size=4, addr=0x0000)
        bar.add_resource(res2, name="status", size=4, addr=0x0004)
        bar.add_resource(res3, name="data", size=4, addr=0x0008)

        resources = list(bar.resources())
        self.assertEqual(len(resources), 3)

        # Check ordering and addresses
        self.assertIs(resources[0][0], res1)
        self.assertEqual(resources[0][1], ("control",))
        self.assertEqual(resources[0][2], (0x0000, 0x0004))

        self.assertIs(resources[1][0], res2)
        self.assertEqual(resources[1][1], ("status",))
        self.assertEqual(resources[1][2], (0x0004, 0x0008))

        self.assertIs(resources[2][0], res3)
        self.assertEqual(resources[2][1], ("data",))
        self.assertEqual(resources[2][2], (0x0008, 0x000C))


class TestBARCHeaderGeneration(unittest.TestCase):
    """test_bar_c_header_generation — Generate C header and verify content."""

    def test_bar_c_header_generation(self):
        bar = BARMemoryMap(bar_index=0, size=0x10000)
        res = _MockResource("ctrl")
        bar.add_resource(res, name="control", size=4, addr=0x0000)

        header = generate_bar_header(bar)

        # Verify header guard
        self.assertIn("#ifndef BAR_REGS_H", header)
        self.assertIn("#define BAR_REGS_H", header)
        self.assertIn("#endif /* BAR_REGS_H */", header)

        # Verify BAR defines
        self.assertIn("#define BAR0_SIZE  0x10000", header)
        self.assertIn("#define BAR0_INDEX 0", header)

        # Verify register offset
        self.assertIn("#define REG_CONTROL_OFFSET 0x0000", header)

        # Verify address macro
        self.assertIn("#define BAR0_ADDR(base, offset) ((base) + (offset))", header)

    def test_bar_c_header_custom_filename(self):
        bar = BARMemoryMap(bar_index=1, size=256)
        header = generate_bar_header(bar, file_name="my_regs.h")
        self.assertIn("#ifndef MY_REGS_H", header)
        self.assertIn("#define MY_REGS_H", header)

    def test_bar_c_header_wrong_type(self):
        with self.assertRaisesRegex(TypeError,
                r"bar_map must be a BARMemoryMap, not 'bad'"):
            generate_bar_header("bad")


class TestBARCHeaderMultipleResources(unittest.TestCase):
    """test_bar_c_header_multiple_resources — Generate header with multiple resources."""

    def test_bar_c_header_multiple_resources(self):
        bar = BARMemoryMap(bar_index=0, size=0x10000)
        res1 = _MockResource("ctrl")
        res2 = _MockResource("status")
        res3 = _MockResource("data")
        bar.add_resource(res1, name="control", size=4, addr=0x0000)
        bar.add_resource(res2, name="status", size=4, addr=0x0004)
        bar.add_resource(res3, name="data", size=4, addr=0x0008)

        header = generate_bar_header(bar)

        # Verify all register offsets are present
        self.assertIn("#define REG_CONTROL_OFFSET 0x0000", header)
        self.assertIn("#define REG_STATUS_OFFSET 0x0004", header)
        self.assertIn("#define REG_DATA_OFFSET 0x0008", header)

        # Verify BAR configuration
        self.assertIn("#define BAR0_SIZE  0x10000", header)
        self.assertIn("#define BAR0_INDEX 0", header)

        # Verify address macro
        self.assertIn("#define BAR0_ADDR(base, offset) ((base) + (offset))", header)

        # Verify header guard
        self.assertIn("#ifndef BAR_REGS_H", header)
        self.assertIn("#endif /* BAR_REGS_H */", header)


if __name__ == "__main__":
    unittest.main()
