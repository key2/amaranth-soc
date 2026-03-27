Interrupt Controllers
#####################

.. py:module:: amaranth_soc.periph.intc

The interrupt controller module provides hardware components for managing interrupt sources
in an SoC design.

Overview
========

Two interrupt controller implementations are provided:

- :class:`InterruptController` — A standard interrupt controller with CSR-accessible
  enable, pending, and clear registers.
- :class:`MSIInterruptController` — A Message Signaled Interrupt (MSI) controller that
  generates memory-mapped interrupt messages.

InterruptController
===================

.. autoclass:: InterruptController
   :members:

MSIInterruptController
======================

.. autoclass:: MSIInterruptController
   :members:

Example
=======

.. code-block:: python

   from amaranth_soc.periph.intc import InterruptController

   # Create an interrupt controller for 8 sources
   intc = InterruptController(source_count=8, addr_width=4, data_width=8)

   # Connect interrupt sources
   # intc.sources[0].eq(uart_irq)
   # intc.sources[1].eq(timer_irq)
   # ...

   # The intc.irq output is the combined interrupt line
