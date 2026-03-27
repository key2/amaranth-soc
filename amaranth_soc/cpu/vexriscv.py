"""VexRiscv CPU integration (not yet implemented).

This module will provide a wrapper for the VexRiscv RISC-V soft-core
processor, allowing it to be integrated into amaranth-soc designs.

VexRiscv is a configurable RISC-V CPU written in SpinalHDL. Integration
requires importing the generated Verilog netlist and wrapping it with
an Amaranth-compatible bus interface.

Planned features:
- VexRiscv Verilog netlist instantiation
- Wishbone or AXI4-Lite bus interface adaptation
- Interrupt controller integration
- Debug interface support (JTAG)
"""
