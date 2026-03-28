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

External Register Ownership
---------------------------

When a peripheral creates and owns its own CSR registers, and you want to expose them via a
CSR bus bridge, you must use ``ownership="external"`` to avoid ``DuplicateElaboratable`` errors.

The Problem
~~~~~~~~~~~

By default, :class:`Bridge` uses ``ownership="owned"``, which means it adds each register as a
submodule during elaboration. If the peripheral *also* adds those same registers as submodules
(which it must, to connect their field ports to internal logic), Amaranth raises a
``DuplicateElaboratable`` error because the same component object appears in two places in the
module hierarchy.

.. code-block:: text

   # This fails at elaboration time:
   Peripheral.elaborate()  →  m.submodules.ctrl = self._ctrl_reg   ← register added here
   Bridge.elaborate()      →  m.submodules.ctrl = self._ctrl_reg   ← DUPLICATE!

The Solution
~~~~~~~~~~~~

Use ``Bridge(memory_map, ownership="external")`` or the convenience method
:meth:`Bridge.from_peripheral` to create a bridge that does **not** add registers as
submodules. The peripheral remains responsible for elaborating its own registers.

.. code-block:: python

   from amaranth import *
   from amaranth.lib import wiring
   from amaranth.lib.wiring import In, Out, connect, flipped

   from amaranth_soc import csr
   from amaranth_soc.csr import action as csr_action
   from amaranth_soc.csr.wishbone import WishboneCSRBridge


   class ControlReg(csr.Register, access="rw"):
       def __init__(self):
           super().__init__({
               "enable":  csr.Field(csr_action.RW, 1),
               "mode":    csr.Field(csr_action.RW, 2),
               "divisor": csr.Field(csr_action.RW, 8),
           })


   class StatusReg(csr.Register, access="r"):
       def __init__(self):
           super().__init__({
               "busy":  csr.Field(csr_action.R, 1),
               "error": csr.Field(csr_action.R, 1),
           })


   class MyPeripheral(wiring.Component):
       """A peripheral that owns its CSR registers."""

       def __init__(self, *, csr_data_width=8):
           # 1. Create registers (owned by this peripheral)
           self._ctrl = ControlReg()
           self._status = StatusReg()

           # 2. Build a CSR memory map using Builder
           regs = csr.Builder(addr_width=8, data_width=csr_data_width)
           regs.add("Control", self._ctrl)
           regs.add("Status", self._status)

           # 3. Create a Bridge with ownership="external"
           self._bridge = csr.Bridge(regs.as_memory_map(), ownership="external")

           # 4. Optionally wrap with a Wishbone-to-CSR bridge
           self._wb_bridge = WishboneCSRBridge(self._bridge.bus, data_width=32)

           super().__init__({
               "bus": Out(self._wb_bridge.wb_bus.signature),
           })

       def elaborate(self, platform):
           m = Module()

           # The peripheral adds its own registers as submodules
           m.submodules.ctrl = self._ctrl
           m.submodules.status = self._status

           # The bridge does NOT add them again (ownership="external")
           m.submodules.bridge = self._bridge
           m.submodules.wb_bridge = self._wb_bridge

           connect(m, flipped(self.bus), self._wb_bridge.wb_bus)

           # Peripheral logic using register field ports
           m.d.comb += self._status.f.busy.r_data.eq(self._ctrl.f.enable.data)

           return m

Using ``Bridge.from_peripheral()``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The :meth:`Bridge.from_peripheral` class method is a convenience wrapper that creates a
:class:`Builder`, adds the registers, and returns a :class:`Bridge` with
``ownership="external"`` in a single call:

.. code-block:: python

   class MyPeripheral(wiring.Component):
       def __init__(self, *, csr_data_width=8):
           self._ctrl = ControlReg()
           self._status = StatusReg()

           # One-liner: builds memory map + bridge with external ownership
           self._bridge = csr.Bridge.from_peripheral(
               {"Control": self._ctrl, "Status": self._status},
               addr_width=8,
               data_width=csr_data_width,
           )
           super().__init__(...)

``Bridge.from_peripheral()`` API Reference
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. method:: Bridge.from_peripheral(registers, *, addr_width, data_width=8, register_addr=None, register_alignment=None, name=None)
   :classmethod:
   :no-index:

   Create a :class:`Bridge` for registers owned by an external peripheral.

   :param registers: A mapping of register names to :class:`Register` objects.
   :type registers: dict[str, Register]
   :param addr_width: Address width of the CSR bus.
   :type addr_width: int
   :param data_width: Data width of the CSR bus. Defaults to ``8``.
   :type data_width: int
   :param register_addr: Optional mapping of register names to explicit addresses.
   :type register_addr: dict[str, int] or None
   :param register_alignment: Optional alignment for register addresses.
   :type register_alignment: int or None
   :param name: Optional name for the Bridge.
   :type name: str or None
   :returns: A :class:`Bridge` instance with ``ownership="external"``.
   :rtype: Bridge

.. note::

   If a register is added to multiple :class:`Builder` instances, a warning is emitted
   suggesting the use of ``ownership="external"``. This is expected when the same register
   objects are shared between a peripheral's internal builder and an external bridge builder.
