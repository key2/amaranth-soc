CSR Registers
=============

.. py:module:: amaranth_soc.csr.reg

The register module provides high-level abstractions for defining CSR registers with typed
fields, automatic layout, and hardware generation.

Overview
--------

A CSR register is defined by subclassing :class:`Register` and specifying its fields in the
constructor. Each field has a shape (bit width or Amaranth shape) and an action type that
determines its hardware behavior.

Example
~~~~~~~

.. code-block:: python

   from amaranth_soc import csr

   class StatusReg(csr.Register, access="r"):
       """Read-only status register."""
       def __init__(self):
           super().__init__({
               "busy":    csr.Field(csr.action.R, 1),
               "error":   csr.Field(csr.action.R, 1),
               "count":   csr.Field(csr.action.R, 8),
           })

   class ConfigReg(csr.Register, access="rw"):
       """Read-write configuration register."""
       def __init__(self):
           super().__init__({
               "enable":  csr.Field(csr.action.RW, 1),
               "mode":    csr.Field(csr.action.RW, 2),
               "divisor": csr.Field(csr.action.RW, 16),
           })

   class ClearReg(csr.Register, access="rw"):
       """Register with write-1-to-clear fields."""
       def __init__(self):
           super().__init__({
               "irq_a":   csr.Field(csr.action.RW1C, 1),
               "irq_b":   csr.Field(csr.action.RW1C, 1),
           })

Field Port
----------

.. autoclass:: FieldPort
   :members:

.. autoclass:: amaranth_soc.csr.reg.FieldPort.Access
   :members:

.. autoclass:: amaranth_soc.csr.reg.FieldPort.Signature
   :members:

Field
-----

.. autoclass:: Field
   :members:

FieldAction
-----------

.. autoclass:: FieldAction
   :members:

FieldActionMap
--------------

.. autoclass:: FieldActionMap
   :members:

FieldActionArray
----------------

.. autoclass:: FieldActionArray
   :members:

Register
--------

.. autoclass:: Register
   :members:

Builder
-------

The :class:`Builder` provides a convenient way to construct a CSR address space by adding
registers and automatically assigning addresses.

.. code-block:: python

   from amaranth_soc import csr

   regs = csr.Builder(addr_width=8, data_width=8)

   ctrl_reg = regs.add("Control", ControlReg())
   stat_reg = regs.add("Status", StatusReg())

   # Get the memory map for use with a Bridge or Multiplexer
   memory_map = regs.as_memory_map()

.. autoclass:: Builder
   :members:

Bridge
------

The :class:`Bridge` wraps a :class:`Multiplexer` and provides a CSR bus interface for a set
of registers defined by a memory map.

.. code-block:: python

   bridge = csr.Bridge(regs.as_memory_map())
   # bridge.bus is a CSR Interface that can be connected to a decoder or protocol bridge

.. autoclass:: Bridge
   :members:
