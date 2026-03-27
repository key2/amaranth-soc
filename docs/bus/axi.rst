AXI Bus
#######

.. py:module:: amaranth_soc.axi

The AXI subsystem implements both AXI4 and AXI4-Lite bus protocols, providing a comprehensive
set of components for building AXI-based interconnects.

Overview
========

The AXI subsystem provides:

- **Bus Interface** — Signature and Interface definitions for AXI4 and AXI4-Lite.
- **Decoder** — Address decoders for routing transactions to subordinate interfaces.
- **Arbiter** — Bus arbiters for multiplexing multiple initiator interfaces.
- **Crossbar** — Full crossbar interconnects for AXI4 and AXI4-Lite.
- **SRAM** — SRAM peripherals with AXI4 and AXI4-Lite interfaces.
- **Adapter** — Protocol adapter from AXI4 to AXI4-Lite.
- **Burst** — Burst-to-beat converter for AXI4 burst transactions.
- **Timeout** — Timeout monitors for detecting hung transactions.

Bus Interface
=============

.. py:module:: amaranth_soc.axi.bus

The AXI bus interfaces are defined using Amaranth's ``wiring`` library.

Protocol Enumerations
---------------------

.. autoclass:: amaranth_soc.axi.bus.AXIResp
   :members:

.. autoclass:: amaranth_soc.axi.bus.AXIBurst
   :members:

.. autoclass:: amaranth_soc.axi.bus.AXISize
   :members:

AXI4-Lite
----------

AXI4-Lite is a simplified version of AXI4 that supports only single-beat transactions.

.. code-block:: python

   from amaranth_soc.axi import AXI4LiteSignature, AXI4LiteInterface

   # Create a 32-bit AXI4-Lite interface
   sig = AXI4LiteSignature(addr_width=32, data_width=32)
   bus = AXI4LiteInterface(addr_width=32, data_width=32, path=("axi",))

.. autoclass:: amaranth_soc.axi.bus.AXI4LiteSignature
   :members:

.. autoclass:: amaranth_soc.axi.bus.AXI4LiteInterface
   :members:

AXI4 (Full)
------------

AXI4 supports burst transactions with configurable ID width.

.. code-block:: python

   from amaranth_soc.axi import AXI4Signature, AXI4Interface

   # Create a 64-bit AXI4 interface with 4-bit IDs
   sig = AXI4Signature(addr_width=32, data_width=64, id_width=4)
   bus = AXI4Interface(addr_width=32, data_width=64, id_width=4, path=("axi",))

.. autoclass:: amaranth_soc.axi.bus.AXI4Signature
   :members:

.. autoclass:: amaranth_soc.axi.bus.AXI4Interface
   :members:

Decoder
=======

.. py:module:: amaranth_soc.axi.decoder

Address decoders route AXI transactions to the appropriate subordinate based on the address.

.. autoclass:: amaranth_soc.axi.decoder.AXI4LiteDecoder
   :members:

.. autoclass:: amaranth_soc.axi.decoder.AXI4Decoder
   :members:

Arbiter
=======

.. py:module:: amaranth_soc.axi.arbiter

Bus arbiters multiplex multiple initiator interfaces onto a single subordinate interface.

.. autoclass:: amaranth_soc.axi.arbiter.AXI4LiteArbiter
   :members:

.. autoclass:: amaranth_soc.axi.arbiter.AXI4Arbiter
   :members:

Crossbar
========

.. py:module:: amaranth_soc.axi.crossbar

Crossbar interconnects combine decoders and arbiters to provide full N×M connectivity.

.. code-block:: python

   from amaranth_soc.axi import AXI4LiteCrossbar

   crossbar = AXI4LiteCrossbar(addr_width=32, data_width=32)
   # Add initiator and subordinate ports...

.. autoclass:: amaranth_soc.axi.crossbar.AXI4LiteCrossbar
   :members:

.. autoclass:: amaranth_soc.axi.crossbar.AXI4Crossbar
   :members:

SRAM
====

.. py:module:: amaranth_soc.axi.sram

SRAM peripherals with AXI bus interfaces.

.. code-block:: python

   from amaranth_soc.axi import AXI4LiteSRAM

   # Create a 4 KiB SRAM with AXI4-Lite interface
   sram = AXI4LiteSRAM(size=4096, data_width=32)

.. autoclass:: amaranth_soc.axi.sram.AXI4LiteSRAM
   :members:

.. autoclass:: amaranth_soc.axi.sram.AXI4SRAM
   :members:

Adapter
=======

.. py:module:: amaranth_soc.axi.adapter

Protocol adapter for converting AXI4 transactions to AXI4-Lite.

.. autoclass:: amaranth_soc.axi.adapter.AXI4ToAXI4Lite
   :members:

Burst Converter
===============

.. py:module:: amaranth_soc.axi.burst

The burst-to-beat converter splits AXI4 burst transactions into individual beats.

.. autoclass:: amaranth_soc.axi.burst.AXIBurst2Beat
   :members:

Timeout Monitor
===============

.. py:module:: amaranth_soc.axi.timeout

Timeout monitors detect hung AXI transactions and generate error responses.

.. autoclass:: amaranth_soc.axi.timeout.AXI4LiteTimeout
   :members:

.. autoclass:: amaranth_soc.axi.timeout.AXI4Timeout
   :members:
