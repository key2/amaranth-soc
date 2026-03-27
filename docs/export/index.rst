Export Utilities
################

.. py:module:: amaranth_soc.export

The export subsystem provides utilities for generating software artifacts from the SoC's
memory map and register definitions. These artifacts enable software development for the
hardware design.

Overview
========

The following export formats are supported:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Format
     - Description
   * - **C Header**
     - Generates C header files with register address definitions and field macros.
   * - **Device Tree**
     - Generates Device Tree Source (DTS) fragments for Linux kernel integration.
   * - **Linker Script**
     - Generates linker script fragments with memory region definitions.
   * - **SVD**
     - Generates CMSIS-SVD files for use with debugging tools and IDEs.

C Header Generator
==================

.. py:module:: amaranth_soc.export.c_header

The :class:`CHeaderGenerator` produces C header files from a memory map, providing
``#define`` macros for register addresses and field bit positions.

.. autoclass:: amaranth_soc.export.c_header.CHeaderGenerator
   :members:

Example
~~~~~~~

.. code-block:: python

   from amaranth_soc.export.c_header import CHeaderGenerator

   generator = CHeaderGenerator()
   header_text = generator.generate(memory_map, base_name="MY_PERIPH")

   # Output example:
   # #define MY_PERIPH_CTRL_ADDR  0x00000000
   # #define MY_PERIPH_STATUS_ADDR  0x00000004

Device Tree Generator
=====================

.. py:module:: amaranth_soc.export.devicetree

.. automodule:: amaranth_soc.export.devicetree
   :members:

Linker Script Generator
=======================

.. py:module:: amaranth_soc.export.linker

.. automodule:: amaranth_soc.export.linker
   :members:

SVD Generator
=============

.. py:module:: amaranth_soc.export.svd

.. automodule:: amaranth_soc.export.svd
   :members:
