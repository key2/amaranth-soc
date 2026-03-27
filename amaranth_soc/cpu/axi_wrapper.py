"""AXI CPU wrapper (not yet implemented).

This module will provide a wrapper for CPU cores that use an AXI4 or
AXI4-Lite bus interface for instruction fetch and data access.

Planned features:
- AXI4-Lite master interface for instruction bus (ibus)
- AXI4-Lite master interface for data bus (dbus)
- Interrupt vector input
- Integration with amaranth_soc.axi bus infrastructure
"""
