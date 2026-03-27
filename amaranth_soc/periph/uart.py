"""UART peripheral (not yet implemented).

This module will provide a CSR-accessible UART (Universal Asynchronous
Receiver-Transmitter) peripheral for use within the amaranth_soc.periph
framework.

Planned features:
- Configurable baud rate via CSR register
- TX and RX FIFOs with configurable depth
- Interrupt support (TX empty, RX available, RX overrun, framing error)
- 8N1, 7E1, and other common frame formats
- Hardware flow control (RTS/CTS) support
"""
