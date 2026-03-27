Bus Bridges
###########

.. py:module:: amaranth_soc.bridge

The bridge subsystem provides protocol translation components for connecting buses of
different standards. This enables heterogeneous SoC designs where different parts of the
system use different bus protocols.

Overview
========

The following bridges are available:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Bridge
     - Description
   * - :class:`WishboneToAXI4Lite`
     - Translates Wishbone initiator transactions to AXI4-Lite subordinate transactions.
   * - :class:`AXI4LiteToWishbone`
     - Translates AXI4-Lite initiator transactions to Wishbone subordinate transactions.
   * - :class:`WishboneCSRBridge`
     - Translates Wishbone transactions to CSR bus transactions.
   * - :class:`AXI4LiteCSRBridge`
     - Translates AXI4-Lite transactions to CSR bus transactions.
   * - :class:`BusAdapter`
     - Generic bus adapter registry for automatic bridge selection.

.. code-block:: text

   Wishbone Initiator ──→ WishboneToAXI4Lite ──→ AXI4-Lite Subordinate
   AXI4-Lite Initiator ──→ AXI4LiteToWishbone ──→ Wishbone Subordinate
   Wishbone Initiator ──→ WishboneCSRBridge ──→ CSR Bus
   AXI4-Lite Initiator ──→ AXI4LiteCSRBridge ──→ CSR Bus

Wishbone to AXI4-Lite
=====================

.. py:module:: amaranth_soc.bridge.wb_to_axi

.. autoclass:: amaranth_soc.bridge.wb_to_axi.WishboneToAXI4Lite
   :members:

AXI4-Lite to Wishbone
=====================

.. py:module:: amaranth_soc.bridge.axi_to_wb

.. autoclass:: amaranth_soc.bridge.axi_to_wb.AXI4LiteToWishbone
   :members:

CSR Bridges
===========

The CSR bridges are re-exported from the :mod:`~amaranth_soc.csr` subsystem. See
:doc:`/csr/bridges` for details.

- :class:`~amaranth_soc.bridge.wb_to_csr.WishboneCSRBridge`
- :class:`~amaranth_soc.bridge.axi_to_csr.AXI4LiteCSRBridge`

Bus Adapter Registry
====================

.. py:module:: amaranth_soc.bridge.registry

The :class:`BusAdapter` provides a registry-based mechanism for automatically selecting
the appropriate bridge when connecting buses of different standards.

.. autoclass:: amaranth_soc.bridge.registry.BusAdapter
   :members:

Example
=======

.. code-block:: python

   from amaranth_soc.bridge import WishboneToAXI4Lite, AXI4LiteToWishbone

   # Bridge from Wishbone to AXI4-Lite
   wb_to_axi = WishboneToAXI4Lite(
       addr_width=30,
       data_width=32,
       granularity=8,
   )

   # Bridge from AXI4-Lite to Wishbone
   axi_to_wb = AXI4LiteToWishbone(
       addr_width=30,
       data_width=32,
       granularity=8,
   )
