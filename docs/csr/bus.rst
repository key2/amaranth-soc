CSR Bus
=======

.. py:module:: amaranth_soc.csr.bus

The CSR bus module provides the low-level bus interface, multiplexer, and decoder for
Control & Status Registers.

Bus Protocol
------------

The CSR bus is a simple synchronous protocol with the following signals:

.. list-table::
   :header-rows: 1
   :widths: 15 15 70

   * - Signal
     - Direction
     - Description
   * - ``addr``
     - Initiator → Target
     - Address for reads and writes.
   * - ``r_data``
     - Target → Initiator
     - Read data. Valid on the next cycle after ``r_stb`` is asserted.
   * - ``r_stb``
     - Initiator → Target
     - Read strobe.
   * - ``w_data``
     - Initiator → Target
     - Write data. Must be valid when ``w_stb`` is asserted.
   * - ``w_stb``
     - Initiator → Target
     - Write strobe.

Atomic Access
~~~~~~~~~~~~~

CSR registers wider than the bus data width are split into chunks. The multiplexer uses
shadow registers to ensure atomic access:

- **Reads**: Reading the first chunk captures the entire register value. Subsequent chunk
  reads return the captured value.
- **Writes**: Writing intermediate chunks stores data in a shadow register. Writing the
  last chunk commits the entire value atomically.

Element Interface
-----------------

.. autoclass:: Element
   :members:

.. autoclass:: amaranth_soc.csr.bus.Element.Access
   :members:

.. autoclass:: amaranth_soc.csr.bus.Element.Signature
   :members:

Bus Signature & Interface
-------------------------

.. autoclass:: amaranth_soc.csr.bus.Signature
   :members:

.. autoclass:: Interface
   :members:

Multiplexer
-----------

.. autoclass:: Multiplexer
   :members:

Decoder
-------

.. autoclass:: Decoder
   :members:
