Getting Started
###############

Installation
============

``amaranth-soc`` requires Python 3.9+ and `Amaranth HDL <https://amaranth-lang.org/>`_.

Install from the project directory:

.. code-block:: bash

   pip install .

Or for development:

.. code-block:: bash

   pip install -e ".[dev]"

Quick Example
=============

Here is a minimal example that creates a Wishbone bus with an SRAM peripheral:

.. code-block:: python

   from amaranth import *
   from amaranth.lib.wiring import connect
   from amaranth_soc.wishbone import Signature as WishboneSignature
   from amaranth_soc.wishbone.sram import SRAM

   class MySoC(Elaboratable):
       def elaborate(self, platform):
           m = Module()

           # Create a 1 KiB SRAM with 32-bit Wishbone interface
           m.submodules.sram = sram = SRAM(
               size=1024,
               data_width=32,
               granularity=8,
           )

           return m

Memory Map Example
==================

The :class:`~amaranth_soc.memory.MemoryMap` is the foundation of address management:

.. code-block:: python

   from amaranth_soc.memory import MemoryMap

   # Create a memory map with 16-bit addresses and 8-bit data
   memory_map = MemoryMap(addr_width=16, data_width=8)

   # Resources and windows can be added to build the address space
   # See the Memory Map documentation for details.

CSR Register Example
====================

Define a CSR register with typed fields:

.. code-block:: python

   from amaranth_soc import csr

   class MyRegister(csr.Register, access="rw"):
       def __init__(self):
           super().__init__({
               "enable": csr.Field(csr.action.RW, 1),
               "status": csr.Field(csr.action.R, 4),
               "config": csr.Field(csr.action.RW, 8),
           })

.. tip::

   When a peripheral owns its CSR registers and also needs a :class:`~amaranth_soc.csr.Bridge`
   to expose them on a bus, use ``Bridge.from_peripheral()`` or
   ``Bridge(memory_map, ownership="external")`` to avoid ``DuplicateElaboratable`` errors.
   See :doc:`/csr/registers` for details and ``examples/csr_external_ownership.py`` for a
   runnable example.

Project Structure
=================

A typical ``amaranth-soc`` project is organized as follows:

.. code-block:: text

   my_soc/
   ├── peripherals/       # Custom peripheral definitions
   │   ├── uart.py
   │   └── spi.py
   ├── soc.py             # Top-level SoC definition
   ├── sim/               # Simulation testbenches
   │   └── test_soc.py
   └── build/             # Build scripts and outputs
       └── platform.py
