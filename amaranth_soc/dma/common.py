"""Common types and utilities for DMA subsystem."""

from amaranth import *
from amaranth.lib import data

__all__ = ["DMAStatus", "DMADescriptorLayout"]


class DMAStatus:
    """DMA channel status flags."""
    IDLE = 0
    RUNNING = 1
    DONE = 2
    ERROR = 3


def DMADescriptorLayout(addr_width=32):
    """Create a DMA descriptor layout.

    Fields
    ------
    src_addr : unsigned(addr_width)
        Source address.
    dst_addr : unsigned(addr_width)
        Destination address.
    length : unsigned(24)
        Transfer length in beats.
    control : unsigned(8)
        Control flags:
        - bit 0: last descriptor in chain
        - bit 1: generate IRQ on completion
    """
    return data.StructLayout({
        "src_addr": addr_width,
        "dst_addr": addr_width,
        "length": 24,
        "control": 8,
    })
