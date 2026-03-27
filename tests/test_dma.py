"""Tests for DMA subsystem: DMAReader, DMAWriter, ScatterGatherDMA."""

import unittest
from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.lib.memory import MemoryData, Memory
from amaranth.sim import Simulator
from amaranth.utils import exact_log2

from amaranth_soc.dma.common import DMAStatus, DMADescriptorLayout
from amaranth_soc.dma.reader import DMAReader
from amaranth_soc.dma.writer import DMAWriter
from amaranth_soc.dma.scatter_gather import ScatterGatherDMA
from amaranth_soc.axi.sram import AXI4SRAM
from amaranth_soc.axi.bus import AXI4Signature, AXIBurst, AXISize, AXIResp


# ---------------------------------------------------------------------------
# AXI4 bus wiring helper
# ---------------------------------------------------------------------------

def _wire_master_to_slave(m, master, slave):
    """Wire an AXI4 master port (Out-oriented) to a slave port (In-oriented).

    Master Out signals -> Slave In signals (directly).
    Slave Out signals -> Master In signals (feedback).
    """
    # Master-driven (Out in master signature) -> Slave receives
    out_signals = [
        "awaddr", "awprot", "awvalid", "awlen", "awsize", "awburst",
        "awlock", "awcache", "awqos", "awregion",
        "wdata", "wstrb", "wvalid", "wlast",
        "bready",
        "araddr", "arprot", "arvalid", "arlen", "arsize", "arburst",
        "arlock", "arcache", "arqos", "arregion",
        "rready",
    ]
    # Slave-driven (In in master signature) -> Master receives
    in_signals = [
        "awready",
        "wready",
        "bresp", "bvalid",
        "arready",
        "rdata", "rresp", "rvalid", "rlast",
    ]

    for name in out_signals:
        if hasattr(master, name) and hasattr(slave, name):
            m.d.comb += getattr(slave, name).eq(getattr(master, name))

    for name in in_signals:
        if hasattr(master, name) and hasattr(slave, name):
            m.d.comb += getattr(master, name).eq(getattr(slave, name))


def _wire_write_channels(m, master, slave):
    """Wire only AXI4 write channels (AW, W, B) from master to slave.

    Leaves read channels (AR, R) unwired so the testbench can drive them.
    """
    aw_signals = [
        "awaddr", "awprot", "awvalid", "awlen", "awsize", "awburst",
        "awlock", "awcache", "awqos", "awregion",
    ]
    w_signals = ["wdata", "wstrb", "wvalid", "wlast"]
    b_out = ["bready"]
    b_in = ["bresp", "bvalid"]

    for name in aw_signals + w_signals + b_out:
        if hasattr(master, name) and hasattr(slave, name):
            m.d.comb += getattr(slave, name).eq(getattr(master, name))

    for name in ["awready", "wready"] + b_in:
        if hasattr(master, name) and hasattr(slave, name):
            m.d.comb += getattr(master, name).eq(getattr(slave, name))


def _wire_read_channels(m, master, slave):
    """Wire only AXI4 read channels (AR, R) from master to slave.

    Leaves write channels (AW, W, B) unwired so the testbench can drive them.
    """
    ar_signals = [
        "araddr", "arprot", "arvalid", "arlen", "arsize", "arburst",
        "arlock", "arcache", "arqos", "arregion",
    ]
    r_out = ["rready"]
    r_in = ["rdata", "rresp", "rvalid", "rlast"]

    for name in ar_signals + r_out:
        if hasattr(master, name) and hasattr(slave, name):
            m.d.comb += getattr(slave, name).eq(getattr(master, name))

    for name in ["arready"] + r_in:
        if hasattr(master, name) and hasattr(slave, name):
            m.d.comb += getattr(master, name).eq(getattr(slave, name))


# ---------------------------------------------------------------------------
# Test harnesses
# ---------------------------------------------------------------------------

class DMAReaderTestHarness(Elaboratable):
    """Wires a DMAReader to an AXI4SRAM (pre-loaded via init) for simulation.

    Only the read channels are wired from the reader to the SRAM.
    The write channels on the SRAM are left free for testbench pre-loading.
    """

    def __init__(self, *, addr_width=10, data_width=32, sram_size=1024,
                 max_burst_len=16, init=()):
        self.reader = DMAReader(addr_width=addr_width, data_width=data_width,
                                max_burst_len=max_burst_len)
        self.sram = AXI4SRAM(size=sram_size, data_width=data_width)
        self._init = init

    def elaborate(self, platform):
        m = Module()
        m.submodules.reader = reader = self.reader
        m.submodules.sram = sram = self.sram

        # Wire only read channels: reader (master) -> sram (slave)
        _wire_read_channels(m, reader.bus, sram.bus)
        return m


class DMAWriterTestHarness(Elaboratable):
    """Wires a DMAWriter to an AXI4SRAM for simulation.

    Only the write channels are wired from the writer to the SRAM.
    The read channels on the SRAM are left free for testbench verification.
    """

    def __init__(self, *, addr_width=10, data_width=32, sram_size=1024,
                 max_burst_len=16):
        self.writer = DMAWriter(addr_width=addr_width, data_width=data_width,
                                max_burst_len=max_burst_len)
        self.sram = AXI4SRAM(size=sram_size, data_width=data_width)

    def elaborate(self, platform):
        m = Module()
        m.submodules.writer = writer = self.writer
        m.submodules.sram = sram = self.sram

        # Wire only write channels: writer (master) -> sram (slave)
        _wire_write_channels(m, writer.bus, sram.bus)
        return m


class ScatterGatherTestHarness(Elaboratable):
    """Wires a ScatterGatherDMA to source and destination AXI4 SRAMs.

    Source SRAM: SG read_bus connected via read channels only (write channels
    free for testbench pre-loading).
    Dest SRAM: SG write_bus connected via write channels only (read channels
    free for testbench verification).
    """

    def __init__(self, *, addr_width=10, data_width=32, sram_size=1024,
                 max_descriptors=16, max_burst_len=16):
        self.sg = ScatterGatherDMA(
            addr_width=addr_width, data_width=data_width,
            max_descriptors=max_descriptors, max_burst_len=max_burst_len)
        self.src_sram = AXI4SRAM(size=sram_size, data_width=data_width)
        self.dst_sram = AXI4SRAM(size=sram_size, data_width=data_width)

    def elaborate(self, platform):
        m = Module()
        m.submodules.sg = sg = self.sg
        m.submodules.src_sram = src_sram = self.src_sram
        m.submodules.dst_sram = dst_sram = self.dst_sram

        # SG read_bus -> source SRAM (read channels only)
        _wire_read_channels(m, sg.read_bus, src_sram.bus)
        # SG write_bus -> destination SRAM (write channels only)
        _wire_write_channels(m, sg.write_bus, dst_sram.bus)
        return m


# ---------------------------------------------------------------------------
# AXI4 burst helpers for testbench pre-loading / verification
# ---------------------------------------------------------------------------

async def axi4_write_burst_tb(ctx, bus, addr, data_list, burst=AXIBurst.INCR,
                               size=AXISize.B4):
    """Perform an AXI4 burst write on a slave bus port from a testbench.

    Used to pre-load SRAM contents when write channels are free.
    """
    awlen = len(data_list) - 1

    # AW phase (don't set bready yet to avoid consuming B response early)
    ctx.set(bus.awaddr, addr)
    ctx.set(bus.awlen, awlen)
    ctx.set(bus.awsize, size)
    ctx.set(bus.awburst, burst)
    ctx.set(bus.awvalid, 1)
    await ctx.tick()
    ctx.set(bus.awvalid, 0)

    # W phase
    for i, data in enumerate(data_list):
        ctx.set(bus.wdata, data)
        ctx.set(bus.wstrb, 0xF)
        ctx.set(bus.wvalid, 1)
        ctx.set(bus.wlast, 1 if i == awlen else 0)
        await ctx.tick()

    ctx.set(bus.wvalid, 0)
    ctx.set(bus.wlast, 0)

    # After the last W beat tick, the SRAM transitions to WR_RESP.
    # bvalid should now be combinationally 1. Wait for it, then assert bready.
    for _ in range(100):
        if ctx.get(bus.bvalid):
            ctx.set(bus.bready, 1)
            await ctx.tick()
            ctx.set(bus.bready, 0)
            await ctx.tick()
            return
        await ctx.tick()
    raise TimeoutError("AXI4 write: timed out waiting for bvalid")


async def axi4_read_burst_tb(ctx, bus, addr, length, burst=AXIBurst.INCR,
                              size=AXISize.B4):
    """Perform an AXI4 burst read on a slave bus port from a testbench.

    Used to verify SRAM contents when read channels are free.
    Returns list of data values.

    The AXI4SRAM read path:
    - RD_IDLE: accepts AR, transitions to RD_MEM
    - RD_MEM: issues memory read enable, transitions to RD_DATA
    - RD_DATA: asserts rvalid with data, waits for rready
    """
    arlen = length - 1

    ctx.set(bus.araddr, addr)
    ctx.set(bus.arlen, arlen)
    ctx.set(bus.arsize, size)
    ctx.set(bus.arburst, burst)
    ctx.set(bus.arvalid, 1)
    await ctx.tick()
    ctx.set(bus.arvalid, 0)

    # Collect R beats. We set rready=1 and wait for rvalid.
    # The SRAM goes RD_MEM -> RD_DATA (rvalid=1). When rready & rvalid,
    # it either goes to RD_IDLE (last beat) or RD_MEM (next beat).
    results = []
    ctx.set(bus.rready, 1)
    for beat in range(length):
        for _ in range(100):
            await ctx.tick()
            if ctx.get(bus.rvalid):
                results.append(ctx.get(bus.rdata))
                break
        else:
            raise TimeoutError(f"AXI4 read: timed out on beat {beat}")

    ctx.set(bus.rready, 0)
    await ctx.tick()
    return results


# ===========================================================================
# Construction tests
# ===========================================================================

class TestDMAReaderCreate(unittest.TestCase):
    """Test DMAReader construction."""

    def test_default_params(self):
        dut = DMAReader(addr_width=32, data_width=32)
        self.assertEqual(dut.addr_width, 32)
        self.assertEqual(dut.data_width, 32)
        self.assertEqual(dut.max_burst_len, 16)

    def test_custom_params(self):
        dut = DMAReader(addr_width=64, data_width=64, max_burst_len=256)
        self.assertEqual(dut.addr_width, 64)
        self.assertEqual(dut.data_width, 64)
        self.assertEqual(dut.max_burst_len, 256)

    def test_invalid_addr_width(self):
        with self.assertRaises(TypeError):
            DMAReader(addr_width=0, data_width=32)

    def test_invalid_data_width(self):
        with self.assertRaises(ValueError):
            DMAReader(addr_width=32, data_width=7)

    def test_invalid_data_width_not_power_of_2(self):
        with self.assertRaises(ValueError):
            DMAReader(addr_width=32, data_width=48)

    def test_invalid_max_burst_len(self):
        with self.assertRaises(ValueError):
            DMAReader(addr_width=32, data_width=32, max_burst_len=0)
        with self.assertRaises(ValueError):
            DMAReader(addr_width=32, data_width=32, max_burst_len=257)


class TestDMAWriterCreate(unittest.TestCase):
    """Test DMAWriter construction."""

    def test_default_params(self):
        dut = DMAWriter(addr_width=32, data_width=32)
        self.assertEqual(dut.addr_width, 32)
        self.assertEqual(dut.data_width, 32)
        self.assertEqual(dut.max_burst_len, 16)

    def test_custom_params(self):
        dut = DMAWriter(addr_width=64, data_width=64, max_burst_len=128)
        self.assertEqual(dut.addr_width, 64)
        self.assertEqual(dut.data_width, 64)
        self.assertEqual(dut.max_burst_len, 128)

    def test_invalid_addr_width(self):
        with self.assertRaises(TypeError):
            DMAWriter(addr_width=-1, data_width=32)

    def test_invalid_data_width(self):
        with self.assertRaises(ValueError):
            DMAWriter(addr_width=32, data_width=3)

    def test_invalid_max_burst_len(self):
        with self.assertRaises(ValueError):
            DMAWriter(addr_width=32, data_width=32, max_burst_len=300)


class TestScatterGatherCreate(unittest.TestCase):
    """Test ScatterGatherDMA construction."""

    def test_default_params(self):
        dut = ScatterGatherDMA(addr_width=32, data_width=32)
        self.assertEqual(dut.addr_width, 32)
        self.assertEqual(dut.data_width, 32)
        self.assertEqual(dut.max_descriptors, 16)
        self.assertEqual(dut.max_burst_len, 16)

    def test_custom_params(self):
        dut = ScatterGatherDMA(addr_width=64, data_width=64,
                               max_descriptors=8, max_burst_len=32)
        self.assertEqual(dut.addr_width, 64)
        self.assertEqual(dut.data_width, 64)
        self.assertEqual(dut.max_descriptors, 8)
        self.assertEqual(dut.max_burst_len, 32)

    def test_invalid_max_descriptors(self):
        with self.assertRaises(ValueError):
            ScatterGatherDMA(addr_width=32, data_width=32, max_descriptors=0)

    def test_invalid_data_width(self):
        with self.assertRaises(ValueError):
            ScatterGatherDMA(addr_width=32, data_width=5)


class TestDMACommon(unittest.TestCase):
    """Test DMA common types."""

    def test_status_values(self):
        self.assertEqual(DMAStatus.IDLE, 0)
        self.assertEqual(DMAStatus.RUNNING, 1)
        self.assertEqual(DMAStatus.DONE, 2)
        self.assertEqual(DMAStatus.ERROR, 3)

    def test_descriptor_layout(self):
        layout = DMADescriptorLayout(addr_width=32)
        self.assertIn("src_addr", dict(layout))
        self.assertIn("dst_addr", dict(layout))
        self.assertIn("length", dict(layout))
        self.assertIn("control", dict(layout))

    def test_descriptor_layout_64(self):
        layout = DMADescriptorLayout(addr_width=64)
        self.assertIn("src_addr", dict(layout))


# ===========================================================================
# Simulation tests
# ===========================================================================

class TestDMAReaderSim(unittest.TestCase):
    """Simulation test for DMAReader."""

    def test_dma_reader_sim(self):
        """Read 4 beats from SRAM via DMAReader, verify output stream."""
        harness = DMAReaderTestHarness(addr_width=10, data_width=32,
                                       sram_size=1024, max_burst_len=16)

        async def testbench(ctx):
            sram_bus = harness.sram.bus
            reader = harness.reader

            # Pre-load SRAM with test data via direct AXI4 writes
            # (write channels are free since only read channels are wired to DMA)
            test_data = [0xAAAA0001, 0xBBBB0002, 0xCCCC0003, 0xDDDD0004]
            await axi4_write_burst_tb(ctx, sram_bus, 0x00, test_data)

            # Allow a few cycles for things to settle
            for _ in range(3):
                await ctx.tick()

            # Configure and start the DMA reader
            ctx.set(reader.src_addr, 0x00)
            ctx.set(reader.length, 4)
            ctx.set(reader.start, 1)
            await ctx.tick()
            ctx.set(reader.start, 0)

            # Collect output data (assert data_ready to accept)
            ctx.set(reader.data_ready, 1)
            collected = []
            for _ in range(200):
                await ctx.tick()
                if ctx.get(reader.data_valid):
                    collected.append(ctx.get(reader.data_out))
                if ctx.get(reader.done):
                    break

            assert len(collected) == 4, \
                f"Expected 4 beats, got {len(collected)}: {[hex(x) for x in collected]}"
            for i, (got, expected) in enumerate(zip(collected, test_data)):
                assert got == expected, \
                    f"Beat {i}: expected {expected:#010x}, got {got:#010x}"

        sim = Simulator(harness)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_dma_reader.vcd"):
            sim.run()


class TestDMAWriterSim(unittest.TestCase):
    """Simulation test for DMAWriter."""

    def test_dma_writer_sim(self):
        """Write 4 beats to SRAM via DMAWriter, verify SRAM contents."""
        harness = DMAWriterTestHarness(addr_width=10, data_width=32,
                                       sram_size=1024, max_burst_len=16)

        async def testbench(ctx):
            sram_bus = harness.sram.bus
            writer = harness.writer

            test_data = [0x11110001, 0x22220002, 0x33330003, 0x44440004]

            # Configure and start the DMA writer
            ctx.set(writer.dst_addr, 0x00)
            ctx.set(writer.length, 4)
            ctx.set(writer.start, 1)
            await ctx.tick()
            ctx.set(writer.start, 0)

            # Feed data into the writer's input stream
            data_idx = 0
            for _ in range(200):
                await ctx.tick()
                if data_idx < len(test_data):
                    ctx.set(writer.data_in, test_data[data_idx])
                    ctx.set(writer.data_valid, 1)
                    if ctx.get(writer.data_ready):
                        data_idx += 1
                else:
                    ctx.set(writer.data_valid, 0)
                if ctx.get(writer.done):
                    break

            assert data_idx == len(test_data), \
                f"Only {data_idx} of {len(test_data)} beats accepted"

            ctx.set(writer.data_valid, 0)

            # Allow a few cycles for write to complete
            for _ in range(5):
                await ctx.tick()

            # Verify SRAM contents by reading back via the free read channels
            read_data = await axi4_read_burst_tb(ctx, sram_bus, 0x00, 4)
            for i, (got, expected) in enumerate(zip(read_data, test_data)):
                assert got == expected, \
                    f"SRAM word {i}: expected {expected:#010x}, got {got:#010x}"

        sim = Simulator(harness)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_dma_writer.vcd"):
            sim.run()


class TestScatterGatherSim(unittest.TestCase):
    """Simulation test for ScatterGatherDMA."""

    def test_scatter_gather_sim(self):
        """Copy 4 words from source SRAM to destination SRAM via SG-DMA."""
        harness = ScatterGatherTestHarness(
            addr_width=10, data_width=32, sram_size=1024,
            max_descriptors=4, max_burst_len=16)

        async def testbench(ctx):
            sg = harness.sg
            src_bus = harness.src_sram.bus
            dst_bus = harness.dst_sram.bus

            # Pre-load source SRAM with test data (write channels are free)
            test_data = [0xDEAD0001, 0xBEEF0002, 0xCAFE0003, 0xBABE0004]
            await axi4_write_burst_tb(ctx, src_bus, 0x00, test_data)

            # Allow settle
            for _ in range(3):
                await ctx.tick()

            # Load descriptor 0: copy 4 words from src addr 0x00 to dst addr 0x00
            # control = 0x01 (last descriptor)
            ctx.set(sg.desc_index, 0)
            ctx.set(sg.desc_src_addr, 0x00)
            ctx.set(sg.desc_dst_addr, 0x00)
            ctx.set(sg.desc_length, 4)
            ctx.set(sg.desc_control, 0x01)  # last descriptor
            ctx.set(sg.desc_we, 1)
            await ctx.tick()
            ctx.set(sg.desc_we, 0)

            # Allow descriptor to be written
            await ctx.tick()

            # Start SG-DMA with 1 descriptor
            ctx.set(sg.num_descriptors, 1)
            ctx.set(sg.start, 1)
            await ctx.tick()
            ctx.set(sg.start, 0)

            # Wait for completion
            for _ in range(500):
                await ctx.tick()
                if ctx.get(sg.done):
                    break
            else:
                raise TimeoutError("SG-DMA did not complete within timeout")

            # Allow settle
            for _ in range(3):
                await ctx.tick()

            # Verify destination SRAM contents (read channels are free)
            read_data = await axi4_read_burst_tb(ctx, dst_bus, 0x00, 4)
            for i, (got, expected) in enumerate(zip(read_data, test_data)):
                assert got == expected, \
                    f"Dst SRAM word {i}: expected {expected:#010x}, got {got:#010x}"

        sim = Simulator(harness)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("tests/test_dma_scatter_gather.vcd"):
            sim.run()


if __name__ == "__main__":
    unittest.main()
