Event Handling
##############

.. py:module:: amaranth_soc.event

The event subsystem provides a mechanism for peripherals to signal events (such as interrupts)
to a central monitor. Events can be level-triggered, rising-edge-triggered, or falling-edge-triggered.

Overview
========

The event system consists of three main components:

- :class:`Source` — An event source interface with configurable trigger mode.
- :class:`EventMap` — A collection of event sources with implicit index assignment.
- :class:`Monitor` — A hardware component that aggregates multiple event sources and provides
  enable, pending, and clear registers.

Trigger Modes
=============

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Mode
     - Description
   * - ``LEVEL``
     - The event is active as long as the input line is asserted.
   * - ``RISE``
     - The event fires on a rising edge of the input line.
   * - ``FALL``
     - The event fires on a falling edge of the input line.

Example
=======

.. code-block:: python

   from amaranth_soc.event import Source, EventMap, Monitor

   # Create event sources
   rx_event = Source(trigger="rise")
   tx_event = Source(trigger="level")

   # Build an event map
   event_map = EventMap()
   event_map.add(rx_event)
   event_map.add(tx_event)

   # Create a monitor that aggregates the events
   monitor = Monitor(event_map, trigger="level")

API Reference
=============

Source
------

.. autoclass:: Source
   :members:

Source.Trigger
~~~~~~~~~~~~~~

.. autoclass:: amaranth_soc.event.Source.Trigger
   :members:

Source.Signature
~~~~~~~~~~~~~~~~

.. autoclass:: amaranth_soc.event.Source.Signature
   :members:

EventMap
--------

.. autoclass:: EventMap
   :members:

Monitor
-------

.. autoclass:: Monitor
   :members:
