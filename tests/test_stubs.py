"""Tests for stub file cleanup — verifies implemented modules and docstring stubs."""

import unittest
import importlib


class TestAXI4LiteCSRBridgeReexport(unittest.TestCase):
    """Test that AXI4LiteCSRBridge is properly re-exported from bridge package."""

    def test_import_from_bridge_axi_to_csr(self):
        """AXI4LiteCSRBridge can be imported from amaranth_soc.bridge.axi_to_csr."""
        from amaranth_soc.bridge.axi_to_csr import AXI4LiteCSRBridge
        self.assertIsNotNone(AXI4LiteCSRBridge)

    def test_same_class_as_csr_axi_lite(self):
        """AXI4LiteCSRBridge from bridge.axi_to_csr is the same class as csr.axi_lite."""
        from amaranth_soc.bridge.axi_to_csr import AXI4LiteCSRBridge as BridgeClass
        from amaranth_soc.csr.axi_lite import AXI4LiteCSRBridge as CSRClass
        self.assertIs(BridgeClass, CSRClass)

    def test_import_from_bridge_package(self):
        """AXI4LiteCSRBridge can be imported from amaranth_soc.bridge."""
        from amaranth_soc.bridge import AXI4LiteCSRBridge
        self.assertIsNotNone(AXI4LiteCSRBridge)


class TestPeripheralBase(unittest.TestCase):
    """Test the Peripheral base class."""

    def test_instantiate_with_name(self):
        """Peripheral base class can be instantiated with a name."""
        from amaranth_soc.periph.base import Peripheral
        p = Peripheral("test_periph")
        self.assertEqual(p.periph_name, "test_periph")

    def test_name_must_be_string(self):
        """Peripheral raises TypeError if name is not a string."""
        from amaranth_soc.periph.base import Peripheral
        with self.assertRaises(TypeError):
            Peripheral(42)

    def test_import_from_module(self):
        """Peripheral can be imported from amaranth_soc.periph.base."""
        from amaranth_soc.periph.base import Peripheral
        self.assertTrue(callable(Peripheral))


class TestSoCPlatform(unittest.TestCase):
    """Test the SoCPlatform wrapper."""

    def test_instantiate_with_mock_platform(self):
        """SoCPlatform can be instantiated with a mock platform object."""
        from amaranth_soc.soc.platform import SoCPlatform

        class MockPlatform:
            pass

        mock = MockPlatform()
        soc_plat = SoCPlatform(mock)
        self.assertIs(soc_plat.platform, mock)

    def test_import_from_module(self):
        """SoCPlatform can be imported from amaranth_soc.soc.platform."""
        from amaranth_soc.soc.platform import SoCPlatform
        self.assertTrue(callable(SoCPlatform))


class TestCPUStubs(unittest.TestCase):
    """Test that CPU stub modules can be imported without errors."""

    def test_import_cpu_package(self):
        """amaranth_soc.cpu can be imported."""
        import amaranth_soc.cpu
        self.assertIsNotNone(amaranth_soc.cpu.__doc__)

    def test_import_cpu_wrapper(self):
        """amaranth_soc.cpu.wrapper can be imported."""
        import amaranth_soc.cpu.wrapper
        self.assertIsNotNone(amaranth_soc.cpu.wrapper.__doc__)

    def test_import_cpu_wb_wrapper(self):
        """amaranth_soc.cpu.wb_wrapper can be imported."""
        import amaranth_soc.cpu.wb_wrapper
        self.assertIsNotNone(amaranth_soc.cpu.wb_wrapper.__doc__)

    def test_import_cpu_axi_wrapper(self):
        """amaranth_soc.cpu.axi_wrapper can be imported."""
        import amaranth_soc.cpu.axi_wrapper
        self.assertIsNotNone(amaranth_soc.cpu.axi_wrapper.__doc__)

    def test_import_cpu_vexriscv(self):
        """amaranth_soc.cpu.vexriscv can be imported."""
        import amaranth_soc.cpu.vexriscv
        self.assertIsNotNone(amaranth_soc.cpu.vexriscv.__doc__)


class TestExportStubs(unittest.TestCase):
    """Test that export stub modules can be imported without errors."""

    def test_import_export_devicetree(self):
        """amaranth_soc.export.devicetree can be imported."""
        import amaranth_soc.export.devicetree
        self.assertIsNotNone(amaranth_soc.export.devicetree.__doc__)

    def test_import_export_linker(self):
        """amaranth_soc.export.linker can be imported."""
        import amaranth_soc.export.linker
        self.assertIsNotNone(amaranth_soc.export.linker.__doc__)

    def test_import_export_svd(self):
        """amaranth_soc.export.svd can be imported."""
        import amaranth_soc.export.svd
        self.assertIsNotNone(amaranth_soc.export.svd.__doc__)


class TestPeriphStubs(unittest.TestCase):
    """Test that periph stub modules can be imported without errors."""

    def test_import_periph_gpio(self):
        """amaranth_soc.periph.gpio can be imported."""
        import amaranth_soc.periph.gpio
        self.assertIsNotNone(amaranth_soc.periph.gpio.__doc__)

    def test_import_periph_uart(self):
        """amaranth_soc.periph.uart can be imported."""
        import amaranth_soc.periph.uart
        self.assertIsNotNone(amaranth_soc.periph.uart.__doc__)


if __name__ == "__main__":
    unittest.main()
