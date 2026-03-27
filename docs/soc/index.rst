SoC Builder
###########

.. py:module:: amaranth_soc.soc

The SoC builder provides a high-level infrastructure for constructing complete System on Chip
designs. It manages bus interconnects, CSR address spaces, and interrupt routing through a
modular handler-based architecture.

Overview
========

The SoC builder is organized around the following concepts:

- :class:`SoCBuilder` — The main builder class that coordinates all SoC components.
- :class:`SoC` — A base class for SoC designs that provides the builder infrastructure.
- **Handlers** — Modular components that manage specific aspects of the SoC:

  - :class:`BusHandler` — Manages the main bus interconnect.
  - :class:`CSRHandler` — Manages the CSR address space.
  - :class:`IRQHandler` — Manages interrupt routing.

Architecture
============

.. code-block:: text

   ┌──────────────────────────────────────────────┐
   │                  SoC Builder                  │
   │                                               │
   │  ┌─────────────┐  ┌────────────┐  ┌────────┐ │
   │  │ Bus Handler  │  │CSR Handler │  │IRQ     │ │
   │  │             │  │            │  │Handler │ │
   │  │ - Decoder   │  │ - Decoder  │  │        │ │
   │  │ - Arbiter   │  │ - Bridge   │  │        │ │
   │  │ - Crossbar  │  │            │  │        │ │
   │  └─────────────┘  └────────────┘  └────────┘ │
   │         │                │              │     │
   │         ▼                ▼              ▼     │
   │    [Peripherals]   [CSR Regs]    [IRQ Lines]  │
   └──────────────────────────────────────────────┘

SoCBuilder
==========

.. py:module:: amaranth_soc.soc.builder

.. autoclass:: amaranth_soc.soc.builder.SoCBuilder
   :members:

.. autoclass:: amaranth_soc.soc.builder.SoC
   :members:

Bus Handler
===========

.. py:module:: amaranth_soc.soc.bus_handler

The bus handler manages the main bus interconnect of the SoC. Different implementations
are provided for different bus standards.

.. autoclass:: BusHandler
   :members:

.. autoclass:: AXI4LiteBusHandler
   :members:

.. autoclass:: WishboneBusHandler
   :members:

CSR Handler
===========

.. py:module:: amaranth_soc.soc.csr_handler

The CSR handler manages the CSR address space, providing automatic address assignment
and bridge generation.

.. autoclass:: CSRHandler
   :members:

IRQ Handler
===========

.. py:module:: amaranth_soc.soc.irq_handler

The IRQ handler manages interrupt routing from peripherals to the CPU.

.. autoclass:: IRQHandler
   :members:

Platform
========

.. py:module:: amaranth_soc.soc.platform
   :no-index:

.. automodule:: amaranth_soc.soc.platform
   :members:
   :no-index:

Example
=======

.. code-block:: python

   from amaranth_soc.soc import SoC

   class MySoC(SoC):
       def __init__(self):
           super().__init__()
           # Add peripherals, configure bus, CSR, and IRQ handlers
           # ...

       def elaborate(self, platform):
           m = super().elaborate(platform)
           # Add custom logic
           return m
