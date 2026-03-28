"""Configurable wait/timeout timer.

Provides :class:`WaitTimer`, the Amaranth equivalent of LiteX's
``WaitTimer``.  Counts clock cycles while ``wait`` is asserted and
asserts ``done`` after the configured number of cycles.
"""

from amaranth import *
from amaranth.lib.wiring import Component, In, Out


__all__ = ["WaitTimer"]


class WaitTimer(Component):
    """Configurable wait/timeout timer.

    Counts up when :attr:`wait` is asserted.  Asserts :attr:`done` after
    *cycles* clock cycles.  Resets the counter when :attr:`wait` is
    deasserted.

    Parameters
    ----------
    cycles : :class:`int`
        Number of clock cycles to wait before asserting ``done``.

    Attributes
    ----------
    wait : Signal, in
        Start / hold the timer.  Counter resets when deasserted.
    done : Signal, out
        Asserted for one or more cycles once the count reaches *cycles*.
        Stays high as long as ``wait`` remains asserted.
    """

    wait: In(1)
    done: Out(1)

    def __init__(self, cycles):
        if cycles < 1:
            raise ValueError(f"cycles must be >= 1, got {cycles}")
        self._cycles = cycles
        super().__init__()

    def elaborate(self, platform):
        m = Module()

        count = Signal(range(self._cycles + 1))

        m.d.comb += self.done.eq(count == self._cycles)

        with m.If(self.wait):
            with m.If(~self.done):
                m.d.sync += count.eq(count + 1)
        with m.Else():
            m.d.sync += count.eq(0)

        return m
