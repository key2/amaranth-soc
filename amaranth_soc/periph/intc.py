"""Simple priority-based interrupt controller with CSR interface."""

from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out, connect, flipped
from amaranth.utils import ceil_log2

from amaranth_soc import csr
from amaranth_soc.csr import action as csr_action
from amaranth_soc.csr.bus import Multiplexer, Signature as CSRSignature
from amaranth_soc.memory import MemoryMap


__all__ = ["InterruptController"]


class _PendingReg(csr.Register, access="rw"):
    """Pending IRQ register. Read shows pending IRQs, write-1-to-clear."""
    def __init__(self, n_irqs):
        super().__init__({"pending": csr.Field(csr_action.RW1C, n_irqs)})


class _EnableReg(csr.Register, access="rw"):
    """Enable IRQ register. Read/write to enable/disable individual IRQs."""
    def __init__(self, n_irqs):
        super().__init__({"enable": csr.Field(csr_action.RW, n_irqs)})


class InterruptController(wiring.Component):
    """Simple priority-based interrupt controller.

    Per-IRQ enable/disable, pending status, edge-triggered with software clear.
    Aggregates N IRQ sources into a single CPU interrupt output.

    CSR registers:
    - pending (RW): Which IRQs are pending (1 bit per IRQ, write-1-to-clear)
    - enable (RW): Which IRQs are enabled (1 bit per IRQ)

    Interrupt output = OR of (pending & enable)

    Parameters
    ----------
    n_irqs : int
        Number of IRQ inputs.
    csr_data_width : int
        CSR bus data width. Default 8.
    """
    def __init__(self, n_irqs, *, csr_data_width=8):
        if not isinstance(n_irqs, int) or n_irqs <= 0:
            raise ValueError(f"Number of IRQs must be a positive integer, not {n_irqs!r}")
        if n_irqs > 32:
            raise ValueError(f"Number of IRQs cannot exceed 32, got {n_irqs}")

        self._n_irqs = n_irqs

        # Create CSR registers
        self._pending_reg = _PendingReg(n_irqs)
        self._enable_reg = _EnableReg(n_irqs)

        # Build CSR memory map
        reg_size = (n_irqs + csr_data_width - 1) // csr_data_width
        addr_width = 1 + max(ceil_log2(reg_size), 0)
        memory_map = MemoryMap(addr_width=addr_width, data_width=csr_data_width)
        memory_map.add_resource(self._pending_reg, size=reg_size, name=("pending",))
        memory_map.add_resource(self._enable_reg, size=reg_size, name=("enable",))

        # Use Multiplexer directly (like Bridge pattern)
        self._mux = Multiplexer(memory_map)

        # Use the original CSR Signature (not the mux's flipped view)
        csr_sig = CSRSignature(addr_width=memory_map.addr_width,
                               data_width=memory_map.data_width)

        # Component signature: CSR bus + IRQ inputs + interrupt output
        super().__init__({
            "bus": In(csr_sig),
            "irq_inputs": In(n_irqs),
            "irq_out": Out(1),
        })
        self.bus.memory_map = memory_map

    @property
    def n_irqs(self):
        return self._n_irqs

    def elaborate(self, platform):
        m = Module()

        m.submodules.mux = self._mux
        m.submodules.pending = self._pending_reg
        m.submodules.enable = self._enable_reg

        # Connect CSR bus (following Bridge pattern)
        connect(m, flipped(self.bus), self._mux.bus)

        # Edge detection: detect rising edges on IRQ inputs
        irq_prev = Signal(self._n_irqs, name="irq_prev")
        m.d.sync += irq_prev.eq(self.irq_inputs)

        # Rising edge = input is high AND was low
        irq_rising = Signal(self._n_irqs, name="irq_rising")
        m.d.comb += irq_rising.eq(self.irq_inputs & ~irq_prev)

        # Set pending bits on rising edge via the RW1C field's set input
        m.d.comb += self._pending_reg.f.pending.set.eq(irq_rising)

        # Interrupt output = OR of (pending & enable)
        pending_val = self._pending_reg.f.pending.data
        enable_val = self._enable_reg.f.enable.data
        m.d.comb += self.irq_out.eq((pending_val & enable_val).any())

        return m
