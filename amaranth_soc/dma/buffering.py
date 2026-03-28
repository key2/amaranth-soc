"""DMA Buffering plugin.

Adds configurable-depth FIFOs with level monitoring to smooth out bus gaps
for fixed-rate user modules.
"""

from amaranth import *
from amaranth.lib.wiring import Component, In, Out
from amaranth.utils import ceil_log2

from amaranth_stream import Signature as StreamSignature, StreamFIFO

from ..csr import reg as csr_reg, action as csr_action

from .common import dma_data_signature
from ..utils.reset_inserter import add_reset_domain


__all__ = ["DMABuffering"]


class _FIFOControlReg(csr_reg.Register, access="rw"):
    """FIFO control register.

    Fields
    ------
    depth : 24-bit configurable FIFO depth.
    scratch : 4-bit software scratchpad.
    level_mode : 1-bit level reporting mode.
        - ``0``: Instantaneous level.
        - ``1``: Min (reader) or Max (writer) level since last clear.
    """

    def __init__(self, default_depth):
        super().__init__(
            {
                "depth": csr_reg.Field(csr_action.RW, 24, init=default_depth),
                "scratch": csr_reg.Field(csr_action.RW, 4),
                "level_mode": csr_reg.Field(csr_action.RW, 1),
            }
        )


class _FIFOStatusReg(csr_reg.Register, access="r"):
    """FIFO status register (read-only).

    Fields
    ------
    level : 24-bit FIFO level.
    """

    level: csr_reg.Field(csr_action.R, 24)


class DMABuffering(Component):
    """DMA Buffering plugin.

    Adds configurable-depth FIFOs for reader and/or writer paths with
    level monitoring.  Smooths out bus gaps for fixed-rate user modules.

    Parameters
    ----------
    data_width : :class:`int`
        Width of the data payload in bits.
    reader_depth : :class:`int`
        Reader FIFO depth in bytes (default 2048).
    writer_depth : :class:`int`
        Writer FIFO depth in bytes (default 2048).
    with_reader : :class:`bool`
        Enable reader FIFO (default True).
    with_writer : :class:`bool`
        Enable writer FIFO (default True).
    dynamic_depth : :class:`bool`
        Enable dynamic depth control via CSR (default True).

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
    reader_enable : In(1)
        Reader enable signal (resets FIFO when deasserted).
    writer_enable : In(1)
        Writer enable signal (resets FIFO when deasserted).
    """

    def __init__(
        self,
        data_width,
        reader_depth=2048,
        writer_depth=2048,
        with_reader=True,
        with_writer=True,
        dynamic_depth=True,
    ):
        self._data_width = data_width
        self._reader_depth = reader_depth
        self._writer_depth = writer_depth
        self._with_reader = with_reader
        self._with_writer = with_writer
        self._dynamic_depth = dynamic_depth

        data_sig = dma_data_signature(data_width)

        # CSR registers (created conditionally)
        if with_reader:
            self.reader_fifo_control = _FIFOControlReg(reader_depth)
            self.reader_fifo_status = _FIFOStatusReg()
        if with_writer:
            self.writer_fifo_control = _FIFOControlReg(writer_depth)
            self.writer_fifo_status = _FIFOStatusReg()

        super().__init__(
            {
                "sink": In(data_sig),
                "source": Out(data_sig),
                "next_source": Out(data_sig),
                "next_sink": In(data_sig),
                "reader_enable": In(1),
                "writer_enable": In(1),
            }
        )

    def elaborate(self, platform):
        m = Module()

        data_width = self._data_width
        data_sig = dma_data_signature(data_width)
        depth_shift = (data_width // 8 - 1).bit_length()

        # Reader FIFO
        if self._with_reader:
            m.submodules.reader_fifo_control = reader_ctrl = self.reader_fifo_control
            m.submodules.reader_fifo_status = reader_status = self.reader_fifo_status

            reader_fifo_words = self._reader_depth // (data_width // 8)
            reader_fifo = StreamFIFO(data_sig, reader_fifo_words, buffered=True)
            reader_fifo_reset = Signal()
            reader_rst_domain = add_reset_domain(
                m, reader_fifo_reset, name="_rst_reader"
            )
            m.submodules.reader_fifo = DomainRenamer({"sync": reader_rst_domain})(
                reader_fifo
            )

            m.d.comb += reader_fifo_reset.eq(~self.reader_enable)

            # Connect sink to reader FIFO (with optional dynamic depth control)
            m.d.comb += [
                reader_fifo.i_stream.payload.eq(self.sink.payload),
                reader_fifo.i_stream.first.eq(self.sink.first),
                reader_fifo.i_stream.last.eq(self.sink.last),
            ]
            if self._dynamic_depth:
                with m.If(reader_fifo.level < reader_ctrl.f.depth.data[depth_shift:]):
                    m.d.comb += [
                        reader_fifo.i_stream.valid.eq(self.sink.valid),
                        self.sink.ready.eq(reader_fifo.i_stream.ready),
                    ]
            else:
                m.d.comb += [
                    reader_fifo.i_stream.valid.eq(self.sink.valid),
                    self.sink.ready.eq(reader_fifo.i_stream.ready),
                ]

            # Connect reader FIFO to next_source
            m.d.comb += [
                self.next_source.payload.eq(reader_fifo.o_stream.payload),
                self.next_source.valid.eq(reader_fifo.o_stream.valid),
                self.next_source.first.eq(reader_fifo.o_stream.first),
                self.next_source.last.eq(reader_fifo.o_stream.last),
                reader_fifo.o_stream.ready.eq(self.next_source.ready),
            ]

            # Level tracking (min)
            reader_fifo_level_min = Signal(range(reader_fifo_words + 1))
            with m.If(reader_fifo.level < reader_fifo_level_min):
                m.d.sync += reader_fifo_level_min.eq(reader_fifo.level)

            # Clear on status read or instantaneous mode
            reader_level_clr = Signal()
            m.d.comb += reader_level_clr.eq(
                reader_status.f.level.port.r_stb | (reader_ctrl.f.level_mode.data == 0)
            )
            with m.If(reader_level_clr):
                m.d.sync += reader_fifo_level_min.eq(
                    (1 << len(reader_fifo_level_min)) - 1
                )

            # Report level
            with m.If(reader_ctrl.f.level_mode.data == 0):
                # Instantaneous
                m.d.comb += reader_status.f.level.r_data[depth_shift:].eq(
                    reader_fifo.level
                )
            with m.Else():
                # Min
                m.d.comb += reader_status.f.level.r_data[depth_shift:].eq(
                    reader_fifo_level_min
                )
        else:
            # No reader FIFO: pass through
            m.d.comb += [
                self.next_source.payload.eq(self.sink.payload),
                self.next_source.valid.eq(self.sink.valid),
                self.next_source.first.eq(self.sink.first),
                self.next_source.last.eq(self.sink.last),
                self.sink.ready.eq(self.next_source.ready),
            ]

        # Writer FIFO
        if self._with_writer:
            m.submodules.writer_fifo_control = writer_ctrl = self.writer_fifo_control
            m.submodules.writer_fifo_status = writer_status = self.writer_fifo_status

            writer_fifo_words = self._writer_depth // (data_width // 8)
            writer_fifo = StreamFIFO(data_sig, writer_fifo_words, buffered=True)
            writer_fifo_reset = Signal()
            writer_rst_domain = add_reset_domain(
                m, writer_fifo_reset, name="_rst_writer"
            )
            m.submodules.writer_fifo = DomainRenamer({"sync": writer_rst_domain})(
                writer_fifo
            )

            m.d.comb += writer_fifo_reset.eq(~self.writer_enable)

            # Connect next_sink to writer FIFO (with optional dynamic depth control)
            m.d.comb += [
                writer_fifo.i_stream.payload.eq(self.next_sink.payload),
                writer_fifo.i_stream.first.eq(self.next_sink.first),
                writer_fifo.i_stream.last.eq(self.next_sink.last),
            ]
            if self._dynamic_depth:
                with m.If(writer_fifo.level < writer_ctrl.f.depth.data[depth_shift:]):
                    m.d.comb += [
                        writer_fifo.i_stream.valid.eq(self.next_sink.valid),
                        self.next_sink.ready.eq(writer_fifo.i_stream.ready),
                    ]
            else:
                m.d.comb += [
                    writer_fifo.i_stream.valid.eq(self.next_sink.valid),
                    self.next_sink.ready.eq(writer_fifo.i_stream.ready),
                ]

            # Connect writer FIFO to source
            m.d.comb += [
                self.source.payload.eq(writer_fifo.o_stream.payload),
                self.source.valid.eq(writer_fifo.o_stream.valid),
                self.source.first.eq(writer_fifo.o_stream.first),
                self.source.last.eq(writer_fifo.o_stream.last),
                writer_fifo.o_stream.ready.eq(self.source.ready),
            ]

            # Level tracking (max)
            writer_fifo_level_max = Signal(range(writer_fifo_words + 1))
            with m.If(writer_fifo.level > writer_fifo_level_max):
                m.d.sync += writer_fifo_level_max.eq(writer_fifo.level)

            # Clear on status read or instantaneous mode
            writer_level_clr = Signal()
            m.d.comb += writer_level_clr.eq(
                writer_status.f.level.port.r_stb | (writer_ctrl.f.level_mode.data == 0)
            )
            with m.If(writer_level_clr):
                m.d.sync += writer_fifo_level_max.eq(0)

            # Report level
            with m.If(writer_ctrl.f.level_mode.data == 0):
                # Instantaneous
                m.d.comb += writer_status.f.level.r_data[depth_shift:].eq(
                    writer_fifo.level
                )
            with m.Else():
                # Max
                m.d.comb += writer_status.f.level.r_data[depth_shift:].eq(
                    writer_fifo_level_max
                )
        else:
            # No writer FIFO: pass through
            m.d.comb += [
                self.source.payload.eq(self.next_sink.payload),
                self.source.valid.eq(self.next_sink.valid),
                self.source.first.eq(self.next_sink.first),
                self.source.last.eq(self.next_sink.last),
                self.next_sink.ready.eq(self.source.ready),
            ]

        return m
