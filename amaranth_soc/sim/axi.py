"""AXI4-Lite simulation helpers for async testbenches."""

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
