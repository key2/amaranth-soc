Timer Peripheral
################

.. py:module:: amaranth_soc.periph.timer

The timer peripheral provides a configurable hardware timer with CSR register access,
supporting countdown operation with interrupt generation.

Overview
========

The :class:`TimerPeripheral` provides:

- A configurable-width countdown timer.
- CSR registers for control, reload value, and current counter value.
- An event source that fires when the counter reaches zero.
- Auto-reload capability for periodic operation.

API Reference
=============

.. autoclass:: TimerPeripheral
   :members:

Example
=======

.. code-block:: python

   from amaranth_soc.periph.timer import TimerPeripheral

   # Create a 32-bit timer with CSR access
   timer = TimerPeripheral(width=32, addr_width=4, data_width=8)

   # In elaborate():
   # Connect timer.bus to your CSR bus
   # The timer.irq event source can be connected to an interrupt controller
