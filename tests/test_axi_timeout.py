"""Tests for AXI timeout watchdogs."""
import unittest
from amaranth import *
from amaranth.sim import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out, connect, flipped
from amaranth.back.rtlil import convert

from amaranth_soc.axi.timeout import AXI4LiteTimeout, AXI4Timeout
from amaranth_soc.axi.bus import AXI4Signature, AXI4LiteSignature, AXIResp, AXIBurst, AXISize
from amaranth_soc.axi.sram import AXI4SRAM


# =============================================================================
# AXI4-Lite Timeout Tests (existing, renamed from AXI4Timeout)
# =============================================================================

class TestAXI4LiteTimeoutConstruction(unittest.TestCase):
    """Test AXI4LiteTimeout construction and parameter validation."""

    def test_create_basic(self):
        """Construct with basic valid parameters."""
        to = AXI4LiteTimeout(addr_width=32, data_width=32)
        self.assertEqual(to.addr_width, 32)
        self.assertEqual(to.data_width, 32)
        self.assertEqual(to.timeout, 1024)  # default

    def test_create_custom_timeout(self):
        """Construct with custom timeout value."""
        to = AXI4LiteTimeout(addr_width=32, data_width=32, timeout=256)
        self.assertEqual(to.timeout, 256)

    def test_create_64bit(self):
        """Construct with 64-bit data width."""
        to = AXI4LiteTimeout(addr_width=32, data_width=64)
        self.assertEqual(to.data_width, 64)

    def test_create_small_timeout(self):
        """Construct with minimum timeout (1)."""
        to = AXI4LiteTimeout(addr_width=32, data_width=32, timeout=1)
        self.assertEqual(to.timeout, 1)

    def test_create_large_timeout(self):
        """Construct with large timeout value."""
        to = AXI4LiteTimeout(addr_width=32, data_width=32, timeout=65536)
        self.assertEqual(to.timeout, 65536)

    def test_create_zero_addr_width(self):
        """Construct with addr_width=0 (edge case)."""
        to = AXI4LiteTimeout(addr_width=0, data_width=32)
        self.assertEqual(to.addr_width, 0)

    def test_invalid_addr_width_negative(self):
        """Negative address width should raise TypeError."""
        with self.assertRaises(TypeError):
            AXI4LiteTimeout(addr_width=-1, data_width=32)

    def test_invalid_addr_width_string(self):
        """String address width should raise TypeError."""
        with self.assertRaises(TypeError):
            AXI4LiteTimeout(addr_width="32", data_width=32)

    def test_invalid_data_width_16(self):
        """Data width 16 should raise ValueError."""
        with self.assertRaises(ValueError):
            AXI4LiteTimeout(addr_width=32, data_width=16)

    def test_valid_data_width_128(self):
        """Data width 128 should now be accepted (power of 2 >= 32)."""
        to = AXI4LiteTimeout(addr_width=32, data_width=128)
        self.assertEqual(to.data_width, 128)

    def test_invalid_data_width_not_power_of_2(self):
        """Data width 48 (not power of 2) should raise ValueError."""
        with self.assertRaises(ValueError):
            AXI4LiteTimeout(addr_width=32, data_width=48)

    def test_invalid_timeout_zero(self):
        """Timeout of 0 should raise ValueError."""
        with self.assertRaises(ValueError):
            AXI4LiteTimeout(addr_width=32, data_width=32, timeout=0)

    def test_invalid_timeout_negative(self):
        """Negative timeout should raise ValueError."""
        with self.assertRaises(ValueError):
            AXI4LiteTimeout(addr_width=32, data_width=32, timeout=-1)

    def test_invalid_timeout_string(self):
        """String timeout should raise ValueError."""
        with self.assertRaises((TypeError, ValueError)):
            AXI4LiteTimeout(addr_width=32, data_width=32, timeout="1024")


class TestAXI4LiteTimeoutProperties(unittest.TestCase):
    """Test AXI4LiteTimeout property access."""

    def test_addr_width_property(self):
        to = AXI4LiteTimeout(addr_width=24, data_width=32)
        self.assertEqual(to.addr_width, 24)

    def test_data_width_property(self):
        to = AXI4LiteTimeout(addr_width=32, data_width=64)
        self.assertEqual(to.data_width, 64)

    def test_timeout_property(self):
        to = AXI4LiteTimeout(addr_width=32, data_width=32, timeout=512)
        self.assertEqual(to.timeout, 512)

    def test_timeout_default_property(self):
        to = AXI4LiteTimeout(addr_width=32, data_width=32)
        self.assertEqual(to.timeout, 1024)


class TestAXI4LiteTimeoutElaboration(unittest.TestCase):
    """Test AXI4LiteTimeout RTLIL elaboration."""

    def test_elaborate_32bit(self):
        """Elaborate with 32-bit data width."""
        to = AXI4LiteTimeout(addr_width=32, data_width=32)
        rtlil = convert(to)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_64bit(self):
        """Elaborate with 64-bit data width."""
        to = AXI4LiteTimeout(addr_width=32, data_width=64)
        rtlil = convert(to)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_custom_timeout(self):
        """Elaborate with custom timeout."""
        to = AXI4LiteTimeout(addr_width=32, data_width=32, timeout=256)
        rtlil = convert(to)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_small_timeout(self):
        """Elaborate with minimum timeout."""
        to = AXI4LiteTimeout(addr_width=32, data_width=32, timeout=1)
        rtlil = convert(to)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_narrow_addr(self):
        """Elaborate with narrow address width."""
        to = AXI4LiteTimeout(addr_width=12, data_width=32)
        rtlil = convert(to)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_various_timeouts(self):
        """Elaborate with various timeout values."""
        for timeout in [1, 16, 256, 1024, 4096]:
            with self.subTest(timeout=timeout):
                to = AXI4LiteTimeout(addr_width=32, data_width=32, timeout=timeout)
                rtlil = convert(to)
                self.assertGreater(len(rtlil), 0)


# =============================================================================
# AXI4 Full Timeout Tests
# =============================================================================

class TestAXI4TimeoutCreate(unittest.TestCase):
    """Test AXI4Timeout construction and parameter validation."""

    def test_create_basic(self):
        """Construct with basic valid parameters."""
        to = AXI4Timeout(addr_width=32, data_width=32)
        self.assertEqual(to.addr_width, 32)
        self.assertEqual(to.data_width, 32)
        self.assertEqual(to.id_width, 0)
        self.assertEqual(to.timeout, 1024)

    def test_create_custom_timeout(self):
        """Construct with custom timeout value."""
        to = AXI4Timeout(addr_width=32, data_width=32, timeout=256)
        self.assertEqual(to.timeout, 256)

    def test_create_8bit_data(self):
        """Construct with 8-bit data width (AXI4 minimum)."""
        to = AXI4Timeout(addr_width=16, data_width=8)
        self.assertEqual(to.data_width, 8)

    def test_create_64bit_data(self):
        """Construct with 64-bit data width."""
        to = AXI4Timeout(addr_width=32, data_width=64)
        self.assertEqual(to.data_width, 64)

    def test_invalid_addr_width_negative(self):
        """Negative address width should raise TypeError."""
        with self.assertRaises(TypeError):
            AXI4Timeout(addr_width=-1, data_width=32)

    def test_invalid_data_width_too_small(self):
        """Data width < 8 should raise ValueError."""
        with self.assertRaises(ValueError):
            AXI4Timeout(addr_width=32, data_width=4)

    def test_invalid_data_width_not_power_of_2(self):
        """Data width not power of 2 should raise ValueError."""
        with self.assertRaises(ValueError):
            AXI4Timeout(addr_width=32, data_width=48)

    def test_invalid_id_width_negative(self):
        """Negative ID width should raise TypeError."""
        with self.assertRaises(TypeError):
            AXI4Timeout(addr_width=32, data_width=32, id_width=-1)

    def test_invalid_timeout_zero(self):
        """Timeout of 0 should raise ValueError."""
        with self.assertRaises(ValueError):
            AXI4Timeout(addr_width=32, data_width=32, timeout=0)

    def test_invalid_timeout_string(self):
        """String timeout should raise ValueError."""
        with self.assertRaises((TypeError, ValueError)):
            AXI4Timeout(addr_width=32, data_width=32, timeout="1024")


class TestAXI4TimeoutCreateWithId(unittest.TestCase):
    """Test AXI4Timeout construction with id_width."""

    def test_create_with_id_width_4(self):
        """Construct with id_width=4."""
        to = AXI4Timeout(addr_width=32, data_width=32, id_width=4)
        self.assertEqual(to.id_width, 4)

    def test_create_with_id_width_8(self):
        """Construct with id_width=8."""
        to = AXI4Timeout(addr_width=32, data_width=32, id_width=8)
        self.assertEqual(to.id_width, 8)

    def test_create_with_id_width_0(self):
        """Construct with id_width=0 (default)."""
        to = AXI4Timeout(addr_width=32, data_width=32, id_width=0)
        self.assertEqual(to.id_width, 0)

    def test_create_with_id_and_timeout(self):
        """Construct with both id_width and custom timeout."""
        to = AXI4Timeout(addr_width=32, data_width=32, id_width=4, timeout=512)
        self.assertEqual(to.id_width, 4)
        self.assertEqual(to.timeout, 512)


class TestAXI4TimeoutElaborate(unittest.TestCase):
    """Test AXI4Timeout RTLIL elaboration."""

    def test_elaborate_basic(self):
        """Elaborate with basic parameters."""
        to = AXI4Timeout(addr_width=32, data_width=32)
        rtlil = convert(to)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_with_id(self):
        """Elaborate with id_width."""
        to = AXI4Timeout(addr_width=32, data_width=32, id_width=4)
        rtlil = convert(to)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_64bit(self):
        """Elaborate with 64-bit data width."""
        to = AXI4Timeout(addr_width=32, data_width=64, id_width=4)
        rtlil = convert(to)
        self.assertGreater(len(rtlil), 0)

    def test_elaborate_various_timeouts(self):
        """Elaborate with various timeout values."""
        for timeout in [1, 16, 256, 1024]:
            with self.subTest(timeout=timeout):
                to = AXI4Timeout(addr_width=32, data_width=32, timeout=timeout)
                rtlil = convert(to)
                self.assertGreater(len(rtlil), 0)


# =============================================================================
# AXI4 Full Timeout Simulation Helpers
# =============================================================================

def _wire_axi4_sub_to_sram(m, sub, sram_bus, id_width):
    """Manually wire timeout.sub port signals to SRAM bus signals.

    Cannot use connect() because the timeout wrapper's elaborate() already
    drives the sub port signals. Manual wiring avoids driver conflicts.
    """
    # AW channel: sub drives → sram reads
    m.d.comb += [
        sram_bus.awaddr.eq(sub.awaddr),
        sram_bus.awprot.eq(sub.awprot),
        sram_bus.awvalid.eq(sub.awvalid),
        sram_bus.awlen.eq(sub.awlen),
        sram_bus.awsize.eq(sub.awsize),
        sram_bus.awburst.eq(sub.awburst),
        sram_bus.awlock.eq(sub.awlock),
        sram_bus.awcache.eq(sub.awcache),
        sram_bus.awqos.eq(sub.awqos),
        sram_bus.awregion.eq(sub.awregion),
        sub.awready.eq(sram_bus.awready),
    ]
    if id_width > 0:
        m.d.comb += sram_bus.awid.eq(sub.awid)

    # W channel
    m.d.comb += [
        sram_bus.wdata.eq(sub.wdata),
        sram_bus.wstrb.eq(sub.wstrb),
        sram_bus.wvalid.eq(sub.wvalid),
        sram_bus.wlast.eq(sub.wlast),
        sub.wready.eq(sram_bus.wready),
    ]

    # B channel: sram drives → sub reads
    m.d.comb += [
        sub.bresp.eq(sram_bus.bresp),
        sub.bvalid.eq(sram_bus.bvalid),
        sram_bus.bready.eq(sub.bready),
    ]
    if id_width > 0:
        m.d.comb += sub.bid.eq(sram_bus.bid)

    # AR channel
    m.d.comb += [
        sram_bus.araddr.eq(sub.araddr),
        sram_bus.arprot.eq(sub.arprot),
        sram_bus.arvalid.eq(sub.arvalid),
        sram_bus.arlen.eq(sub.arlen),
        sram_bus.arsize.eq(sub.arsize),
        sram_bus.arburst.eq(sub.arburst),
        sram_bus.arlock.eq(sub.arlock),
        sram_bus.arcache.eq(sub.arcache),
        sram_bus.arqos.eq(sub.arqos),
        sram_bus.arregion.eq(sub.arregion),
        sub.arready.eq(sram_bus.arready),
    ]
    if id_width > 0:
        m.d.comb += sram_bus.arid.eq(sub.arid)

    # R channel
    m.d.comb += [
        sub.rdata.eq(sram_bus.rdata),
        sub.rresp.eq(sram_bus.rresp),
        sub.rvalid.eq(sram_bus.rvalid),
        sub.rlast.eq(sram_bus.rlast),
        sram_bus.rready.eq(sub.rready),
    ]
    if id_width > 0:
        m.d.comb += sub.rid.eq(sram_bus.rid)


def _wire_axi4(m, master, slave, id_width):
    """Manually wire AXI4 master port signals to slave port signals.

    This avoids using connect() which can conflict with components that
    drive their own port signals in elaborate().
    """
    # AW channel: master drives → slave reads
    m.d.comb += [
        slave.awaddr.eq(master.awaddr),
        slave.awprot.eq(master.awprot),
        slave.awvalid.eq(master.awvalid),
        slave.awlen.eq(master.awlen),
        slave.awsize.eq(master.awsize),
        slave.awburst.eq(master.awburst),
        slave.awlock.eq(master.awlock),
        slave.awcache.eq(master.awcache),
        slave.awqos.eq(master.awqos),
        slave.awregion.eq(master.awregion),
        master.awready.eq(slave.awready),
    ]
    if id_width > 0:
        m.d.comb += slave.awid.eq(master.awid)

    # W channel
    m.d.comb += [
        slave.wdata.eq(master.wdata),
        slave.wstrb.eq(master.wstrb),
        slave.wvalid.eq(master.wvalid),
        slave.wlast.eq(master.wlast),
        master.wready.eq(slave.wready),
    ]

    # B channel: slave drives → master reads
    m.d.comb += [
        master.bresp.eq(slave.bresp),
        master.bvalid.eq(slave.bvalid),
        slave.bready.eq(master.bready),
    ]
    if id_width > 0:
        m.d.comb += master.bid.eq(slave.bid)

    # AR channel
    m.d.comb += [
        slave.araddr.eq(master.araddr),
        slave.arprot.eq(master.arprot),
        slave.arvalid.eq(master.arvalid),
        slave.arlen.eq(master.arlen),
        slave.arsize.eq(master.arsize),
        slave.arburst.eq(master.arburst),
        slave.arlock.eq(master.arlock),
        slave.arcache.eq(master.arcache),
        slave.arqos.eq(master.arqos),
        slave.arregion.eq(master.arregion),
        master.arready.eq(slave.arready),
    ]
    if id_width > 0:
        m.d.comb += slave.arid.eq(master.arid)

    # R channel
    m.d.comb += [
        master.rdata.eq(slave.rdata),
        master.rresp.eq(slave.rresp),
        master.rvalid.eq(slave.rvalid),
        master.rlast.eq(slave.rlast),
        slave.rready.eq(master.rready),
    ]
    if id_width > 0:
        m.d.comb += master.rid.eq(slave.rid)


class _TimeoutSRAMTestHarness(wiring.Component):
    """Test harness connecting AXI4Timeout to AXI4SRAM."""
    def __init__(self, *, size=256, data_width=32, id_width=0, timeout=64):
        self._size = size
        self._data_width = data_width
        self._id_width = id_width
        self._timeout_val = timeout

        addr_width = (size - 1).bit_length()
        self._addr_width = addr_width

        super().__init__({
            "bus": In(AXI4Signature(addr_width=addr_width, data_width=data_width,
                                    id_width=id_width)),
        })

    def elaborate(self, platform):
        m = Module()

        timeout = AXI4Timeout(
            addr_width=self._addr_width,
            data_width=self._data_width,
            id_width=self._id_width,
            timeout=self._timeout_val,
        )
        sram = AXI4SRAM(
            size=self._size,
            data_width=self._data_width,
            id_width=self._id_width,
        )
        m.submodules.timeout = timeout
        m.submodules.sram = sram

        # Wire harness bus → timeout bus (manual, no connect())
        _wire_axi4(m, flipped(self).bus, timeout.bus, self._id_width)
        # Wire timeout sub → sram bus (manual, no connect())
        _wire_axi4(m, timeout.sub, sram.bus, self._id_width)

        return m


class _TimeoutDeadTestHarness(wiring.Component):
    """Test harness connecting AXI4Timeout to a dead subordinate that never responds."""
    def __init__(self, *, addr_width=8, data_width=32, id_width=0, timeout=16):
        self._addr_width = addr_width
        self._data_width = data_width
        self._id_width = id_width
        self._timeout_val = timeout

        super().__init__({
            "bus": In(AXI4Signature(addr_width=addr_width, data_width=data_width,
                                    id_width=id_width)),
        })

    def elaborate(self, platform):
        m = Module()

        timeout = AXI4Timeout(
            addr_width=self._addr_width,
            data_width=self._data_width,
            id_width=self._id_width,
            timeout=self._timeout_val,
        )
        m.submodules.timeout = timeout

        # Wire harness bus → timeout bus (manual, no connect())
        _wire_axi4(m, flipped(self).bus, timeout.bus, self._id_width)

        # Dead subordinate: accept all handshakes, never respond
        sub = timeout.sub
        m.d.comb += [
            sub.awready.eq(1),
            sub.wready.eq(1),
            sub.arready.eq(1),
            sub.bvalid.eq(0),
            sub.bresp.eq(0),
            sub.rvalid.eq(0),
            sub.rdata.eq(0),
            sub.rresp.eq(0),
            sub.rlast.eq(0),
        ]
        if self._id_width > 0:
            m.d.comb += [
                sub.bid.eq(0),
                sub.rid.eq(0),
            ]

        return m


# =============================================================================
# AXI4 protocol helpers for simulation
# =============================================================================

async def _axi4_write_single(ctx, bus, addr, data, strb=None, awid=0):
    """Perform a single-beat AXI4 write.

    Drives AW for one tick (the SRAM accepts it combinationally in WR_IDLE),
    then drives W for one tick (accepted in WR_DATA), then waits for B.
    """
    has_id = bus.signature.id_width > 0
    bytes_per_word = bus.signature.data_width // 8
    if strb is None:
        strb = (1 << bytes_per_word) - 1

    # Assert bready early
    ctx.set(bus.bready, 1)

    # Drive AW channel
    ctx.set(bus.awaddr, addr)
    ctx.set(bus.awlen, 0)
    ctx.set(bus.awsize, AXISize.B4)
    ctx.set(bus.awburst, AXIBurst.INCR)
    ctx.set(bus.awvalid, 1)
    if has_id:
        ctx.set(bus.awid, awid)

    # Tick — AW handshake happens (SRAM accepts combinationally in WR_IDLE)
    await ctx.tick()
    ctx.set(bus.awvalid, 0)

    # Drive W channel
    ctx.set(bus.wdata, data)
    ctx.set(bus.wstrb, strb)
    ctx.set(bus.wlast, 1)
    ctx.set(bus.wvalid, 1)

    # Wait for W handshake and then B response
    for _ in range(100):
        await ctx.tick()
        if ctx.get(bus.bvalid):
            bresp = ctx.get(bus.bresp)
            bid = ctx.get(bus.bid) if has_id else 0
            ctx.set(bus.wvalid, 0)
            ctx.set(bus.wlast, 0)
            await ctx.tick()
            ctx.set(bus.bready, 0)
            await ctx.tick()
            return bresp, bid
        if ctx.get(bus.wready):
            ctx.set(bus.wvalid, 0)
            ctx.set(bus.wlast, 0)

    raise TimeoutError("No B response received")


async def _axi4_read_single(ctx, bus, addr, arid=0):
    """Perform a single-beat AXI4 read.

    Drives AR for one tick (accepted combinationally), then waits for R.
    """
    has_id = bus.signature.id_width > 0

    # Drive AR channel
    ctx.set(bus.araddr, addr)
    ctx.set(bus.arlen, 0)
    ctx.set(bus.arsize, AXISize.B4)
    ctx.set(bus.arburst, AXIBurst.INCR)
    ctx.set(bus.arvalid, 1)
    ctx.set(bus.rready, 1)
    if has_id:
        ctx.set(bus.arid, arid)

    # Tick — AR handshake happens (accepted combinationally)
    await ctx.tick()
    ctx.set(bus.arvalid, 0)

    # Wait for R response
    for _ in range(100):
        await ctx.tick()
        if ctx.get(bus.rvalid):
            rdata = ctx.get(bus.rdata)
            rresp = ctx.get(bus.rresp)
            rlast = ctx.get(bus.rlast)
            rid = ctx.get(bus.rid) if has_id else 0
            await ctx.tick()
            ctx.set(bus.rready, 0)
            await ctx.tick()
            return rdata, rresp, rlast, rid

    raise TimeoutError("No R response received")


# =============================================================================
# AXI4 Full Timeout Simulation Tests
# =============================================================================

class TestAXI4TimeoutSimNoTimeout(unittest.TestCase):
    """Simulation: normal operation through timeout wrapper to SRAM."""

    def test_axi4_timeout_sim_no_timeout(self):
        """Write and read through timeout wrapper — data passes correctly."""
        dut = _TimeoutSRAMTestHarness(size=256, data_width=32, id_width=4, timeout=64)

        async def testbench(ctx):
            bus = dut.bus

            # Write 0xDEADBEEF to address 0x10
            bresp, bid = await _axi4_write_single(ctx, bus, 0x10, 0xDEADBEEF, awid=0x5)
            self.assertEqual(bresp, AXIResp.OKAY)
            self.assertEqual(bid, 0x5)

            # Read back from address 0x10
            rdata, rresp, rlast, rid = await _axi4_read_single(ctx, bus, 0x10, arid=0xA)
            self.assertEqual(rdata, 0xDEADBEEF)
            self.assertEqual(rresp, AXIResp.OKAY)
            self.assertEqual(rlast, 1)
            self.assertEqual(rid, 0xA)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("test_axi4_timeout_no_timeout.vcd"):
            sim.run()


class TestAXI4TimeoutSimReadTimeout(unittest.TestCase):
    """Simulation: read timeout generates DECERR with rlast=1."""

    def test_axi4_timeout_sim_read_timeout(self):
        """Connect to dead subordinate, verify DECERR on read timeout."""
        timeout_cycles = 16
        dut = _TimeoutDeadTestHarness(
            addr_width=8, data_width=32, id_width=4, timeout=timeout_cycles
        )

        async def testbench(ctx):
            bus = dut.bus

            # Issue a read to the dead subordinate
            ctx.set(bus.araddr, 0x00)
            ctx.set(bus.arlen, 0)
            ctx.set(bus.arsize, AXISize.B4)
            ctx.set(bus.arburst, AXIBurst.INCR)
            ctx.set(bus.arvalid, 1)
            ctx.set(bus.arid, 0x7)

            # Wait for AR handshake
            for _ in range(10):
                await ctx.tick()
                if ctx.get(bus.arready):
                    break
            ctx.set(bus.arvalid, 0)

            # Wait for timeout DECERR response
            ctx.set(bus.rready, 1)
            for cycle in range(timeout_cycles + 30):
                await ctx.tick()
                if ctx.get(bus.rvalid):
                    rresp = ctx.get(bus.rresp)
                    rlast = ctx.get(bus.rlast)
                    rid = ctx.get(bus.rid)
                    self.assertEqual(rresp, AXIResp.DECERR,
                                     f"Expected DECERR, got {rresp}")
                    self.assertEqual(rlast, 1,
                                     "Expected rlast=1 on timeout response")
                    self.assertEqual(rid, 0x7,
                                     f"Expected RID=0x7, got {rid}")
                    break
            else:
                self.fail(f"No DECERR response within {timeout_cycles + 30} cycles")

            ctx.set(bus.rready, 0)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with sim.write_vcd("test_axi4_timeout_read_timeout.vcd"):
            sim.run()


if __name__ == "__main__":
    unittest.main()
