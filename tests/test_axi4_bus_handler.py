"""Tests for AXI4BusHandler and AXI4 Full SoC builder integration."""

import unittest

from amaranth import *
from amaranth.sim import Simulator

from amaranth_soc import BusStandard
from amaranth_soc.soc.bus_handler import AXI4BusHandler
from amaranth_soc.soc.builder import SoCBuilder, SoC
from amaranth_soc.axi.bus import AXI4Signature, AXIResp, AXIBurst
from amaranth_soc.axi.decoder import AXI4Decoder
from amaranth_soc.axi.sram import AXI4SRAM


# ---------------------------------------------------------------------------
# AXI4 simulation helpers for SoC bus (keeps valid asserted until ready)
# ---------------------------------------------------------------------------

async def _soc_axi4_write(ctx, bus, addr, data):
    """Perform a single-beat AXI4 write through the SoC bus.

    Drives AW and W channels simultaneously, keeps them asserted until
    the B response is received. This matches the AXI4 decoder's FSM timing
    where AW and W are forwarded in sequence.
    """
    # Drive AW + W + bready simultaneously
    ctx.set(bus.awaddr, addr)
    ctx.set(bus.awlen, 0)       # single beat
    ctx.set(bus.awsize, 2)      # 4 bytes
    ctx.set(bus.awburst, AXIBurst.INCR)
    ctx.set(bus.awprot, 0)
    ctx.set(bus.awlock, 0)
    ctx.set(bus.awcache, 0)
    ctx.set(bus.awqos, 0)
    ctx.set(bus.awregion, 0)
    ctx.set(bus.awvalid, 1)

    ctx.set(bus.wdata, data)
    ctx.set(bus.wstrb, 0xF)
    ctx.set(bus.wlast, 1)
    ctx.set(bus.wvalid, 1)

    ctx.set(bus.bready, 1)

    # Wait for B response (AW and W handshakes happen along the way)
    for _ in range(100):
        await ctx.tick()
        if ctx.get(bus.bvalid):
            break
    else:
        raise TimeoutError("AXI4 write: timed out waiting for bvalid")

    bresp = ctx.get(bus.bresp)

    # Clean up
    ctx.set(bus.awvalid, 0)
    ctx.set(bus.wvalid, 0)
    ctx.set(bus.wlast, 0)
    ctx.set(bus.bready, 0)
    await ctx.tick()
    return AXIResp(bresp)


async def _soc_axi4_read(ctx, bus, addr):
    """Perform a single-beat AXI4 read through the SoC bus.

    Drives AR and rready simultaneously, keeps them asserted until
    the R response is received.
    """
    # Drive AR + rready simultaneously
    ctx.set(bus.araddr, addr)
    ctx.set(bus.arlen, 0)       # single beat
    ctx.set(bus.arsize, 2)      # 4 bytes
    ctx.set(bus.arburst, AXIBurst.INCR)
    ctx.set(bus.arprot, 0)
    ctx.set(bus.arlock, 0)
    ctx.set(bus.arcache, 0)
    ctx.set(bus.arqos, 0)
    ctx.set(bus.arregion, 0)
    ctx.set(bus.arvalid, 1)
    ctx.set(bus.rready, 1)

    # Wait for R response (AR handshake happens along the way)
    for _ in range(100):
        await ctx.tick()
        if ctx.get(bus.rvalid):
            break
    else:
        raise TimeoutError("AXI4 read: timed out waiting for rvalid")

    rdata = ctx.get(bus.rdata)
    rresp = ctx.get(bus.rresp)

    # Clean up
    ctx.set(bus.arvalid, 0)
    ctx.set(bus.rready, 0)
    await ctx.tick()
    return rdata, AXIResp(rresp)


class TestAXI4BusHandler(unittest.TestCase):
    """Test AXI4BusHandler construction and methods."""

    def test_axi4_handler_create(self):
        """Constructor with valid params."""
        handler = AXI4BusHandler(addr_width=16, data_width=32)
        self.assertEqual(handler.addr_width, 16)
        self.assertEqual(handler.data_width, 32)
        self.assertEqual(handler.id_width, 0)

    def test_axi4_handler_create_with_id(self):
        """Constructor with id_width=4."""
        handler = AXI4BusHandler(addr_width=16, data_width=32, id_width=4)
        self.assertEqual(handler.addr_width, 16)
        self.assertEqual(handler.data_width, 32)
        self.assertEqual(handler.id_width, 4)

    def test_axi4_handler_bus_signature(self):
        """Verify returns AXI4Signature."""
        handler = AXI4BusHandler(addr_width=16, data_width=32)
        sig = handler.bus_signature()
        self.assertIsInstance(sig, AXI4Signature)
        self.assertEqual(sig.addr_width, 16)
        self.assertEqual(sig.data_width, 32)
        self.assertEqual(sig.id_width, 0)

    def test_axi4_handler_bus_signature_with_id(self):
        """Verify returns AXI4Signature with id_width."""
        handler = AXI4BusHandler(addr_width=16, data_width=32, id_width=4)
        sig = handler.bus_signature()
        self.assertIsInstance(sig, AXI4Signature)
        self.assertEqual(sig.id_width, 4)

    def test_axi4_handler_create_decoder(self):
        """Verify returns AXI4Decoder."""
        handler = AXI4BusHandler(addr_width=16, data_width=32)
        decoder = handler.create_decoder()
        self.assertIsInstance(decoder, AXI4Decoder)

    def test_axi4_handler_create_sram(self):
        """Verify returns AXI4SRAM."""
        handler = AXI4BusHandler(addr_width=16, data_width=32)
        sram = handler.create_sram(size=1024, writable=True)
        self.assertIsInstance(sram, AXI4SRAM)
        self.assertEqual(sram.size, 1024)

    def test_axi4_handler_get_sram_bus(self):
        """Verify returns sram.bus."""
        handler = AXI4BusHandler(addr_width=16, data_width=32)
        sram = handler.create_sram(size=256, writable=True)
        bus = handler.get_sram_bus(sram)
        self.assertIs(bus, sram.bus)


class TestSoCBuilderAXI4(unittest.TestCase):
    """Test SoCBuilder with AXI4 Full bus standard."""

    def test_soc_builder_axi4(self):
        """Create SoCBuilder with bus_standard=BusStandard.AXI4, build it."""
        builder = SoCBuilder(
            bus_standard=BusStandard.AXI4,
            bus_addr_width=16,
            bus_data_width=32,
        )
        builder.add_rom(size=1024, init=[0] * 256)
        builder.add_ram(size=2048)
        soc = builder.build()

        self.assertIsInstance(soc, SoC)
        self.assertEqual(soc.bus_standard, BusStandard.AXI4)
        self.assertIsInstance(soc.bus_handler, AXI4BusHandler)
        self.assertEqual(soc.bus_handler.id_width, 0)

    def test_soc_builder_axi4_with_id(self):
        """Create SoCBuilder with bus_standard=BusStandard.AXI4 and bus_id_width=4."""
        builder = SoCBuilder(
            bus_standard=BusStandard.AXI4,
            bus_addr_width=16,
            bus_data_width=32,
            bus_id_width=4,
        )
        builder.add_rom(size=1024, init=[0] * 256)
        builder.add_ram(size=2048)
        soc = builder.build()

        self.assertIsInstance(soc, SoC)
        self.assertIsInstance(soc.bus_handler, AXI4BusHandler)
        self.assertEqual(soc.bus_handler.id_width, 4)

    def test_soc_axi4_elaborate(self):
        """Build and elaborate an AXI4 SoC, verify it converts to RTLIL."""
        builder = SoCBuilder(
            bus_standard=BusStandard.AXI4,
            bus_addr_width=16,
            bus_data_width=32,
        )
        builder.add_rom(size=1024, init=[0] * 256)
        builder.add_ram(size=2048)
        soc = builder.build()

        from amaranth.back.rtlil import convert
        rtlil = convert(soc)
        self.assertIsInstance(rtlil, str)
        self.assertGreater(len(rtlil), 0)

    def test_soc_axi4_elaborate_with_id(self):
        """Build and elaborate an AXI4 SoC with ID width, verify RTLIL."""
        builder = SoCBuilder(
            bus_standard=BusStandard.AXI4,
            bus_addr_width=16,
            bus_data_width=32,
            bus_id_width=4,
        )
        builder.add_rom(size=1024, init=[0] * 256)
        builder.add_ram(size=2048)
        soc = builder.build()

        from amaranth.back.rtlil import convert
        rtlil = convert(soc)
        self.assertIsInstance(rtlil, str)
        self.assertGreater(len(rtlil), 0)

    def test_soc_axi4_sim(self):
        """Simulation test: write data to RAM through AXI4 bus, read it back.

        Builds an AXI4 SoC with ROM and RAM, writes two values to RAM,
        reads them back, and verifies correctness. Also reads from ROM
        to verify the read path works for both memory regions.
        """
        builder = SoCBuilder(
            bus_standard=BusStandard.AXI4,
            bus_addr_width=16,
            bus_data_width=32,
        )
        # ROM at address 0x0000 (1024 bytes)
        builder.add_rom(size=1024)
        # RAM at address 0x0400 (auto-allocated after ROM)
        builder.add_ram(size=1024)
        soc = builder.build()

        sim = Simulator(soc)
        sim.add_clock(1e-6)

        results = {}

        async def testbench(ctx):
            bus = soc.bus

            # Wait a few cycles for reset
            for _ in range(5):
                await ctx.tick()

            # Write 0x12345678 to RAM at offset 0 (RAM base = 0x0400)
            resp = await _soc_axi4_write(ctx, bus, 0x0400, 0x12345678)
            assert resp == AXIResp.OKAY, f"Write resp: {resp}"

            # Write 0xCAFEBABE to RAM at offset 4 (0x0404)
            resp = await _soc_axi4_write(ctx, bus, 0x0404, 0xCAFEBABE)
            assert resp == AXIResp.OKAY, f"Write resp: {resp}"

            # Read back from RAM offset 0
            data, resp = await _soc_axi4_read(ctx, bus, 0x0400)
            assert resp == AXIResp.OKAY, f"Read resp: {resp}"
            results["ram_0"] = data

            # Read back from RAM offset 4
            data, resp = await _soc_axi4_read(ctx, bus, 0x0404)
            assert resp == AXIResp.OKAY, f"Read resp: {resp}"
            results["ram_4"] = data

            # Read from ROM offset 0 (uninitialized, should be 0)
            data, resp = await _soc_axi4_read(ctx, bus, 0x0000)
            assert resp == AXIResp.OKAY, f"Read resp: {resp}"
            results["rom_0"] = data

        sim.add_testbench(testbench)
        with sim.write_vcd("test_axi4_soc_sim.vcd"):
            sim.run()

        # Verify RAM write/read roundtrip
        self.assertEqual(results["ram_0"], 0x12345678,
                         f"RAM[0] = {results['ram_0']:#010x}, expected 0x12345678")
        self.assertEqual(results["ram_4"], 0xCAFEBABE,
                         f"RAM[4] = {results['ram_4']:#010x}, expected 0xCAFEBABE")
        # ROM read should succeed (value is 0 since AXI4SRAM doesn't support init)
        self.assertEqual(results["rom_0"], 0x00000000,
                         f"ROM[0] = {results['rom_0']:#010x}, expected 0x00000000")


if __name__ == "__main__":
    unittest.main()
