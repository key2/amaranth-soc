CSR Bus Bridges
===============

The CSR subsystem includes protocol bridges that connect the CSR bus to standard bus protocols
(Wishbone and AXI4-Lite).

Wishbone to CSR Bridge
----------------------

.. py:module:: amaranth_soc.csr.wishbone

The :class:`WishboneCSRBridge` translates Wishbone bus transactions into CSR bus transactions.
It handles the width conversion and timing differences between the two protocols.

.. code-block:: python

   from amaranth_soc.csr.wishbone import WishboneCSRBridge

   bridge = WishboneCSRBridge(csr_bus, data_width=32)

.. autoclass:: WishboneCSRBridge
   :members:

AXI4-Lite to CSR Bridge
------------------------

.. py:module:: amaranth_soc.csr.axi_lite

The :class:`AXI4LiteCSRBridge` translates AXI4-Lite bus transactions into CSR bus transactions.

.. code-block:: python

   from amaranth_soc.csr.axi_lite import AXI4LiteCSRBridge

   bridge = AXI4LiteCSRBridge(csr_bus, data_width=32)

.. autoclass:: AXI4LiteCSRBridge
   :members:
