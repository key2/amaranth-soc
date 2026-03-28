"""DMA Synchronizer plugin.

Synchronizes DMA start to an external signal (e.g. PPS for SDR applications).
"""

from amaranth import *
from amaranth.lib.wiring import Component, In, Out

from amaranth_stream import Signature as StreamSignature

from ..csr import reg as csr_reg, action as csr_action

from .common import dma_data_signature


__all__ = ["DMASynchronizer"]


class _EnableReg(csr_reg.Register, access="rw"):
    """Synchronizer enable register.

    Fields
    ------
    mode : 2-bit mode selection.
        - ``0b00``: Synchronization disabled.
        - ``0b01``: Reader and Writer to PPS synchronization enabled.
        - ``0b10``: PPS synchronization enabled.
        - ``0b11``: Reserved.
    """

    mode: csr_reg.Field(csr_action.RW, 2)


class _BypassReg(csr_reg.Register, access="rw"):
    """Synchronizer bypass register."""

    bypass: csr_reg.Field(csr_action.RW, 1)


class DMASynchronizer(Component):
    """DMA Synchronizer plugin.

    Synchronizes DMA data stream start to an external signal (e.g. PPS).
    Supports multiple synchronization modes.

    Parameters
    ----------
    data_width : :class:`int`
        Width of the data payload in bits.

    Attributes
    ----------
    sink : In stream
        Input data stream (from reader).
    source : Out stream
        Output data stream (to writer).
    next_source : Out stream
        Pass-through output (for plugin chain).
    next_sink : In stream
        Pass-through input (for plugin chain).
    pps : In(1)
        External synchronization signal.
    ready : In(1)
        External ready signal (default high).
    enable_reg : CSR register
        Synchronization mode control.
    bypass_reg : CSR register
        Bypass control.
    """

    def __init__(self, data_width):
        self._data_width = data_width
        data_sig = dma_data_signature(data_width)

        self.enable_reg = _EnableReg()
        self.bypass_reg = _BypassReg()

        super().__init__(
            {
                "sink": In(data_sig),
                "source": Out(data_sig),
                "next_source": Out(data_sig),
                "next_sink": In(data_sig),
                "pps": In(1),
                "ready": In(1, init=1),
            }
        )

    def elaborate(self, platform):
        m = Module()

        m.submodules.enable_reg = enable_reg = self.enable_reg
        m.submodules.bypass_reg = bypass_reg = self.bypass_reg

        mode = enable_reg.f.mode.data
        bypass = bypass_reg.f.bypass.data

        synced = Signal()

        # Synchronization logic
        with m.If(bypass):
            m.d.sync += synced.eq(1)
        with m.Elif(mode == 0b00):
            # Disabled
            m.d.sync += synced.eq(0)
        with m.Else():
            # On PPS and with external ready signal
            with m.If(self.ready & self.pps):
                # TX/RX synchronization: make sure TX has data
                with m.If((mode == 0b01) & self.sink.valid):
                    m.d.sync += synced.eq(1)
                # PPS-only synchronization
                with m.If(mode == 0b10):
                    m.d.sync += synced.eq(1)

        # Data path
        with m.If(synced):
            # Pass through: sink -> next_source, next_sink -> source
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
        with m.Else():
            # Block sink, ack next_sink
            m.d.comb += [
                self.next_source.valid.eq(0),
                self.sink.ready.eq(0),
                self.source.valid.eq(0),
                self.next_sink.ready.eq(1),
            ]

        return m
