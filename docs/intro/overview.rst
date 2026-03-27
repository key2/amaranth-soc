Overview
########

``amaranth-soc`` is a System on Chip toolkit for `Amaranth HDL <https://amaranth-lang.org/>`_.
It provides reusable building blocks for constructing SoC designs, including bus protocols,
peripherals, memory maps, and integration infrastructure.

Architecture
============

The library is organized into several subsystems:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Subsystem
     - Description
   * - **Core Infrastructure**
     - Memory maps, event handling, and bus-common utilities (endianness).
   * - **Wishbone**
     - Wishbone B4 bus protocol with decoder, arbiter, and SRAM components.
   * - **AXI**
     - AXI4 and AXI4-Lite bus protocols with decoders, arbiters, crossbars, SRAM, and timeout monitors.
   * - **CSR**
     - Control & Status Register bus with register definitions, field actions, and bus bridges.
   * - **Peripherals**
     - GPIO, Timer, and Interrupt Controller peripherals.
   * - **Bus Bridges**
     - Protocol bridges: Wishbone ↔ AXI4-Lite, Wishbone → CSR, AXI4-Lite → CSR.
   * - **DMA**
     - DMA reader, writer, and scatter-gather engines.
   * - **SoC Builder**
     - High-level SoC construction with bus, CSR, and IRQ handler integration.
   * - **CPU Integration**
     - CPU wrapper infrastructure for integrating processor cores.
   * - **Export**
     - Utilities for generating C headers, device trees, linker scripts, and SVD files.
   * - **Simulation**
     - Simulation helpers and protocol checkers for Wishbone and AXI buses.

Bus Standard Detection
======================

The top-level :mod:`amaranth_soc` package provides a bus standard detection mechanism:

.. autoclass:: amaranth_soc.BusStandard
   :members:

.. autofunction:: amaranth_soc.detect_bus_standard

Design Philosophy
=================

``amaranth-soc`` follows these principles:

- **Composability**: Components are designed to be composed together using Amaranth's
  ``wiring`` library. Interfaces use ``Signature`` and ``Component`` patterns.
- **Memory Map Driven**: Address decoding and resource management is driven by
  :class:`~amaranth_soc.memory.MemoryMap`, which provides hierarchical address translation.
- **Protocol Agnostic**: The SoC builder can work with multiple bus standards (Wishbone,
  AXI4-Lite, AXI4) through a unified handler interface.
- **Simulation First**: Every bus protocol includes simulation helpers and protocol checkers
  to verify correct behavior before synthesis.
