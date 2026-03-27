CSR Event Monitor
=================

.. py:module:: amaranth_soc.csr.event

The CSR event monitor provides CSR-accessible registers for monitoring and controlling
hardware events. It wraps the core :mod:`~amaranth_soc.event` subsystem with CSR registers
for enable, pending, and clear operations.

Overview
--------

The :class:`EventMonitor` creates CSR registers that allow software to:

- **Enable/disable** individual event sources via a mask register.
- **Read pending** events to determine which events have fired.
- **Clear pending** events by writing to the appropriate register.

Example
-------

.. code-block:: python

   from amaranth_soc.event import Source, EventMap
   from amaranth_soc.csr.event import EventMonitor

   # Create event sources
   rx_event = Source(trigger="rise")
   tx_event = Source(trigger="level")

   # Build event map
   event_map = EventMap()
   event_map.add(rx_event)
   event_map.add(tx_event)

   # Create CSR-accessible event monitor
   monitor = EventMonitor(event_map, trigger="level",
                          data_width=8)

API Reference
-------------

.. autoclass:: EventMonitor
   :members:
