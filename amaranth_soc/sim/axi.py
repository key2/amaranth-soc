"""AXI4-Lite and AXI4 Full simulation helpers for async testbenches."""

from amaranth.utils import exact_log2

from amaranth_soc.axi.bus import AXIResp


async def axi_lite_write(ctx, bus, addr, data, strb=None, expected_resp=AXIResp.OKAY):
    """Perform an AXI4-Lite write transaction.

    Drives AW+W channels simultaneously, waits for B response.

    Parameters
    ----------
    ctx : SimulatorContext
        The simulator context from an async testbench.
    bus : AXI4LiteInterface
        The AXI4-Lite bus interface to drive.
    addr : int
        Write address.
    data : int
        Write data.
    strb : int or None
        Write strobe. If None, all bytes enabled (all 1s).
    expected_resp : AXIResp
        Expected response code (asserted).

    Returns
    -------
    AXIResp
        The actual response code.
    """
    if strb is None:
        strb = (1 << (len(bus.wstrb))) - 1  # All bytes enabled

    # Drive AW channel
    ctx.set(bus.awaddr, addr)
    ctx.set(bus.awvalid, 1)
    ctx.set(bus.awprot, 0)

    # Drive W channel simultaneously
    ctx.set(bus.wdata, data)
    ctx.set(bus.wstrb, strb)
    ctx.set(bus.wvalid, 1)

    # Ready to accept response
    ctx.set(bus.bready, 1)

    # Wait until we see bvalid (the write response).
    # Keep all signals asserted until we see the response.
    for _ in range(100):  # Safety limit
        await ctx.tick()
        if ctx.get(bus.bvalid):
            resp = ctx.get(bus.bresp)
            # The B handshake (bvalid & bready) is now visible to the slave.
            # On the NEXT tick, the slave will see bready=1 and transition.
            # We need to tick once more with bready=1 to complete the handshake,
            # then deassert.
            ctx.set(bus.awvalid, 0)
            ctx.set(bus.wvalid, 0)
            # Keep bready=1 for this tick so the slave sees the handshake
            await ctx.tick()
            # Now deassert bready
            ctx.set(bus.bready, 0)
            await ctx.tick()
            assert resp == expected_resp, f"Expected {expected_resp}, got {AXIResp(resp)}"
            return AXIResp(resp)

    raise TimeoutError("AXI4-Lite write: timed out waiting for response")


async def axi_lite_read(ctx, bus, addr, expected_resp=AXIResp.OKAY):
    """Perform an AXI4-Lite read transaction.

    Drives AR channel, waits for R response.

    Parameters
    ----------
    ctx : SimulatorContext
        The simulator context from an async testbench.
    bus : AXI4LiteInterface
        The AXI4-Lite bus interface to drive.
    addr : int
        Read address.
    expected_resp : AXIResp
        Expected response code (asserted).

    Returns
    -------
    tuple of (int, AXIResp)
        The read data and response code.
    """
    # Drive AR channel
    ctx.set(bus.araddr, addr)
    ctx.set(bus.arvalid, 1)
    ctx.set(bus.arprot, 0)

    # Ready to accept response
    ctx.set(bus.rready, 1)

    # Wait for read response. Keep arvalid asserted until we see rvalid.
    for _ in range(100):  # Safety limit
        await ctx.tick()
        if ctx.get(bus.rvalid):
            data = ctx.get(bus.rdata)
            resp = ctx.get(bus.rresp)
            # Deassert arvalid (may already be accepted)
            ctx.set(bus.arvalid, 0)
            # Keep rready=1 for this tick so the slave sees the handshake
            await ctx.tick()
            # Now deassert rready
            ctx.set(bus.rready, 0)
            await ctx.tick()
            assert resp == expected_resp, f"Expected {expected_resp}, got {AXIResp(resp)}"
            return data, AXIResp(resp)

    raise TimeoutError("AXI4-Lite read: timed out waiting for response")


# ---------------------------------------------------------------------------
# AXI4 Full simulation helpers
# ---------------------------------------------------------------------------

def _auto_size(bus):
    """Calculate AXI size encoding from bus data_width.

    Returns the ``axsize`` value corresponding to the number of bytes per beat,
    e.g. 32-bit data → 4 bytes → size=2.
    """
    return exact_log2(bus.data_width // 8)


def _has_id(bus):
    """Return True if the bus signature includes ID signals."""
    return "awid" in dict(bus.signature.members)


async def axi4_write_burst(ctx, bus, addr, data_list, *, id=0, burst_type=0b01,
                            size=None):
    """Perform an AXI4 burst write transaction in simulation.

    Drives the AW channel for one clock cycle (the subordinate is expected to
    accept it combinationally or within a few cycles), then sends W beats one
    per cycle, and finally waits for the B response.

    Parameters
    ----------
    ctx : SimulatorContext
        The simulation context.
    bus : AXI4Interface
        The AXI4 bus interface (manager side).
    addr : int
        Start address.
    data_list : list of int
        Data values to write (one per beat).
    id : int
        Transaction ID (default 0).
    burst_type : int
        Burst type: 0b00=FIXED, 0b01=INCR, 0b10=WRAP (default INCR).
    size : int or None
        Beat size encoding. If None, auto-calculated from data_width.

    Returns
    -------
    int
        Write response (bresp value).
    """
    if size is None:
        size = _auto_size(bus)

    awlen = len(data_list) - 1
    bytes_per_word = bus.data_width // 8
    strb_all = (1 << bytes_per_word) - 1
    has_id = _has_id(bus)

    # Assert bready early so we capture the B response as soon as it appears
    ctx.set(bus.bready, 1)

    # --- AW channel ---
    # Drive AW signals and tick once. For subordinates that assert awready
    # combinationally (like AXI4SRAM), the handshake completes on this tick.
    ctx.set(bus.awaddr, addr)
    ctx.set(bus.awlen, awlen)
    ctx.set(bus.awsize, size)
    ctx.set(bus.awburst, burst_type)
    ctx.set(bus.awvalid, 1)
    if has_id:
        ctx.set(bus.awid, id)

    await ctx.tick()
    ctx.set(bus.awvalid, 0)

    # --- W channel: send data beats ---
    for i, data in enumerate(data_list):
        ctx.set(bus.wdata, data)
        ctx.set(bus.wstrb, strb_all)
        ctx.set(bus.wvalid, 1)
        ctx.set(bus.wlast, 1 if i == awlen else 0)

        await ctx.tick()

        # Check if B response appeared (for single-beat or last beat)
        if ctx.get(bus.bvalid):
            bresp = ctx.get(bus.bresp)
            ctx.set(bus.wvalid, 0)
            ctx.set(bus.wlast, 0)
            # Keep bready=1 for one more tick so the subordinate sees the handshake
            await ctx.tick()
            ctx.set(bus.bready, 0)
            await ctx.tick()
            return bresp

    ctx.set(bus.wvalid, 0)
    ctx.set(bus.wlast, 0)

    # --- B channel: wait for write response if not already received ---
    for _ in range(100):
        await ctx.tick()
        if ctx.get(bus.bvalid):
            bresp = ctx.get(bus.bresp)
            # Keep bready=1 for one more tick so the subordinate sees the handshake
            await ctx.tick()
            ctx.set(bus.bready, 0)
            await ctx.tick()
            return bresp

    raise TimeoutError("AXI4 write: timed out waiting for bvalid")


async def axi4_read_burst(ctx, bus, addr, length, *, id=0, burst_type=0b01,
                           size=None):
    """Perform an AXI4 burst read transaction in simulation.

    Parameters
    ----------
    ctx : SimulatorContext
        The simulation context.
    bus : AXI4Interface
        The AXI4 bus interface (manager side).
    addr : int
        Start address.
    length : int
        Number of beats to read.
    id : int
        Transaction ID (default 0).
    burst_type : int
        Burst type (default INCR).
    size : int or None
        Beat size encoding. If None, auto-calculated from data_width.

    Returns
    -------
    tuple of (list of int, int)
        (data_list, rresp) — list of read data values and response code.
    """
    if size is None:
        size = _auto_size(bus)

    arlen = length - 1
    has_id = _has_id(bus)

    # --- AR channel ---
    # Drive AR signals and tick once. For subordinates that assert arready
    # combinationally (like AXI4SRAM), the handshake completes on this tick.
    ctx.set(bus.araddr, addr)
    ctx.set(bus.arlen, arlen)
    ctx.set(bus.arsize, size)
    ctx.set(bus.arburst, burst_type)
    ctx.set(bus.arvalid, 1)
    if has_id:
        ctx.set(bus.arid, id)

    await ctx.tick()
    ctx.set(bus.arvalid, 0)

    # --- R channel: collect read beats ---
    data_list = []
    rresp = 0
    ctx.set(bus.rready, 1)

    for beat in range(length):
        for _ in range(100):
            await ctx.tick()
            if ctx.get(bus.rvalid):
                data_list.append(ctx.get(bus.rdata))
                rresp = ctx.get(bus.rresp)
                break
        else:
            raise TimeoutError(
                f"AXI4 read: timed out waiting for rvalid on beat {beat}")

    # Keep rready=1 for one more tick so the subordinate sees the handshake
    await ctx.tick()
    ctx.set(bus.rready, 0)
    await ctx.tick()

    return data_list, rresp


async def axi4_write_single(ctx, bus, addr, data, *, id=0):
    """Perform a single-beat AXI4 write (convenience wrapper).

    Parameters
    ----------
    ctx : SimulatorContext
        The simulation context.
    bus : AXI4Interface
        The AXI4 bus interface (manager side).
    addr : int
        Write address.
    data : int
        Data value to write.
    id : int
        Transaction ID (default 0).

    Returns
    -------
    int
        Write response (bresp value).
    """
    return await axi4_write_burst(ctx, bus, addr, [data], id=id)


async def axi4_read_single(ctx, bus, addr, *, id=0):
    """Perform a single-beat AXI4 read (convenience wrapper).

    Parameters
    ----------
    ctx : SimulatorContext
        The simulation context.
    bus : AXI4Interface
        The AXI4 bus interface (manager side).
    addr : int
        Read address.
    id : int
        Transaction ID (default 0).

    Returns
    -------
    tuple of (int, int)
        (data, rresp) — read data value and response code.
    """
    data_list, rresp = await axi4_read_burst(ctx, bus, addr, 1, id=id)
    return data_list[0], rresp
