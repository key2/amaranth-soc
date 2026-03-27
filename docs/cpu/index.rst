CPU Integration
###############

.. py:module:: amaranth_soc.cpu

The CPU integration package provides wrapper infrastructure for integrating processor cores
into ``amaranth-soc`` designs.

.. note::

   This package is under active development. The wrapper infrastructure provides base classes
   and bus-specific wrappers for connecting CPU cores to the SoC bus fabric.

Overview
========

The CPU package provides:

- :mod:`~amaranth_soc.cpu.wrapper` — Base CPU wrapper class.
- :mod:`~amaranth_soc.cpu.wb_wrapper` — Wishbone bus CPU wrapper.
- :mod:`~amaranth_soc.cpu.axi_wrapper` — AXI4-Lite bus CPU wrapper.
- :mod:`~amaranth_soc.cpu.vexriscv` — VexRiscv RISC-V CPU integration stub.

CPU Wrapper Base
================

.. py:module:: amaranth_soc.cpu.wrapper

.. automodule:: amaranth_soc.cpu.wrapper
   :members:

Wishbone CPU Wrapper
====================

.. py:module:: amaranth_soc.cpu.wb_wrapper

.. automodule:: amaranth_soc.cpu.wb_wrapper
   :members:

AXI CPU Wrapper
===============

.. py:module:: amaranth_soc.cpu.axi_wrapper

.. automodule:: amaranth_soc.cpu.axi_wrapper
   :members:

VexRiscv Integration
====================

.. py:module:: amaranth_soc.cpu.vexriscv

.. automodule:: amaranth_soc.cpu.vexriscv
   :members:

Usage Pattern
=============

.. code-block:: python

   # Example: Integrating a CPU with a Wishbone bus SoC
   from amaranth_soc.cpu.wb_wrapper import WishboneCPUWrapper

   class MySoC(Elaboratable):
       def elaborate(self, platform):
           m = Module()

           # Instantiate CPU wrapper
           # cpu = WishboneCPUWrapper(...)

           # Connect to bus fabric
           # connect(m, cpu.ibus, decoder.bus)
           # connect(m, cpu.dbus, decoder.bus)

           return m
