CSR (Control & Status Registers)
#################################

.. py:module:: amaranth_soc.csr

The CSR subsystem provides a complete infrastructure for defining, accessing, and bridging
Control & Status Registers. It is the primary mechanism for software to configure and monitor
hardware peripherals.

Overview
========

The CSR subsystem is organized into several layers:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Layer
     - Description
   * - **Bus**
     - Low-level CSR bus interface, multiplexer, and decoder.
   * - **Registers**
     - High-level register definitions with typed fields and field actions.
   * - **Actions**
     - Predefined field action types (R, W, RW, RW1C, RW1S, etc.).
   * - **Event Monitor**
     - CSR-accessible event monitoring with enable/pending/clear registers.
   * - **Bridges**
     - Protocol bridges from Wishbone and AXI4-Lite to the CSR bus.

.. toctree::
   :maxdepth: 2

   bus
   registers
   actions
   event
   bridges

Architecture
============

The CSR bus uses a simple address/data protocol with read and write strobes. Registers wider
than the bus data width are automatically split into multiple chunks and accessed atomically
using shadow registers.

.. code-block:: text

   CPU Bus (Wishbone/AXI4-Lite)
       │
       ▼
   ┌──────────────────┐
   │  CSR Bridge       │  (WishboneCSRBridge / AXI4LiteCSRBridge)
   └──────────────────┘
       │
       ▼
   ┌──────────────────┐
   │  CSR Decoder      │  (Address routing to sub-buses)
   └──────────────────┘
       │         │
       ▼         ▼
   ┌────────┐ ┌────────┐
   │  Mux   │ │  Mux   │  (CSR Multiplexers)
   └────────┘ └────────┘
       │         │
       ▼         ▼
   [Registers] [Registers]

Quick Example
=============

.. code-block:: python

   from amaranth_soc import csr

   # Define a register with typed fields
   class ControlReg(csr.Register, access="rw"):
       def __init__(self):
           super().__init__({
               "enable":  csr.Field(csr.action.RW, 1),
               "mode":    csr.Field(csr.action.RW, 2),
               "status":  csr.Field(csr.action.R, 4),
           })

   # Build a CSR address space
   regs = csr.Builder(addr_width=8, data_width=8)
   ctrl = regs.add("Control", ControlReg())

   # Create a bridge to connect to a Wishbone or AXI bus
   bridge = csr.Bridge(regs.as_memory_map())
