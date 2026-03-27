Memory Map
##########

.. py:module:: amaranth_soc.memory

The memory map is the foundation of address management in ``amaranth-soc``. It provides a
hierarchical description of an address space, describing the structure of address decoders
of peripherals as well as bus bridges.

Overview
========

A :class:`MemoryMap` is built by adding **resources** (range allocations for registers, memory,
etc.) and **windows** (range allocations for bus bridges). It can be queried later to determine
the address of any given resource from a specific vantage point in the design.

Address assignment is simplified by an implicit next address that starts at 0. If a resource or
window is added without specifying an address explicitly, the implicit next address is used.

Example
-------

.. code-block:: python

   from amaranth_soc.memory import MemoryMap

   # Create a 16-bit address space with 8-bit data width
   memory_map = MemoryMap(addr_width=16, data_width=8)

   # Add a resource at the next available address
   start, end = memory_map.add_resource(my_peripheral, name="uart", size=0x100)

   # Add a window for a sub-bus
   sub_map = MemoryMap(addr_width=12, data_width=8)
   start, end, ratio = memory_map.add_window(sub_map, name="csr")

   # Query all resources recursively
   for info in memory_map.all_resources():
       print(f"{info.path}: {info.start:#x}..{info.end:#x}")

API Reference
=============

ResourceInfo
------------

.. autoclass:: ResourceInfo
   :members:

MemoryMap
---------

.. autoclass:: MemoryMap
   :members:

MemoryMap.Name
~~~~~~~~~~~~~~

.. autoclass:: amaranth_soc.memory.MemoryMap.Name
   :members:

BARMemoryMap
------------

.. autoclass:: BARMemoryMap
   :members:

The :class:`BARMemoryMap` wraps a :class:`MemoryMap` with a BAR (Base Address Register) concept,
useful for PCIe and runtime-configured address spaces. Resources are added at offsets relative
to the BAR base, and the base address can be configured at runtime.

Example
~~~~~~~

.. code-block:: python

   from amaranth_soc.memory import BARMemoryMap

   bar = BARMemoryMap(bar_index=0, size=4096, data_width=8)
   bar.add_resource(my_reg, name="ctrl", size=4)

   # Set runtime base address
   bar.base_addr = 0xFE00_0000

   # Convert between relative and absolute addresses
   abs_addr = bar.absolute_addr(0x10)   # 0xFE000010
   rel_addr = bar.relative_addr(abs_addr)  # 0x10
