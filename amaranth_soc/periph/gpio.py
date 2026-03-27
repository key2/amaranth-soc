"""GPIO peripheral (not yet implemented).

This module will provide a CSR-accessible GPIO peripheral for use within
the amaranth_soc.periph framework.

.. note::
    A standalone GPIO implementation already exists at :mod:`amaranth_soc.gpio`.
    This module is reserved for a version that integrates with the peripheral
    base class (:class:`amaranth_soc.periph.base.Peripheral`) and the SoC
    builder infrastructure.

Planned features:
- Pin direction control (input/output/tristate)
- Output value and input readback registers
- Interrupt-on-change support (rising/falling/both edges)
- Per-pin interrupt enable and status registers
"""
