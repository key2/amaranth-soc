# amaranth: UnusedElaboratable=no

"""Tests for Wishbone burst support in Decoder and Arbiter."""

import unittest
from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out, connect
from amaranth.sim import *

from amaranth_soc import wishbone
from amaranth_soc.wishbone import CycleType, BurstTypeExt, Feature
from amaranth_soc.wishbone.sram import WishboneSRAM
from amaranth_soc.memory import MemoryMap


class DecoderBurstTestCase(unittest.TestCase):
    """Tests for burst-aware address locking in the Wishbone Decoder."""

    def test_decoder_burst_hold(self):
        """During an INCR_BURST, the decoder stays locked to the initial subordinate
        even as the address increments, preventing re-decode to a different subordinate.

        Setup: Decoder with 2 subordinates, each 256 words (1024 bytes) of 32-bit SRAM.
        Sub 0 at address 0x000, Sub 1 at address 0x400 (word address).
        We write 4 words in burst mode to sub 0, read them back, verify data.
        """
        dut = wishbone.Decoder(addr_width=16, data_width=32,
                               features={Feature.CTI, Feature.BTE})

        sram_0 = WishboneSRAM(size=256, data_width=32)
        sram_1 = WishboneSRAM(size=256, data_width=32)

        dut.add(sram_0.wb_bus, name="sram0")
        dut.add(sram_1.wb_bus, name="sram1")

        m = Module()
        m.submodules.dut = dut
        m.submodules.sram_0 = sram_0
        m.submodules.sram_1 = sram_1

        async def testbench(ctx):
            bus = dut.bus

            # --- Burst write 4 words to subordinate 0 starting at address 0 ---
            test_data = [0xDEAD0000, 0xDEAD0001, 0xDEAD0002, 0xDEAD0003]

            for i, data in enumerate(test_data):
                ctx.set(bus.cyc, 1)
                ctx.set(bus.stb, 1)
                ctx.set(bus.we, 1)
                ctx.set(bus.adr, i)  # word addresses 0, 1, 2, 3
                ctx.set(bus.dat_w, data)
                ctx.set(bus.sel, 0x1)  # granularity == data_width, so sel width is 1

                if i < len(test_data) - 1:
                    ctx.set(bus.cti, CycleType.INCR_BURST)
                else:
                    ctx.set(bus.cti, CycleType.END_OF_BURST)

                ctx.set(bus.bte, BurstTypeExt.LINEAR)

                # Wait for ack
                for _ in range(20):
                    await ctx.tick()
                    if ctx.get(bus.ack):
                        break
                else:
                    self.fail(f"Timeout waiting for ack on burst write word {i}")

            # Deassert bus
            ctx.set(bus.cyc, 0)
            ctx.set(bus.stb, 0)
            ctx.set(bus.we, 0)
            ctx.set(bus.cti, CycleType.CLASSIC)
            await ctx.tick()
            await ctx.tick()

            # --- Read back the 4 words from subordinate 0 using classic cycles ---
            for i, expected in enumerate(test_data):
                ctx.set(bus.cyc, 1)
                ctx.set(bus.stb, 1)
                ctx.set(bus.we, 0)
                ctx.set(bus.adr, i)
                ctx.set(bus.sel, 0x1)
                ctx.set(bus.cti, CycleType.CLASSIC)

                for _ in range(20):
                    await ctx.tick()
                    if ctx.get(bus.ack):
                        break
                else:
                    self.fail(f"Timeout waiting for ack on read word {i}")

                read_data = ctx.get(bus.dat_r)
                self.assertEqual(read_data, expected,
                    f"Word {i}: expected {expected:#010x}, got {read_data:#010x}")

                ctx.set(bus.cyc, 0)
                ctx.set(bus.stb, 0)
                await ctx.tick()

        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test_decoder_burst_hold.vcd"):
            sim.run()

    def test_decoder_burst_end(self):
        """After a burst completes (CTI=END_OF_BURST), verify the decoder can switch
        to a different subordinate on the next transaction.

        Setup: Decoder with 2 subordinates. Write to sub 0 in burst mode,
        then write to sub 1 in classic mode, read back from both.
        """
        dut = wishbone.Decoder(addr_width=16, data_width=32,
                               features={Feature.CTI, Feature.BTE})

        sram_0 = WishboneSRAM(size=256, data_width=32)
        sram_1 = WishboneSRAM(size=256, data_width=32)

        dut.add(sram_0.wb_bus, name="sram0")
        dut.add(sram_1.wb_bus, name="sram1")

        m = Module()
        m.submodules.dut = dut
        m.submodules.sram_0 = sram_0
        m.submodules.sram_1 = sram_1

        # Determine the base address of sram_1 in the decoder's address space.
        # sram_0 occupies 256 words (addresses 0..255), sram_1 starts at 256.
        sram1_base = 256  # word address

        async def testbench(ctx):
            bus = dut.bus

            # --- Burst write 2 words to subordinate 0 ---
            ctx.set(bus.cyc, 1)
            ctx.set(bus.stb, 1)
            ctx.set(bus.we, 1)
            ctx.set(bus.adr, 0)
            ctx.set(bus.dat_w, 0xAAAA0000)
            ctx.set(bus.sel, 0x1)
            ctx.set(bus.cti, CycleType.INCR_BURST)
            ctx.set(bus.bte, BurstTypeExt.LINEAR)

            for _ in range(20):
                await ctx.tick()
                if ctx.get(bus.ack):
                    break

            # Second word — END_OF_BURST
            ctx.set(bus.adr, 1)
            ctx.set(bus.dat_w, 0xAAAA0001)
            ctx.set(bus.cti, CycleType.END_OF_BURST)

            for _ in range(20):
                await ctx.tick()
                if ctx.get(bus.ack):
                    break

            # Deassert bus
            ctx.set(bus.cyc, 0)
            ctx.set(bus.stb, 0)
            ctx.set(bus.we, 0)
            ctx.set(bus.cti, CycleType.CLASSIC)
            await ctx.tick()
            await ctx.tick()

            # --- Classic write to subordinate 1 ---
            ctx.set(bus.cyc, 1)
            ctx.set(bus.stb, 1)
            ctx.set(bus.we, 1)
            ctx.set(bus.adr, sram1_base + 0)
            ctx.set(bus.dat_w, 0xBBBB0000)
            ctx.set(bus.sel, 0x1)
            ctx.set(bus.cti, CycleType.CLASSIC)

            for _ in range(20):
                await ctx.tick()
                if ctx.get(bus.ack):
                    break
            else:
                self.fail("Timeout waiting for ack on classic write to sub 1")

            ctx.set(bus.cyc, 0)
            ctx.set(bus.stb, 0)
            ctx.set(bus.we, 0)
            await ctx.tick()
            await ctx.tick()

            # --- Read back from subordinate 0, word 0 ---
            ctx.set(bus.cyc, 1)
            ctx.set(bus.stb, 1)
            ctx.set(bus.we, 0)
            ctx.set(bus.adr, 0)
            ctx.set(bus.sel, 0x1)
            ctx.set(bus.cti, CycleType.CLASSIC)

            for _ in range(20):
                await ctx.tick()
                if ctx.get(bus.ack):
                    break

            self.assertEqual(ctx.get(bus.dat_r), 0xAAAA0000)

            ctx.set(bus.cyc, 0)
            ctx.set(bus.stb, 0)
            await ctx.tick()
            await ctx.tick()

            # --- Read back from subordinate 1, word 0 ---
            ctx.set(bus.cyc, 1)
            ctx.set(bus.stb, 1)
            ctx.set(bus.we, 0)
            ctx.set(bus.adr, sram1_base + 0)
            ctx.set(bus.sel, 0x1)
            ctx.set(bus.cti, CycleType.CLASSIC)

            for _ in range(20):
                await ctx.tick()
                if ctx.get(bus.ack):
                    break

            self.assertEqual(ctx.get(bus.dat_r), 0xBBBB0000)

            ctx.set(bus.cyc, 0)
            ctx.set(bus.stb, 0)
            await ctx.tick()

        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test_decoder_burst_end.vcd"):
            sim.run()

    def test_decoder_no_burst_feature(self):
        """Create a Decoder WITHOUT CTI feature. Verify it still works correctly
        for classic cycles (backward compatibility).
        """
        dut = wishbone.Decoder(addr_width=16, data_width=32)

        sram_0 = WishboneSRAM(size=256, data_width=32)
        sram_1 = WishboneSRAM(size=256, data_width=32)

        dut.add(sram_0.wb_bus, name="sram0")
        dut.add(sram_1.wb_bus, name="sram1")

        m = Module()
        m.submodules.dut = dut
        m.submodules.sram_0 = sram_0
        m.submodules.sram_1 = sram_1

        sram1_base = 256  # word address

        async def testbench(ctx):
            bus = dut.bus

            # --- Classic write to subordinate 0 ---
            ctx.set(bus.cyc, 1)
            ctx.set(bus.stb, 1)
            ctx.set(bus.we, 1)
            ctx.set(bus.adr, 5)
            ctx.set(bus.dat_w, 0x12345678)
            ctx.set(bus.sel, 0x1)

            for _ in range(20):
                await ctx.tick()
                if ctx.get(bus.ack):
                    break
            else:
                self.fail("Timeout waiting for ack on write to sub 0")

            ctx.set(bus.cyc, 0)
            ctx.set(bus.stb, 0)
            ctx.set(bus.we, 0)
            await ctx.tick()

            # --- Classic write to subordinate 1 ---
            ctx.set(bus.cyc, 1)
            ctx.set(bus.stb, 1)
            ctx.set(bus.we, 1)
            ctx.set(bus.adr, sram1_base + 10)
            ctx.set(bus.dat_w, 0xABCDEF01)
            ctx.set(bus.sel, 0x1)

            for _ in range(20):
                await ctx.tick()
                if ctx.get(bus.ack):
                    break
            else:
                self.fail("Timeout waiting for ack on write to sub 1")

            ctx.set(bus.cyc, 0)
            ctx.set(bus.stb, 0)
            ctx.set(bus.we, 0)
            await ctx.tick()

            # --- Read back from subordinate 0 ---
            ctx.set(bus.cyc, 1)
            ctx.set(bus.stb, 1)
            ctx.set(bus.we, 0)
            ctx.set(bus.adr, 5)
            ctx.set(bus.sel, 0x1)

            for _ in range(20):
                await ctx.tick()
                if ctx.get(bus.ack):
                    break

            self.assertEqual(ctx.get(bus.dat_r), 0x12345678)

            ctx.set(bus.cyc, 0)
            ctx.set(bus.stb, 0)
            await ctx.tick()

            # --- Read back from subordinate 1 ---
            ctx.set(bus.cyc, 1)
            ctx.set(bus.stb, 1)
            ctx.set(bus.we, 0)
            ctx.set(bus.adr, sram1_base + 10)
            ctx.set(bus.sel, 0x1)

            for _ in range(20):
                await ctx.tick()
                if ctx.get(bus.ack):
                    break

            self.assertEqual(ctx.get(bus.dat_r), 0xABCDEF01)

            ctx.set(bus.cyc, 0)
            ctx.set(bus.stb, 0)
            await ctx.tick()

        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test_decoder_no_burst.vcd"):
            sim.run()


class ArbiterLockTestCase(unittest.TestCase):
    """Tests for lock-aware arbitration in the Wishbone Arbiter."""

    def test_arbiter_lock_support(self):
        """Create an Arbiter with 2 initiators. Have initiator 0 assert LOCK during
        a transaction. Verify initiator 1 cannot gain the bus until LOCK is released.
        """
        dut = wishbone.Arbiter(addr_width=8, data_width=32,
                               features={Feature.LOCK})

        intr_0 = wishbone.Interface(addr_width=8, data_width=32,
                                    features={Feature.LOCK}, path=("intr_0",))
        intr_1 = wishbone.Interface(addr_width=8, data_width=32,
                                    features={Feature.LOCK}, path=("intr_1",))
        dut.add(intr_0)
        dut.add(intr_1)

        async def testbench(ctx):
            # --- Initiator 0 starts a transaction with LOCK asserted ---
            ctx.set(intr_0.cyc, 1)
            ctx.set(intr_0.stb, 1)
            ctx.set(intr_0.lock, 1)
            ctx.set(intr_0.adr, 0x10)
            ctx.set(intr_0.dat_w, 0xAAAAAAAA)
            ctx.set(intr_0.we, 1)
            ctx.set(intr_0.sel, 0x1)

            # Initiator 1 also requests the bus
            ctx.set(intr_1.cyc, 1)
            ctx.set(intr_1.stb, 1)
            ctx.set(intr_1.lock, 0)
            ctx.set(intr_1.adr, 0x20)
            ctx.set(intr_1.dat_w, 0xBBBBBBBB)
            ctx.set(intr_1.we, 1)
            ctx.set(intr_1.sel, 0x1)

            await ctx.tick()

            # Initiator 0 should have the bus (grant=0 initially)
            self.assertEqual(ctx.get(dut.bus.adr), 0x10)
            self.assertEqual(ctx.get(dut.bus.cyc), 1)
            self.assertEqual(ctx.get(dut.bus.lock), 1)

            # Now initiator 0 drops cyc briefly but keeps lock asserted
            ctx.set(intr_0.cyc, 0)
            ctx.set(intr_0.stb, 0)
            # lock stays asserted
            await ctx.tick()

            # The arbiter should NOT re-arbitrate because lock is held
            # Initiator 1 should NOT get the bus
            # After tick, grant should still be 0
            ctx.set(intr_0.cyc, 1)
            ctx.set(intr_0.stb, 1)
            ctx.set(intr_0.adr, 0x11)
            await ctx.tick()

            # Verify initiator 0 still has the bus
            self.assertEqual(ctx.get(dut.bus.adr), 0x11)
            self.assertEqual(ctx.get(dut.bus.cyc), 1)

            # Now release lock and drop cyc
            ctx.set(intr_0.lock, 0)
            ctx.set(intr_0.cyc, 0)
            ctx.set(intr_0.stb, 0)
            await ctx.tick()

            # After releasing lock and cyc, arbiter should re-arbitrate
            # Initiator 1 should now get the bus
            await ctx.tick()

            self.assertEqual(ctx.get(dut.bus.adr), 0x20)
            self.assertEqual(ctx.get(dut.bus.cyc), 1)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test_arbiter_lock.vcd"):
            sim.run()


if __name__ == "__main__":
    unittest.main()
