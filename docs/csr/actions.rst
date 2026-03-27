CSR Field Actions
=================

.. py:module:: amaranth_soc.csr.action

Field actions define the hardware behavior of individual CSR register fields. Each action type
determines how the field responds to reads and writes from the bus.

Overview
--------

.. list-table::
   :header-rows: 1
   :widths: 15 15 70

   * - Action
     - Access
     - Description
   * - :class:`R`
     - Read-only
     - Field value is driven externally. Reads return the current value.
   * - :class:`W`
     - Write-only
     - Field value is written from the bus. Reads return zero.
   * - :class:`RW`
     - Read-write
     - Field value is stored in a flip-flop. Reads return the stored value; writes update it.
   * - :class:`RW1C`
     - Read-write
     - Write-1-to-clear. Writing a 1 to a bit clears it. Bits can be set externally.
   * - :class:`RW1S`
     - Read-write
     - Write-1-to-set. Writing a 1 to a bit sets it. Bits can be cleared externally.
   * - :class:`ResRAW0`
     - Reserved
     - Reserved field. Reads as written, initial value 0.
   * - :class:`ResRAWL`
     - Reserved
     - Reserved field. Reads as last written value.
   * - :class:`ResR0WA`
     - Reserved
     - Reserved field. Reads as 0, writes are accepted.
   * - :class:`ResR0W0`
     - Reserved
     - Reserved field. Reads as 0, writes are ignored.

Usage
-----

Field actions are used as the first argument to :class:`~amaranth_soc.csr.reg.Field`:

.. code-block:: python

   from amaranth_soc import csr

   class MyReg(csr.Register, access="rw"):
       def __init__(self):
           super().__init__({
               "enable":   csr.Field(csr.action.RW, 1),
               "status":   csr.Field(csr.action.R, 4),
               "irq_flag": csr.Field(csr.action.RW1C, 1),
               "_reserved": csr.Field(csr.action.ResR0W0, 2),
           })

Custom Field Actions
--------------------

You can create custom field actions by subclassing :class:`~amaranth_soc.csr.reg.FieldAction`:

.. code-block:: python

   from amaranth_soc.csr.reg import FieldAction

   class MyCustomAction(FieldAction):
       def __init__(self):
           super().__init__(shape=unsigned(8), access="rw", members=(
               ("data", Out(unsigned(8))),
           ))
           self._storage = Signal(unsigned(8))

       def elaborate(self, platform):
           m = Module()
           # Custom read/write logic here
           with m.If(self.port.w_stb):
               m.d.sync += self._storage.eq(self.port.w_data)
           m.d.comb += [
               self.port.r_data.eq(self._storage),
               self.data.eq(self._storage),
           ]
           return m

API Reference
-------------

R (Read-Only)
~~~~~~~~~~~~~

.. autoclass:: R
   :members:

W (Write-Only)
~~~~~~~~~~~~~~

.. autoclass:: W
   :members:

RW (Read-Write)
~~~~~~~~~~~~~~~

.. autoclass:: RW
   :members:

RW1C (Read, Write-1-to-Clear)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: RW1C
   :members:

RW1S (Read, Write-1-to-Set)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: RW1S
   :members:

Reserved Fields
~~~~~~~~~~~~~~~

.. autoclass:: ResRAW0
   :members:

.. autoclass:: ResRAWL
   :members:

.. autoclass:: ResR0WA
   :members:

.. autoclass:: ResR0W0
   :members:
