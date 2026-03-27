"""Tests for bus protocol checkers."""

import unittest

from amaranth import *
from amaranth.sim import Simulator

from amaranth_soc.sim.protocol_checker import (
    WishboneChecker, AXI4LiteChecker, AXI4Checker,
)


# ---------------------------------------------------------------------------
# Wishbone checker tests
# ---------------------------------------------------------------------------

class TestWishboneCheckerCreate(unittest.TestCase):
    """test_wb_checker_create — Constructor."""

    def test_basic_construction(self):
        checker = WishboneChecker(addr_width=16, data_width=32)
        self.assertEqual(checker.addr_width, 16)
        self.assertEqual(checker.data_width, 32)

    def test_construction_with_features(self):
        from amaranth_soc.wishbone.bus import Feature
        checker = WishboneChecker(
            addr_width=14, data_width=32,
            features={Feature.ERR},
        )
        self.assertEqual(checker.addr_width, 14)
        self.assertEqual(checker.data_width, 32)

    def test_import_from_package(self):
        from amaranth_soc.sim import WishboneChecker as WC
        self.assertIs(WC, WishboneChecker)


class TestWishboneCheckerSimNoViolation(unittest.TestCase):
    """test_wb_checker_sim_no_violation — Normal Wishbone transaction, violations=0."""

    def test_no_violation(self):
        checker = WishboneChecker(addr_width=16, data_width=32)

        async def testbench(ctx):
            # Perform a normal write: cyc=1, stb=1, we=1
            ctx.set(checker.bus.cyc, 1)
            ctx.set(checker.bus.stb, 1)
            ctx.set(checker.bus.we, 1)
            ctx.set(checker.bus.adr, 0x100)
            ctx.set(checker.bus.dat_w, 0xDEADBEEF)
            ctx.set(checker.bus.sel, 0xF)
            await ctx.tick()

            # Simulate ack from target
            ctx.set(checker.bus.ack, 1)
            await ctx.tick()

            # Deassert
            ctx.set(checker.bus.cyc, 0)
            ctx.set(checker.bus.stb, 0)
            ctx.set(checker.bus.ack, 0)
            await ctx.tick()
            await ctx.tick()

            # Check violations
            violations = ctx.get(checker.violations)
            assert violations == 0, f"Expected 0 violations, got {violations}"

        sim = Simulator(checker)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_wb_checker_no_violation.vcd"):
            sim.run()


class TestWishboneCheckerSimStbWithoutCyc(unittest.TestCase):
    """test_wb_checker_sim_stb_without_cyc — Assert stb without cyc, violations>0."""

    def test_stb_without_cyc(self):
        checker = WishboneChecker(addr_width=16, data_width=32)

        async def testbench(ctx):
            # Violate: stb=1 but cyc=0
            ctx.set(checker.bus.cyc, 0)
            ctx.set(checker.bus.stb, 1)
            await ctx.tick()
            await ctx.tick()  # violation registered on sync edge
            await ctx.tick()

            # Deassert
            ctx.set(checker.bus.stb, 0)
            await ctx.tick()
            await ctx.tick()

            violations = ctx.get(checker.violations)
            assert violations > 0, f"Expected violations > 0, got {violations}"

        sim = Simulator(checker)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_wb_checker_stb_no_cyc.vcd"):
            sim.run()


# ---------------------------------------------------------------------------
# AXI4-Lite checker tests
# ---------------------------------------------------------------------------

class TestAXI4LiteCheckerCreate(unittest.TestCase):
    """test_axi4lite_checker_create — Constructor."""

    def test_basic_construction(self):
        checker = AXI4LiteChecker(addr_width=16, data_width=32)
        self.assertEqual(checker.addr_width, 16)
        self.assertEqual(checker.data_width, 32)

    def test_import_from_package(self):
        from amaranth_soc.sim import AXI4LiteChecker as ALC
        self.assertIs(ALC, AXI4LiteChecker)


class TestAXI4LiteCheckerSimNoViolation(unittest.TestCase):
    """test_axi4lite_checker_sim_no_violation — Normal AXI4-Lite transaction, violations=0."""

    def test_no_violation_read(self):
        checker = AXI4LiteChecker(addr_width=16, data_width=32)

        async def testbench(ctx):
            # AR handshake
            ctx.set(checker.bus.arvalid, 1)
            ctx.set(checker.bus.arready, 1)
            ctx.set(checker.bus.araddr, 0x100)
            await ctx.tick()

            # Deassert AR
            ctx.set(checker.bus.arvalid, 0)
            ctx.set(checker.bus.arready, 0)
            await ctx.tick()

            # R response
            ctx.set(checker.bus.rvalid, 1)
            ctx.set(checker.bus.rready, 1)
            ctx.set(checker.bus.rdata, 0xCAFEBABE)
            await ctx.tick()

            # Deassert R
            ctx.set(checker.bus.rvalid, 0)
            ctx.set(checker.bus.rready, 0)
            await ctx.tick()
            await ctx.tick()

            violations = ctx.get(checker.violations)
            assert violations == 0, f"Expected 0 violations, got {violations}"

        sim = Simulator(checker)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_axi4lite_checker_no_violation.vcd"):
            sim.run()

    def test_no_violation_write(self):
        checker = AXI4LiteChecker(addr_width=16, data_width=32)

        async def testbench(ctx):
            # AW handshake
            ctx.set(checker.bus.awvalid, 1)
            ctx.set(checker.bus.awready, 1)
            ctx.set(checker.bus.awaddr, 0x200)
            await ctx.tick()

            # Deassert AW
            ctx.set(checker.bus.awvalid, 0)
            ctx.set(checker.bus.awready, 0)

            # W handshake
            ctx.set(checker.bus.wvalid, 1)
            ctx.set(checker.bus.wready, 1)
            ctx.set(checker.bus.wdata, 0xDEADBEEF)
            await ctx.tick()

            ctx.set(checker.bus.wvalid, 0)
            ctx.set(checker.bus.wready, 0)

            # B response
            ctx.set(checker.bus.bvalid, 1)
            ctx.set(checker.bus.bready, 1)
            await ctx.tick()

            ctx.set(checker.bus.bvalid, 0)
            ctx.set(checker.bus.bready, 0)
            await ctx.tick()
            await ctx.tick()

            violations = ctx.get(checker.violations)
            assert violations == 0, f"Expected 0 violations, got {violations}"

        sim = Simulator(checker)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_axi4lite_checker_write_no_violation.vcd"):
            sim.run()


# ---------------------------------------------------------------------------
# AXI4 Full checker tests
# ---------------------------------------------------------------------------

class TestAXI4CheckerCreate(unittest.TestCase):
    """test_axi4_checker_create — Constructor."""

    def test_basic_construction(self):
        checker = AXI4Checker(addr_width=32, data_width=32)
        self.assertEqual(checker.addr_width, 32)
        self.assertEqual(checker.data_width, 32)
        self.assertEqual(checker.id_width, 0)

    def test_construction_with_id(self):
        checker = AXI4Checker(addr_width=32, data_width=64, id_width=4)
        self.assertEqual(checker.id_width, 4)

    def test_import_from_package(self):
        from amaranth_soc.sim import AXI4Checker as AC
        self.assertIs(AC, AXI4Checker)


class TestAXI4CheckerSimNoViolation(unittest.TestCase):
    """test_axi4_checker_sim_no_violation — Normal AXI4 burst, violations=0."""

    def test_no_violation_write_burst(self):
        """4-beat write burst with correct wlast on beat 3 (awlen=3)."""
        checker = AXI4Checker(addr_width=32, data_width=32)

        async def testbench(ctx):
            # AW handshake: awlen=3 means 4 beats
            ctx.set(checker.bus.awvalid, 1)
            ctx.set(checker.bus.awready, 1)
            ctx.set(checker.bus.awaddr, 0x0)
            ctx.set(checker.bus.awlen, 3)
            ctx.set(checker.bus.awsize, 2)  # 4 bytes
            ctx.set(checker.bus.awburst, 1)  # INCR
            await ctx.tick()

            ctx.set(checker.bus.awvalid, 0)
            ctx.set(checker.bus.awready, 0)

            # 4 W beats
            for beat in range(4):
                ctx.set(checker.bus.wvalid, 1)
                ctx.set(checker.bus.wready, 1)
                ctx.set(checker.bus.wdata, 0x1000 + beat)
                ctx.set(checker.bus.wstrb, 0xF)
                if beat == 3:
                    ctx.set(checker.bus.wlast, 1)
                else:
                    ctx.set(checker.bus.wlast, 0)
                await ctx.tick()

            ctx.set(checker.bus.wvalid, 0)
            ctx.set(checker.bus.wready, 0)
            ctx.set(checker.bus.wlast, 0)

            # B response
            ctx.set(checker.bus.bvalid, 1)
            ctx.set(checker.bus.bready, 1)
            await ctx.tick()

            ctx.set(checker.bus.bvalid, 0)
            ctx.set(checker.bus.bready, 0)
            await ctx.tick()
            await ctx.tick()

            violations = ctx.get(checker.violations)
            assert violations == 0, f"Expected 0 violations, got {violations}"

        sim = Simulator(checker)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_axi4_checker_no_violation.vcd"):
            sim.run()

    def test_no_violation_read_burst(self):
        """4-beat read burst with correct rlast on beat 3 (arlen=3)."""
        checker = AXI4Checker(addr_width=32, data_width=32)

        async def testbench(ctx):
            # AR handshake: arlen=3 means 4 beats
            ctx.set(checker.bus.arvalid, 1)
            ctx.set(checker.bus.arready, 1)
            ctx.set(checker.bus.araddr, 0x0)
            ctx.set(checker.bus.arlen, 3)
            ctx.set(checker.bus.arsize, 2)
            ctx.set(checker.bus.arburst, 1)
            await ctx.tick()

            ctx.set(checker.bus.arvalid, 0)
            ctx.set(checker.bus.arready, 0)

            # 4 R beats
            for beat in range(4):
                ctx.set(checker.bus.rvalid, 1)
                ctx.set(checker.bus.rready, 1)
                ctx.set(checker.bus.rdata, 0x2000 + beat)
                if beat == 3:
                    ctx.set(checker.bus.rlast, 1)
                else:
                    ctx.set(checker.bus.rlast, 0)
                await ctx.tick()

            ctx.set(checker.bus.rvalid, 0)
            ctx.set(checker.bus.rready, 0)
            ctx.set(checker.bus.rlast, 0)
            await ctx.tick()
            await ctx.tick()

            violations = ctx.get(checker.violations)
            assert violations == 0, f"Expected 0 violations, got {violations}"

        sim = Simulator(checker)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_axi4_checker_read_no_violation.vcd"):
            sim.run()


if __name__ == "__main__":
    unittest.main()
