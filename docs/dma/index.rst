DMA Engine
##########

.. py:module:: amaranth_soc.dma

The DMA (Direct Memory Access) subsystem provides hardware components for high-throughput
data transfers without CPU intervention.

Overview
========

The DMA subsystem provides three main components:

- :class:`~amaranth_soc.dma.reader.DMAReader` — Reads data from memory via a bus interface.
- :class:`~amaranth_soc.dma.writer.DMAWriter` — Writes data to memory via a bus interface.
- :class:`~amaranth_soc.dma.scatter_gather.ScatterGatherDMA` — A scatter-gather DMA engine
  that processes descriptor lists for complex transfer patterns.

.. code-block:: text

   ┌─────────────┐     ┌──────────┐     ┌──────────────┐
   │  DMA Reader  │────→│  Stream  │────→│  DMA Writer   │
   │  (bus read)  │     │  FIFO    │     │  (bus write)  │
   └─────────────┘     └──────────┘     └──────────────┘
         │                                      │
         ▼                                      ▼
   ┌──────────┐                          ┌──────────┐
   │ Source    │                          │ Dest     │
   │ Memory   │                          │ Memory   │
   └──────────┘                          └──────────┘

Common Types
============

.. py:module:: amaranth_soc.dma.common

.. autoclass:: amaranth_soc.dma.common.DMAStatus
   :members:

DMA Reader
==========

.. py:module:: amaranth_soc.dma.reader

The :class:`DMAReader` reads data from a bus interface and produces a data stream.

.. autoclass:: DMAReader
   :members:

DMA Writer
==========

.. py:module:: amaranth_soc.dma.writer

The :class:`DMAWriter` consumes a data stream and writes it to a bus interface.

.. autoclass:: DMAWriter
   :members:

Scatter-Gather DMA
==================

.. py:module:: amaranth_soc.dma.scatter_gather

The :class:`ScatterGatherDMA` processes a list of descriptors, each specifying a source
address, destination address, and transfer length. This enables complex transfer patterns
such as gathering data from multiple non-contiguous source regions and scattering it to
multiple destination regions.

.. autoclass:: ScatterGatherDMA
   :members:

Example
=======

.. code-block:: python

   from amaranth_soc.dma import DMAReader, DMAWriter, ScatterGatherDMA

   # Simple DMA reader
   reader = DMAReader(addr_width=32, data_width=32)

   # Simple DMA writer
   writer = DMAWriter(addr_width=32, data_width=32)

   # Scatter-gather DMA engine
   sg_dma = ScatterGatherDMA(
       addr_width=32,
       data_width=32,
       max_descriptors=16,
   )
