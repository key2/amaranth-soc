System on Chip toolkit
######################

.. warning::

   This manual is a work in progress and is seriously incomplete!

The ``amaranth-soc`` library provides a collection of bus protocols, peripherals, and
integration utilities for building Systems on Chip with `Amaranth HDL <https://amaranth-lang.org/>`_.

.. toctree::
   :maxdepth: 2
   :caption: Introduction

   intro/overview
   intro/getting_started

.. toctree::
   :maxdepth: 2
   :caption: Core Infrastructure

   core/memory
   core/event
   core/bus_common

.. toctree::
   :maxdepth: 2
   :caption: Bus Protocols

   bus/wishbone
   bus/axi

.. toctree::
   :maxdepth: 2
   :caption: CSR (Control & Status Registers)

   csr/index

.. toctree::
   :maxdepth: 2
   :caption: Peripherals

   periph/gpio
   periph/timer
   periph/intc
   periph/info

.. toctree::
   :maxdepth: 2
   :caption: Bus Bridges

   bridge/index

.. toctree::
   :maxdepth: 2
   :caption: DMA Engine

   dma/index

.. toctree::
   :maxdepth: 2
   :caption: SoC Builder

   soc/index

.. toctree::
   :maxdepth: 2
   :caption: CPU Integration

   cpu/index

.. toctree::
   :maxdepth: 2
   :caption: Export Utilities

   export/index

.. toctree::
   :maxdepth: 2
   :caption: Simulation Helpers

   sim/index
