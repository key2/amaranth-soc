"""Common types and utilities for DMA subsystem.

Provides both bidirectional (memory-to-memory) descriptor layouts for the
AXI4-based DMA engines, and unidirectional descriptor layouts for the
bus-agnostic DMA controllers.
"""

from amaranth import *
from amaranth.lib import data
from amaranth.lib.data import StructLayout
from amaranth_stream import Signature as StreamSignature

__all__ = [
    "DMAStatus",
    "DMADescriptorLayout",
    "descriptor_layout",
    "split_descriptor_layout",
    "dma_data_signature",
]


class DMAStatus:
    """DMA channel status flags."""

    IDLE = 0
    RUNNING = 1
    DONE = 2
    ERROR = 3


def DMADescriptorLayout(addr_width=32):
    """Create a bidirectional DMA descriptor layout (memory-to-memory).

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
    return data.StructLayout(
        {
            "src_addr": addr_width,
            "dst_addr": addr_width,
            "length": 24,
            "control": 8,
        }
    )


def descriptor_layout(address_width=32):
    """Unidirectional DMA descriptor layout.

    Used by bus-agnostic DMA controllers where each descriptor targets
    a single address (either read or write, not both).

    Parameters
    ----------
    address_width : :class:`int`
        Width of the address field (default 32).

    Returns
    -------
    :class:`~amaranth.lib.data.StructLayout`
        Layout with fields:

        - ``address`` (*address_width*) -- target address.
        - ``length`` (24) -- transfer length in bytes.
        - ``irq_disable`` (1) -- disable IRQ on completion.
        - ``last_disable`` (1) -- disable ``last`` signal on completion.
    """
    return StructLayout(
        {
            "address": address_width,
            "length": 24,
            "irq_disable": 1,
            "last_disable": 1,
        }
    )


def split_descriptor_layout(address_width=32):
    """Split DMA descriptor layout (after splitting by max transfer size).

    Parameters
    ----------
    address_width : :class:`int`
        Width of the address field (default 32).

    Returns
    -------
    :class:`~amaranth.lib.data.StructLayout`
        Layout with fields:

        - ``address`` (*address_width*) -- target address.
        - ``length`` (24) -- transfer length in bytes.
        - ``irq_disable`` (1) -- disable IRQ.
        - ``last_disable`` (1) -- disable ``last`` signal.
        - ``user_id`` (8) -- packet identifier for tracking.
    """
    return StructLayout(
        {
            "address": address_width,
            "length": 24,
            "irq_disable": 1,
            "last_disable": 1,
            "user_id": 8,
        }
    )


def dma_data_signature(data_width):
    """DMA data stream signature.

    A simple data stream with first/last packet framing, suitable for
    bulk data transfers.

    Parameters
    ----------
    data_width : :class:`int`
        Width of the data payload in bits.

    Returns
    -------
    :class:`~amaranth_stream.Signature`
        Stream signature with ``has_first_last=True``.
    """
    return StreamSignature(data_width, has_first_last=True)
