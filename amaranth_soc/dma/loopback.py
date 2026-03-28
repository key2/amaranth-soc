"""DMA Loopback plugin.

Connects DMA reader output to DMA writer input for testing.  When enabled,
user data streams are bypassed and the DMA loops back internally.
"""

from amaranth import *
from amaranth.lib.wiring import Component, In, Out

from amaranth_stream import Signature as StreamSignature

from ..csr import reg as csr_reg, action as csr_action

from .common import dma_data_signature


__all__ = ["DMALoopback"]


class _EnableReg(csr_reg.Register, access="rw"):
    """DMA Loopback enable register."""

    enable: csr_reg.Field(csr_action.RW, 1)


class DMALoopback(Component):
    """DMA Loopback plugin.

    When enabled, connects ``sink`` directly to ``source`` (reader->writer
    loopback).  When disabled, passes through to ``next_source``/``next_sink``
    for normal user data flow.

    Parameters
    ----------
    data_width : :class:`int`
        Width of the data payload in bits.

    Attributes
    ----------
    sink : In stream
        Input data stream (from DMA reader).
    source : Out stream
        Output data stream (to DMA writer).
    next_source : Out stream
        Pass-through output (to user, when loopback disabled).
    next_sink : In stream
        Pass-through input (from user, when loopback disabled).
    enable_reg : CSR register
        Loopback enable control.
    """

    def __init__(self, data_width):
        self._data_width = data_width
        data_sig = dma_data_signature(data_width)

        self.enable_reg = _EnableReg()

        super().__init__(
            {
                "sink": In(data_sig),
                "source": Out(data_sig),
                "next_source": Out(data_sig),
                "next_sink": In(data_sig),
            }
        )

    def elaborate(self, platform):
        m = Module()

        m.submodules.enable_reg = enable_reg = self.enable_reg
        enable = enable_reg.f.enable.data

        with m.If(enable):
            # Loopback: connect sink directly to source
            m.d.comb += [
                self.source.payload.eq(self.sink.payload),
                self.source.valid.eq(self.sink.valid),
                self.source.first.eq(self.sink.first),
                self.source.last.eq(self.sink.last),
                self.sink.ready.eq(self.source.ready),
                # Disconnect next ports
                self.next_source.valid.eq(0),
                self.next_sink.ready.eq(0),
            ]
        with m.Else():
            # Pass-through: sink -> next_source, next_sink -> source
            m.d.comb += [
                self.next_source.payload.eq(self.sink.payload),
                self.next_source.valid.eq(self.sink.valid),
                self.next_source.first.eq(self.sink.first),
                self.next_source.last.eq(self.sink.last),
                self.sink.ready.eq(self.next_source.ready),
                self.source.payload.eq(self.next_sink.payload),
                self.source.valid.eq(self.next_sink.valid),
                self.source.first.eq(self.next_sink.first),
                self.source.last.eq(self.next_sink.last),
                self.next_sink.ready.eq(self.source.ready),
            ]

        return m
