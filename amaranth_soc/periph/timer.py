"""Countdown timer peripheral with CSR interface."""

from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out, connect, flipped
from amaranth.utils import ceil_log2

from amaranth_soc import csr
from amaranth_soc.csr import action as csr_action
from amaranth_soc.csr.bus import Multiplexer, Signature as CSRSignature
from amaranth_soc.memory import MemoryMap


__all__ = ["TimerPeripheral"]


class _ReloadReg(csr.Register, access="rw"):
    """Reload value register."""
    def __init__(self, width):
        super().__init__({"reload": csr.Field(csr_action.RW, width)})


class _EnableReg(csr.Register, access="rw"):
    """Timer enable register (1 bit)."""
    def __init__(self):
        super().__init__({"enable": csr.Field(csr_action.RW, 1)})


class _CounterReg(csr.Register, access="r"):
    """Current counter value (read-only)."""
    def __init__(self, width):
        super().__init__({"counter": csr.Field(csr_action.R, width)})


class _EvStatusReg(csr.Register, access="r"):
    """Event status register (read-only). Shows raw event state."""
    def __init__(self):
        super().__init__({"status": csr.Field(csr_action.R, 1)})


class _EvPendingReg(csr.Register, access="rw"):
    """Event pending register. Write 1 to clear."""
    def __init__(self):
        super().__init__({"pending": csr.Field(csr_action.RW1C, 1)})


class _EvEnableReg(csr.Register, access="rw"):
    """Event enable register."""
    def __init__(self):
        super().__init__({"enable": csr.Field(csr_action.RW, 1)})


class TimerPeripheral(wiring.Component):
    """Countdown timer with CSR interface.

    CSR Registers:
    - reload (RW): Reload value
    - enable (RW): Timer enable (1 bit)
    - counter (R): Current counter value
    - ev_status (R): Event status (raw zero event)
    - ev_pending (RW): Event pending (write 1 to clear)
    - ev_enable (RW): Event enable

    When enabled, counter counts down from reload value.
    When counter reaches 0, event fires and counter reloads.

    Parameters
    ----------
    width : int
        Counter width in bits (max 32).
    csr_data_width : int
        CSR bus data width. Default 8.
    """
    def __init__(self, width, *, csr_data_width=8):
        if not isinstance(width, int) or width <= 0:
            raise ValueError(f"Counter width must be a positive integer, not {width!r}")
        if width > 32:
            raise ValueError(f"Counter width cannot exceed 32, got {width}")

        self._width = width

        # Create CSR registers
        self._reload_reg = _ReloadReg(width)
        self._enable_reg = _EnableReg()
        self._counter_reg = _CounterReg(width)
        self._ev_status_reg = _EvStatusReg()
        self._ev_pending_reg = _EvPendingReg()
        self._ev_enable_reg = _EvEnableReg()

        # Build CSR memory map
        reload_size = (width + csr_data_width - 1) // csr_data_width
        enable_size = 1  # 1 bit fits in 1 CSR word
        counter_size = reload_size
        ev_size = 1  # 1 bit each

        # Calculate address width needed for all registers
        total_size = reload_size + enable_size + counter_size + ev_size * 3
        addr_width = max(1, ceil_log2(total_size) + 1)

        memory_map = MemoryMap(addr_width=addr_width, data_width=csr_data_width)
        memory_map.add_resource(self._reload_reg, size=reload_size, name=("reload",))
        memory_map.add_resource(self._enable_reg, size=enable_size, name=("enable",))
        memory_map.add_resource(self._counter_reg, size=counter_size, name=("counter",))
        memory_map.add_resource(self._ev_status_reg, size=ev_size, name=("ev_status",))
        memory_map.add_resource(self._ev_pending_reg, size=ev_size, name=("ev_pending",))
        memory_map.add_resource(self._ev_enable_reg, size=ev_size, name=("ev_enable",))

        # Use Multiplexer directly (like Bridge pattern)
        self._mux = Multiplexer(memory_map)

        # Use the original CSR Signature (not the mux's flipped view)
        csr_sig = CSRSignature(addr_width=memory_map.addr_width,
                               data_width=memory_map.data_width)

        # Component signature: CSR bus + IRQ output
        super().__init__({
            "bus": In(csr_sig),
            "irq": Out(1),
        })
        self.bus.memory_map = memory_map

    @property
    def width(self):
        return self._width

    def elaborate(self, platform):
        m = Module()

        m.submodules.mux = self._mux
        m.submodules.reload = self._reload_reg
        m.submodules.enable = self._enable_reg
        m.submodules.counter = self._counter_reg
        m.submodules.ev_status = self._ev_status_reg
        m.submodules.ev_pending = self._ev_pending_reg
        m.submodules.ev_enable = self._ev_enable_reg

        # Connect CSR bus (following Bridge pattern)
        connect(m, flipped(self.bus), self._mux.bus)

        # Internal counter
        counter = Signal(self._width, name="counter")
        zero_event = Signal(name="zero_event")

        # Get field data outputs
        reload_val = self._reload_reg.f.reload.data
        enable_val = self._enable_reg.f.enable.data

        # Drive counter register read data
        m.d.comb += self._counter_reg.f.counter.r_data.eq(counter)

        # Timer logic
        m.d.comb += zero_event.eq(0)
        with m.If(enable_val):
            with m.If(counter == 0):
                m.d.comb += zero_event.eq(1)
                m.d.sync += counter.eq(reload_val)
            with m.Else():
                m.d.sync += counter.eq(counter - 1)

        # Event status: raw zero event
        m.d.comb += self._ev_status_reg.f.status.r_data.eq(zero_event)

        # Event pending: set on zero event
        m.d.comb += self._ev_pending_reg.f.pending.set.eq(zero_event)

        # IRQ output: pending AND enabled
        ev_pending = self._ev_pending_reg.f.pending.data
        ev_enable = self._ev_enable_reg.f.enable.data
        m.d.comb += self.irq.eq(ev_pending & ev_enable)

        return m
