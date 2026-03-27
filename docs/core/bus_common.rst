Bus Common Utilities
####################

.. py:module:: amaranth_soc.bus_common

The :mod:`amaranth_soc.bus_common` module provides shared utilities for bus protocol
implementations, including endianness handling and byte-swap logic.

Overview
========

When integrating components with different byte orderings, the bus common module provides:

- :class:`Endianness` — An enumeration of byte orderings (little-endian, big-endian).
- :func:`byte_swap` — A function to generate combinational byte-swap logic.
- :class:`EndianAdapter` — A hardware component that performs byte swapping.

Example
=======

.. code-block:: python

   from amaranth import *
   from amaranth_soc.bus_common import Endianness, byte_swap, EndianAdapter

   # Use byte_swap in combinational logic
   m = Module()
   swapped = byte_swap(m, data_signal, data_width=32)

   # Or use the EndianAdapter component
   adapter = EndianAdapter(data_width=32)

API Reference
=============

Endianness
----------

.. autoclass:: Endianness
   :members:

byte_swap
---------

.. autofunction:: byte_swap

EndianAdapter
-------------

.. autoclass:: EndianAdapter
   :members:
