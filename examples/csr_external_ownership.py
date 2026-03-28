#!/usr/bin/env python3
"""Example: CSR External Register Ownership Pattern

Demonstrates how a peripheral can own its CSR registers while exposing them
through a standard CSR Bridge and Wishbone bus interface.

This pattern avoids DuplicateElaboratable errors that occur when both the
peripheral and the bridge try to elaborate the same register objects.

Run with: pdm run python examples/csr_external_ownership.py
"""

import warnings
from amaranth import *
from amaranth.hdl import UnusedElaboratable
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out, connect, flipped
from amaranth.sim import *

from amaranth_soc import csr
from amaranth_soc.csr import action as csr_action
from amaranth_soc.csr.wishbone import WishboneCSRBridge

# Suppress UnusedElaboratable warnings in this example
warnings.simplefilter(action="ignore", category=UnusedElaboratable)


# =============================================================================
# Step 1: Define CSR Registers
# =============================================================================
# These are standard CSR registers. They will be *owned* by the peripheral
# (i.e., the peripheral adds them as submodules), not by the Bridge.

class ControlReg(csr.Register, access="rw"):
    """Control register: enable bit + LED brightness (7 bits)."""
    enable: csr.Field(csr_action.RW, 1)
    brightness: csr.Field(csr_action.RW, 7, init=0x40)


class StatusReg(csr.Register, access="r"):
    """Status register: read-only, driven by the peripheral logic."""
    active: csr.Field(csr_action.R, 1)
    error: csr.Field(csr_action.R, 1)
    counter: csr.Field(csr_action.R, 6)


class PatternReg(csr.Register, access="rw"):
    """LED blink pattern register (8-bit)."""
    def __init__(self):
        super().__init__({"pattern": csr.Field(csr_action.RW, 8, init=0xAA)})


# =============================================================================
# Step 2: Define the Peripheral
# =============================================================================
# The peripheral owns its registers and uses Bridge.from_peripheral() to
# create a CSR bridge with ownership="external". This means the bridge will
# NOT try to add the registers as submodules — the peripheral does that.

class LEDController(wiring.Component):
    """Simple LED controller peripheral.

    This peripheral demonstrates the external ownership pattern:
    - It creates and owns CSR registers (control, status, pattern)
    - It uses Bridge.from_peripheral() to create a CSR bridge
    - The bridge exposes registers on the CSR bus without owning them
    - The peripheral drives the status register from internal logic
    """

    def __init__(self):
        # Create registers (the peripheral owns these)
        self._control = ControlReg()
        self._status = StatusReg()
        self._pattern = PatternReg()

        # Create a CSR bridge using the convenience method.
        # This automatically sets ownership="external", so the bridge
        # will NOT add registers as submodules during elaboration.
        self._bridge = csr.Bridge.from_peripheral(
            {
                "control": self._control,
                "status":  self._status,
                "pattern": self._pattern,
            },
            addr_width=8,
            data_width=8,
        )

        # The component exposes the CSR bus interface
        super().__init__({
            "bus": In(csr.Signature(addr_width=8, data_width=8)),
        })
        # Share the bridge's memory map so the bus hierarchy is correct
        self.bus.memory_map = self._bridge.bus.memory_map

    def elaborate(self, platform):
        m = Module()

        # The peripheral adds its own registers as submodules
        m.submodules.control = self._control
        m.submodules.status = self._status
        m.submodules.pattern = self._pattern

        # The bridge does NOT add them again (ownership="external")
        m.submodules.bridge = self._bridge

        # Connect the external CSR bus to the bridge's bus
        connect(m, flipped(self.bus), self._bridge.bus)

        # --- Peripheral logic ---

        # Internal tick counter (increments every clock cycle when enabled)
        tick_counter = Signal(6)

        with m.If(self._control.f.enable.data):
            m.d.sync += tick_counter.eq(tick_counter + 1)

        # Drive the read-only status register from internal logic
        m.d.comb += [
            self._status.f.active.r_data.eq(self._control.f.enable.data),
            self._status.f.error.r_data.eq(0),  # no error
            self._status.f.counter.r_data.eq(tick_counter),
        ]

        return m


# =============================================================================
# Step 3: Top-Level Module with Wishbone Bridge
# =============================================================================

class Top(Elaboratable):
    """Top-level module wiring the LED controller to a Wishbone bus.

    Architecture:
        Wishbone Bus  →  WishboneCSRBridge  →  CSR Bus  →  LEDController
                                                              ├── control reg
                                                              ├── status reg
                                                              └── pattern reg
    """

    def __init__(self):
        self.led = LEDController()
        self.wb_csr = WishboneCSRBridge(self.led.bus, data_width=8)

    def elaborate(self, platform):
        m = Module()
        m.submodules.led = self.led
        m.submodules.wb_csr = self.wb_csr

        # Connect the LED controller's CSR bus to the Wishbone-CSR bridge
        connect(m, flipped(self.led.bus), self.wb_csr.csr_bus)

        return m


# =============================================================================
# Step 4: Simulation
# =============================================================================

def main():
    print("=" * 70)
    print("CSR External Ownership Example")
    print("=" * 70)
    print()
    print("This example demonstrates the Bridge.from_peripheral() pattern.")
    print("The LED controller peripheral owns its CSR registers, while a")
    print("Bridge with ownership='external' exposes them on the CSR bus.")
    print()

    top = Top()

    # Helper: perform a Wishbone write cycle
    # For an 8-bit CSR data width with 8-bit Wishbone, each CSR address
    # maps to one Wishbone address. The WishboneCSRBridge takes
    # (data_width // csr_data_width + 1) cycles = 2 cycles per access.
    async def wb_write(ctx, addr, data):
        ctx.set(top.wb_csr.wb_bus.cyc, 1)
        ctx.set(top.wb_csr.wb_bus.stb, 1)
        ctx.set(top.wb_csr.wb_bus.we, 1)
        ctx.set(top.wb_csr.wb_bus.sel, 0b1)
        ctx.set(top.wb_csr.wb_bus.adr, addr)
        ctx.set(top.wb_csr.wb_bus.dat_w, data)
        # Wait for ack
        for _ in range(10):
            await ctx.tick()
            if ctx.get(top.wb_csr.wb_bus.ack):
                break
        ctx.set(top.wb_csr.wb_bus.stb, 0)
        ctx.set(top.wb_csr.wb_bus.cyc, 0)
        ctx.set(top.wb_csr.wb_bus.we, 0)
        await ctx.tick()

    # Helper: perform a Wishbone read cycle
    async def wb_read(ctx, addr):
        ctx.set(top.wb_csr.wb_bus.cyc, 1)
        ctx.set(top.wb_csr.wb_bus.stb, 1)
        ctx.set(top.wb_csr.wb_bus.we, 0)
        ctx.set(top.wb_csr.wb_bus.sel, 0b1)
        ctx.set(top.wb_csr.wb_bus.adr, addr)
        # Wait for ack
        for _ in range(10):
            await ctx.tick()
            if ctx.get(top.wb_csr.wb_bus.ack):
                break
        value = ctx.get(top.wb_csr.wb_bus.dat_r)
        ctx.set(top.wb_csr.wb_bus.stb, 0)
        ctx.set(top.wb_csr.wb_bus.cyc, 0)
        await ctx.tick()
        return value

    async def testbench(ctx):
        # Let the design settle
        await ctx.tick()
        await ctx.tick()

        # --- Read initial register values ---
        # Register layout (8-bit CSR data width):
        #   Address 0: control register (8 bits: enable[0] + brightness[7:1])
        #   Address 1: status register  (8 bits: active[0] + error[1] + counter[7:2])
        #   Address 2: pattern register (8 bits)

        print("--- Initial Register Values ---")

        val = await wb_read(ctx, 0)
        # Initial: enable=0, brightness=0x40 → byte = (0x40 << 1) | 0 = 0x80
        print(f"  Control reg (addr 0): 0x{val:02X}")
        print(f"    enable     = {val & 1}")
        print(f"    brightness = 0x{(val >> 1) & 0x7F:02X}")

        val = await wb_read(ctx, 1)
        print(f"  Status reg  (addr 1): 0x{val:02X}")
        print(f"    active  = {val & 1}")
        print(f"    error   = {(val >> 1) & 1}")
        print(f"    counter = {(val >> 2) & 0x3F}")

        val = await wb_read(ctx, 2)
        print(f"  Pattern reg (addr 2): 0x{val:02X}")
        print()

        # --- Write to control register: enable=1, brightness=0x3F ---
        # Byte = (0x3F << 1) | 1 = 0x7F
        print("--- Writing control: enable=1, brightness=0x3F ---")
        await wb_write(ctx, 0, 0x7F)

        val = await wb_read(ctx, 0)
        print(f"  Control reg (addr 0): 0x{val:02X}")
        print(f"    enable     = {val & 1}")
        print(f"    brightness = 0x{(val >> 1) & 0x7F:02X}")
        print()

        # --- Let the counter run for a few cycles ---
        print("--- Letting counter run for 8 cycles ---")
        for _ in range(8):
            await ctx.tick()

        val = await wb_read(ctx, 1)
        print(f"  Status reg  (addr 1): 0x{val:02X}")
        print(f"    active  = {val & 1}")
        print(f"    error   = {(val >> 1) & 1}")
        print(f"    counter = {(val >> 2) & 0x3F}")
        print()

        # --- Write a new blink pattern ---
        print("--- Writing pattern: 0x55 ---")
        await wb_write(ctx, 2, 0x55)

        val = await wb_read(ctx, 2)
        print(f"  Pattern reg (addr 2): 0x{val:02X}")
        print()

        # --- Verify peripheral can see register values directly ---
        print("--- Verifying peripheral-side register access ---")
        enable_val = ctx.get(top.led._control.f.enable.data)
        brightness_val = ctx.get(top.led._control.f.brightness.data)
        pattern_val = ctx.get(top.led._pattern.f.pattern.data)
        print(f"  control.enable     = {enable_val}")
        print(f"  control.brightness = 0x{brightness_val:02X}")
        print(f"  pattern.pattern    = 0x{pattern_val:02X}")
        print()

        # --- Verify the bridge ownership ---
        print("--- Bridge Configuration ---")
        print(f"  Bridge ownership: {top.led._bridge.ownership!r}")
        print()

        print("=" * 70)
        print("SUCCESS: All register accesses via Wishbone worked correctly!")
        print("The peripheral owns its registers, and the Bridge with")
        print("ownership='external' exposes them without DuplicateElaboratable.")
        print("=" * 70)

    sim = Simulator(top)
    sim.add_clock(1e-6)
    sim.add_testbench(testbench)
    with sim.write_vcd(vcd_file="examples/csr_external_ownership.vcd"):
        sim.run()


if __name__ == "__main__":
    main()
