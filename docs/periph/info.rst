Peripheral Info & Constants
###########################

.. py:module:: amaranth_soc.periph

The peripheral info module provides metadata classes for describing peripherals and their
configuration constants.

Overview
========

When building an SoC, it is useful to associate metadata with each peripheral, such as its
memory map, IRQ line, and configuration constants. The :class:`PeripheralInfo` class provides
a unified container for this metadata.

Constants
=========

ConstantValue
-------------

.. autoclass:: ConstantValue
   :members:

ConstantBool
------------

.. autoclass:: ConstantBool
   :members:

ConstantInt
-----------

.. autoclass:: ConstantInt
   :members:

ConstantMap
-----------

.. autoclass:: ConstantMap
   :members:

Peripheral Info
===============

.. autoclass:: PeripheralInfo
   :members:

Example
=======

.. code-block:: python

   from amaranth_soc.periph import PeripheralInfo, ConstantMap
   from amaranth_soc.memory import MemoryMap

   memory_map = MemoryMap(addr_width=8, data_width=8)
   # ... add resources to memory_map ...

   info = PeripheralInfo(
       memory_map=memory_map,
       constant_map=ConstantMap(
           FIFO_DEPTH=16,
           VERSION=3,
       ),
   )

   # Query constants
   for name, value in info.constant_map.items():
       print(f"{name} = {value.value}")
