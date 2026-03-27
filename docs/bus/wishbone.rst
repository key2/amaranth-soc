Wishbone Bus
############

.. py:module:: amaranth_soc.wishbone

The Wishbone bus subsystem implements the `Wishbone B4 <https://cdn.opencores.org/downloads/wbspec_b4.pdf>`_
bus protocol, providing a complete set of components for building Wishbone-based interconnects.

Overview
========

The Wishbone subsystem provides:

- **Bus Interface** — Signature and Interface definitions for Wishbone B4.
- **Decoder** — Address decoder that routes transactions to subordinate interfaces.
- **Arbiter** — Bus arbiter that multiplexes multiple initiator interfaces.
- **SRAM** — A simple SRAM peripheral with Wishbone interface.

Bus Interface
=============

.. py:module:: amaranth_soc.wishbone.bus

The Wishbone bus interface is defined using Amaranth's ``wiring`` library. It supports
configurable address width, data width, granularity, and optional features.

Features
--------

Wishbone optional signals are controlled by the ``features`` parameter:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Feature
     - Description
   * - ``err``
     - Error termination signal. Subordinate asserts to indicate a bus error.
   * - ``rty``
     - Retry signal. Subordinate requests the initiator to retry the transaction.
   * - ``stall``
     - Pipeline stall signal. Used for pipelined Wishbone transactions.
   * - ``lock``
     - Lock signal. Initiator requests exclusive bus access.
   * - ``cti``
     - Cycle Type Identifier. Indicates the type of bus cycle (classic, incrementing burst, etc.).
   * - ``bte``
     - Burst Type Extension. Specifies the burst addressing mode.

Example
-------

.. code-block:: python

   from amaranth_soc.wishbone.bus import Signature, Interface

   # Create a 32-bit Wishbone interface with 8-bit granularity
   sig = Signature(addr_width=30, data_width=32, granularity=8)
   bus = sig.create(path=("wb",))

   # With optional features
   sig = Signature(
       addr_width=30,
       data_width=32,
       granularity=8,
       features={"err", "stall"},
   )

API Reference
-------------

.. autoclass:: amaranth_soc.wishbone.bus.CycleType
   :members:

.. autoclass:: amaranth_soc.wishbone.bus.BurstTypeExt
   :members:

.. autoclass:: amaranth_soc.wishbone.bus.Signature
   :members:

.. autoclass:: amaranth_soc.wishbone.bus.Interface
   :members:

.. autoclass:: amaranth_soc.wishbone.bus.Decoder
   :members:

.. autoclass:: amaranth_soc.wishbone.bus.Arbiter
   :members:

SRAM
====

.. py:module:: amaranth_soc.wishbone.sram

The :class:`SRAM` component provides a simple synchronous SRAM with a Wishbone interface.

Example
-------

.. code-block:: python

   from amaranth_soc.wishbone.sram import SRAM

   # Create a 4 KiB SRAM with 32-bit data width
   sram = SRAM(size=4096, data_width=32, granularity=8)

API Reference
-------------

.. autoclass:: amaranth_soc.wishbone.sram.SRAM
   :members:
