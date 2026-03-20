"""Wishbone B4 simulation helpers for async testbenches."""

__all__ = ["wb_write", "wb_read", "wb_write_pipelined", "wb_read_pipelined"]


async def wb_write(ctx, bus, addr, data, sel=None, expected_ack=True):
    """Perform a classic Wishbone write transaction.

    Drives CYC, STB, WE, ADR, DAT_W, SEL and waits for ACK (or ERR/RTY).

    Parameters
    ----------
    ctx : SimulatorContext
        The simulator context from an async testbench.
    bus : wishbone.Interface
        The Wishbone bus interface to drive.
    addr : int
        Write address.
    data : int
        Write data.
    sel : int or None
        Byte select. If None, all granules enabled (all 1s).
    expected_ack : bool
        If True, assert that the response is ``"ack"``.

    Returns
    -------
    str
        The response type: ``"ack"``, ``"err"``, or ``"rty"``.
    """
    if sel is None:
        sel = (1 << len(bus.sel)) - 1

    # Drive bus signals
    ctx.set(bus.cyc, 1)
    ctx.set(bus.stb, 1)
    ctx.set(bus.we, 1)
    ctx.set(bus.adr, addr)
    ctx.set(bus.dat_w, data)
    ctx.set(bus.sel, sel)

    # Wait for response
    for _ in range(100):  # Safety limit
        await ctx.tick()
        if ctx.get(bus.ack):
            response = "ack"
        elif hasattr(bus, "err") and ctx.get(bus.err):
            response = "err"
        elif hasattr(bus, "rty") and ctx.get(bus.rty):
            response = "rty"
        else:
            continue

        # Got a response — deassert bus signals
        ctx.set(bus.cyc, 0)
        ctx.set(bus.stb, 0)
        ctx.set(bus.we, 0)
        await ctx.tick()

        if expected_ack:
            assert response == "ack", f"Expected 'ack', got '{response}'"
        return response

    raise TimeoutError("Wishbone write: timed out waiting for response")


async def wb_read(ctx, bus, addr, sel=None, expected_ack=True):
    """Perform a classic Wishbone read transaction.

    Drives CYC, STB, ADR, SEL (with WE=0) and waits for ACK (or ERR/RTY).

    Parameters
    ----------
    ctx : SimulatorContext
        The simulator context from an async testbench.
    bus : wishbone.Interface
        The Wishbone bus interface to drive.
    addr : int
        Read address.
    sel : int or None
        Byte select. If None, all granules enabled (all 1s).
    expected_ack : bool
        If True, assert that the response is ``"ack"``.

    Returns
    -------
    tuple of (int, str)
        The read data and response type (``"ack"``, ``"err"``, or ``"rty"``).
    """
    if sel is None:
        sel = (1 << len(bus.sel)) - 1

    # Drive bus signals
    ctx.set(bus.cyc, 1)
    ctx.set(bus.stb, 1)
    ctx.set(bus.we, 0)
    ctx.set(bus.adr, addr)
    ctx.set(bus.sel, sel)

    # Wait for response
    for _ in range(100):  # Safety limit
        await ctx.tick()
        if ctx.get(bus.ack):
            response = "ack"
        elif hasattr(bus, "err") and ctx.get(bus.err):
            response = "err"
        elif hasattr(bus, "rty") and ctx.get(bus.rty):
            response = "rty"
        else:
            continue

        # Capture read data
        data = ctx.get(bus.dat_r)

        # Got a response — deassert bus signals
        ctx.set(bus.cyc, 0)
        ctx.set(bus.stb, 0)
        await ctx.tick()

        if expected_ack:
            assert response == "ack", f"Expected 'ack', got '{response}'"
        return data, response

    raise TimeoutError("Wishbone read: timed out waiting for response")


async def wb_write_pipelined(ctx, bus, addr, data, sel=None, expected_ack=True):
    """Perform a pipelined Wishbone write transaction.

    Phase 1: Drive signals, wait for stall=0, then deassert STB.
    Phase 2: Wait for ACK/ERR/RTY.

    Parameters
    ----------
    ctx : SimulatorContext
        The simulator context from an async testbench.
    bus : wishbone.Interface
        The Wishbone bus interface to drive (must have ``stall`` feature).
    addr : int
        Write address.
    data : int
        Write data.
    sel : int or None
        Byte select. If None, all granules enabled (all 1s).
    expected_ack : bool
        If True, assert that the response is ``"ack"``.

    Returns
    -------
    str
        The response type: ``"ack"``, ``"err"``, or ``"rty"``.
    """
    if sel is None:
        sel = (1 << len(bus.sel)) - 1

    # Drive bus signals
    ctx.set(bus.cyc, 1)
    ctx.set(bus.stb, 1)
    ctx.set(bus.we, 1)
    ctx.set(bus.adr, addr)
    ctx.set(bus.dat_w, data)
    ctx.set(bus.sel, sel)

    # Phase 1: Wait for stall=0 (address phase accepted)
    for _ in range(100):  # Safety limit
        await ctx.tick()
        if not ctx.get(bus.stall):
            # Address phase accepted — deassert STB
            ctx.set(bus.stb, 0)
            break
    else:
        raise TimeoutError("Wishbone pipelined write: timed out waiting for stall deassert")

    # Phase 2: Wait for response
    for _ in range(100):  # Safety limit
        await ctx.tick()
        if ctx.get(bus.ack):
            response = "ack"
        elif hasattr(bus, "err") and ctx.get(bus.err):
            response = "err"
        elif hasattr(bus, "rty") and ctx.get(bus.rty):
            response = "rty"
        else:
            continue

        # Got a response — deassert bus signals
        ctx.set(bus.cyc, 0)
        ctx.set(bus.we, 0)
        await ctx.tick()

        if expected_ack:
            assert response == "ack", f"Expected 'ack', got '{response}'"
        return response

    raise TimeoutError("Wishbone pipelined write: timed out waiting for response")


async def wb_read_pipelined(ctx, bus, addr, sel=None, expected_ack=True):
    """Perform a pipelined Wishbone read transaction.

    Phase 1: Drive signals, wait for stall=0, then deassert STB.
    Phase 2: Wait for ACK/ERR/RTY, capture dat_r.

    Parameters
    ----------
    ctx : SimulatorContext
        The simulator context from an async testbench.
    bus : wishbone.Interface
        The Wishbone bus interface to drive (must have ``stall`` feature).
    addr : int
        Read address.
    sel : int or None
        Byte select. If None, all granules enabled (all 1s).
    expected_ack : bool
        If True, assert that the response is ``"ack"``.

    Returns
    -------
    tuple of (int, str)
        The read data and response type (``"ack"``, ``"err"``, or ``"rty"``).
    """
    if sel is None:
        sel = (1 << len(bus.sel)) - 1

    # Drive bus signals
    ctx.set(bus.cyc, 1)
    ctx.set(bus.stb, 1)
    ctx.set(bus.we, 0)
    ctx.set(bus.adr, addr)
    ctx.set(bus.sel, sel)

    # Phase 1: Wait for stall=0 (address phase accepted)
    for _ in range(100):  # Safety limit
        await ctx.tick()
        if not ctx.get(bus.stall):
            # Address phase accepted — deassert STB
            ctx.set(bus.stb, 0)
            break
    else:
        raise TimeoutError("Wishbone pipelined read: timed out waiting for stall deassert")

    # Phase 2: Wait for response
    for _ in range(100):  # Safety limit
        await ctx.tick()
        if ctx.get(bus.ack):
            response = "ack"
        elif hasattr(bus, "err") and ctx.get(bus.err):
            response = "err"
        elif hasattr(bus, "rty") and ctx.get(bus.rty):
            response = "rty"
        else:
            continue

        # Capture read data
        data = ctx.get(bus.dat_r)

        # Got a response — deassert bus signals
        ctx.set(bus.cyc, 0)
        await ctx.tick()

        if expected_ack:
            assert response == "ack", f"Expected 'ack', got '{response}'"
        return data, response

    raise TimeoutError("Wishbone pipelined read: timed out waiting for response")
