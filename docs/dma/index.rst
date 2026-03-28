DMA Engine
##########

.. py:module:: amaranth_soc.dma

The DMA (Direct Memory Access) subsystem provides hardware components for high-throughput
data transfers without CPU intervention.

Overview
========

The DMA subsystem provides the following components:

**Core transfer engines:**

- :class:`~amaranth_soc.dma.reader.DMAReader` — Reads data from memory via a bus interface.
- :class:`~amaranth_soc.dma.writer.DMAWriter` — Writes data to memory via a bus interface.
- :class:`~amaranth_soc.dma.scatter_gather.ScatterGatherDMA` — A scatter-gather DMA engine
  that processes descriptor lists for complex transfer patterns.

**Descriptor management:**

- :class:`~amaranth_soc.dma.descriptor_table.DMADescriptorTable` — Software-programmable
  scatter-gather descriptor FIFO with prog and loop modes.
- :class:`~amaranth_soc.dma.splitter.DMADescriptorSplitter` — Splits large descriptors into
  bus-sized chunks with auto-incrementing ``user_id``.

**Bus-agnostic controllers:**

- :class:`~amaranth_soc.dma.read_controller.DMAReadController` — DMA read engine that
  generates bus read requests from split descriptors.
- :class:`~amaranth_soc.dma.write_controller.DMAWriteController` — DMA write engine that
  buffers incoming data and issues bus write requests.

**Data-path plugins:**

- :class:`~amaranth_soc.dma.loopback.DMALoopback` — Testing plugin connecting reader
  output directly to writer input when enabled.
- :class:`~amaranth_soc.dma.synchronizer.DMASynchronizer` — Gates data flow until an
  external synchronization event (e.g., PPS signal).
- :class:`~amaranth_soc.dma.buffering.DMABuffering` — Inserts configurable-depth FIFOs
  into reader/writer data paths with CSR-controlled depth.

.. code-block:: text

   Expanded DMA Pipeline
   =====================

   ┌────────────────┐
   │  Descriptor    │   CSR writes (prog mode)
   │  Table         │──────────────────────────┐
   │  (loop / prog) │                          │
   └───────┬────────┘                          │
           │ descriptors                       │
           ▼                                   │
   ┌────────────────┐                          │
   │  Descriptor    │                          │
   │  Splitter      │  max_size chunks         │
   └──┬─────────┬───┘                          │
      │         │                              │
      ▼         ▼                              │
   ┌────────┐ ┌─────────┐                     │
   │  Read  │ │  Write  │                     │
   │  Ctrl  │ │  Ctrl   │                     │
   └───┬────┘ └────┬────┘                     │
       │           │                           │
       ▼           ▼                           │
   ┌────────┐ ┌─────────┐                     │
   │  Bus   │ │  Bus    │                     │
   │  Read  │ │  Write  │                     │
   └───┬────┘ └────┬────┘                     │
       │           ▲                           │
       ▼           │                           │
   ┌──────────────────────┐                    │
   │    Synchronizer      │  PPS / ext sync    │
   └──────────┬───────────┘                    │
              │                                │
              ▼                                │
   ┌──────────────────────┐                    │
   │    Buffering         │  CSR-controlled    │
   │    (FIFO depth)      │  depth & levels    │
   └──────────┬───────────┘                    │
              │                                │
              ▼                                │
   ┌──────────────────────┐                    │
   │    Loopback          │  test mode         │
   │    (reader ↔ writer) │                    │
   └──────────────────────┘                    │

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

DMA Descriptor Table
====================

.. py:module:: amaranth_soc.dma.descriptor_table

The :class:`DMADescriptorTable` is a software-programmable scatter-gather descriptor FIFO
that supports two operating modes:

- **Prog mode:** Descriptors are filled via CSR writes and consumed once. New descriptors
  must be written by the CPU after each transfer.
- **Loop mode:** Consumed descriptors are automatically refilled from the table, enabling
  circular-buffer operation without CPU intervention.

CSR registers:

- ``value`` — Descriptor value to be written into the FIFO.
- ``we`` — Write-enable: commits the current ``value`` into the descriptor FIFO.
- ``mode`` — Selects between prog mode and loop mode.
- ``loop_status`` — Reports whether the loop is active and the current loop position.
- ``level`` — Reports the current fill level of the descriptor FIFO.
- ``reset`` — Resets the descriptor table, clearing all entries.

.. autoclass:: DMADescriptorTable
   :members:

DMA Descriptor Splitter
=======================

.. py:module:: amaranth_soc.dma.splitter

The :class:`DMADescriptorSplitter` takes large DMA descriptors and splits them into
bus-sized chunks of at most ``max_size`` bytes. This ensures that individual bus
transactions do not exceed the maximum burst length supported by the interconnect.

The splitter adds an auto-incrementing ``user_id`` field to each output descriptor,
allowing downstream logic to track which chunk belongs to which original descriptor.

Early termination is supported via the ``terminate`` signal, which causes the splitter
to discard the remaining chunks of the current descriptor and move on to the next one.

.. autoclass:: DMADescriptorSplitter
   :members:

DMA Read Controller
===================

.. py:module:: amaranth_soc.dma.read_controller

The :class:`DMAReadController` is a bus-agnostic DMA read engine. It consumes split
descriptors from a :class:`~amaranth_soc.dma.splitter.DMADescriptorSplitter`, generates
read requests to a bus master port, collects completions, and outputs a data stream.

Key features:

- Pending-word tracking for flow control and back-pressure.
- ``enable`` / ``idle`` CSR fields for software control and status monitoring.
- IRQ raised on descriptor completion for interrupt-driven workflows.

.. autoclass:: DMAReadController
   :members:

DMA Write Controller
====================

.. py:module:: amaranth_soc.dma.write_controller

The :class:`DMAWriteController` is a bus-agnostic DMA write engine. It buffers incoming
data in an internal FIFO, waits until enough data is available for a full bus transaction,
and then issues bus write requests.

Key features:

- ``enable`` / ``idle`` CSR fields for software control and status monitoring.
- Early termination support: when the ``last`` beat is received, the controller flushes
  the remaining data even if the FIFO is not full.
- IRQ raised on descriptor completion for interrupt-driven workflows.

.. autoclass:: DMAWriteController
   :members:

DMA Loopback
=============

.. py:module:: amaranth_soc.dma.loopback

The :class:`DMALoopback` is a testing plugin that connects the DMA reader output directly
to the DMA writer input when enabled via a CSR. When disabled, data passes through to
user-facing ports for normal operation.

This is useful for hardware self-test and verification without requiring an external data
source or sink.

.. autoclass:: DMALoopback
   :members:

DMA Synchronizer
================

.. py:module:: amaranth_soc.dma.synchronizer

The :class:`DMASynchronizer` gates DMA data flow until an external synchronization event
occurs (e.g., a PPS signal for software-defined radio applications).

Operating modes:

- **Disabled** — Data flows freely without synchronization.
- **TX/RX-aware PPS sync** — Synchronizes data flow to a PPS signal with awareness of
  the transfer direction.
- **PPS-only sync** — Synchronizes to PPS without direction awareness.
- **Bypass** — Passes data through unconditionally (similar to disabled, but explicit).

.. autoclass:: DMASynchronizer
   :members:

DMA Buffering
=============

.. py:module:: amaranth_soc.dma.buffering

The :class:`DMABuffering` component inserts configurable-depth FIFOs into the reader
and/or writer data paths to absorb bus latency and throughput variations.

Key features:

- CSR-controlled dynamic FIFO depth.
- Min/max fill-level tracking with instantaneous or watermark reporting.
- Supports independent configuration of reader-side and writer-side buffers.

.. autoclass:: DMABuffering
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

Using the expanded DMA pipeline:

.. code-block:: python

   from amaranth_soc.dma.descriptor_table import DMADescriptorTable
   from amaranth_soc.dma.splitter import DMADescriptorSplitter
   from amaranth_soc.dma.read_controller import DMAReadController
   from amaranth_soc.dma.write_controller import DMAWriteController
   from amaranth_soc.dma.loopback import DMALoopback
   from amaranth_soc.dma.synchronizer import DMASynchronizer
   from amaranth_soc.dma.buffering import DMABuffering

   # Descriptor table with 16-entry FIFO
   desc_table = DMADescriptorTable(depth=16)

   # Splitter: break descriptors into 256-byte bus transactions
   splitter = DMADescriptorSplitter(max_size=256)

   # Read and write controllers
   read_ctrl = DMAReadController(addr_width=32, data_width=32)
   write_ctrl = DMAWriteController(addr_width=32, data_width=32)

   # Optional: loopback for hardware self-test
   loopback = DMALoopback(data_width=32)

   # Optional: synchronize to PPS signal
   sync = DMASynchronizer(data_width=32)

   # Optional: buffering with 512-entry FIFOs
   buffering = DMABuffering(data_width=32, depth=512)
