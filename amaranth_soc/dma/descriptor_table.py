"""DMA Scatter-Gather descriptor table.

A software-programmable descriptor FIFO with two operating modes:

- **Prog mode** (``loop_prog_n=0``): Software fills descriptors via CSR
  writes; each descriptor is consumed once.
- **Loop mode** (``loop_prog_n=1``): Consumed descriptors are automatically
  refilled into the table for continuous circular-buffer operation.
"""

from amaranth import *
from amaranth.lib.wiring import Component, In, Out, connect, flipped
from amaranth.utils import ceil_log2

from amaranth_stream import Signature as StreamSignature, StreamFIFO

from ..csr import reg as csr_reg, action as csr_action
from ..csr.bus import Element

from .common import descriptor_layout
from ..utils.reset_inserter import add_reset_domain


__all__ = ["DMADescriptorTable"]


class _DescValueReg(csr_reg.Register, access="rw"):
    """64-bit descriptor value register.

    Fields
    ------
    address_lsb : 32-bit LSB of the descriptor address.
    length : 24-bit transfer length in bytes.
    irq_disable : 1-bit IRQ disable control.
    last_disable : 1-bit last-signal disable control.
    """

    address_lsb: csr_reg.Field(csr_action.RW, 32)
    length: csr_reg.Field(csr_action.RW, 24)
    irq_disable: csr_reg.Field(csr_action.RW, 1)
    last_disable: csr_reg.Field(csr_action.RW, 1)


class _DescWeReg(csr_reg.Register, access="rw"):
    """Write-enable / MSB address register.

    Writing to this register triggers a descriptor write into the table.

    Fields
    ------
    address_msb : 32-bit MSB of the descriptor address (for 64-bit mode).
    """

    address_msb: csr_reg.Field(csr_action.RW, 32)


class _LoopProgNReg(csr_reg.Register, access="rw"):
    """Mode selection register.

    ``0``: Prog mode -- ``1``: Loop mode.
    """

    loop_prog_n: csr_reg.Field(csr_action.RW, 1)


class _LoopStatusReg(csr_reg.Register, access="r"):
    """Loop status register (read-only).

    Fields
    ------
    index : 16-bit index of the last descriptor executed.
    count : 16-bit loop count since start.
    """

    index: csr_reg.Field(csr_action.R, 16)
    count: csr_reg.Field(csr_action.R, 16)


class _LevelReg(csr_reg.Register, access="r"):
    """FIFO level register (read-only)."""

    def __init__(self, depth):
        super().__init__({"level": csr_reg.Field(csr_action.R, ceil_log2(depth + 1))})


class _ResetReg(csr_reg.Register, access="rw"):
    """Table reset register.  Writing triggers a table reset."""

    reset: csr_reg.Field(csr_action.RW, 1)


class DMADescriptorTable(Component):
    """DMA Scatter-Gather descriptor table.

    A software-programmable descriptor FIFO with prog/loop modes.

    Parameters
    ----------
    depth : :class:`int`
        Number of descriptor entries in the table.
    address_width : :class:`int`
        Width of the address field (32 or 64).

    Attributes
    ----------
    source : Out stream
        Output stream of descriptors.
    value : CSR register
        64-bit descriptor data to program.
    we : CSR register
        Write-enable / MSB address.
    loop_prog_n : CSR register
        Mode selection (0=prog, 1=loop).
    loop_status : CSR register
        Loop index/count status.
    level : CSR register
        FIFO fill level.
    reset : CSR register
        Table reset control.
    """

    def __init__(self, depth=256, address_width=32):
        assert address_width in (32, 64)
        self._depth = depth
        self._address_width = address_width

        # Descriptor stream signature (with first/last for framing)
        desc_layout = descriptor_layout(address_width=address_width)
        self._stream_sig = StreamSignature(desc_layout, has_first_last=True)

        # CSR registers
        self.value = _DescValueReg()
        self.we = _DescWeReg()
        self.loop_prog_n = _LoopProgNReg()
        self.loop_status = _LoopStatusReg()
        self.level = _LevelReg(depth)
        self.reset_reg = _ResetReg()

        super().__init__(
            {
                "source": Out(self._stream_sig),
            }
        )

    def elaborate(self, platform):
        m = Module()

        depth = self._depth
        address_width = self._address_width

        # CSR submodules
        m.submodules.value = value = self.value
        m.submodules.we = we = self.we
        m.submodules.loop_prog_n = loop_prog_n = self.loop_prog_n
        m.submodules.loop_status = loop_status = self.loop_status
        m.submodules.level = level_reg = self.level
        m.submodules.reset_reg = reset_reg = self.reset_reg

        # Table (FIFO) with reset domain
        table = StreamFIFO(self._stream_sig, depth, buffered=True)
        table_reset = Signal()
        rst_domain = add_reset_domain(m, table_reset)
        m.submodules.table = DomainRenamer({"sync": rst_domain})(table)

        # Reset logic: pulse on CSR write
        m.d.comb += table_reset.eq(
            reset_reg.f.reset.data & reset_reg.f.reset.port.w_stb
        )

        # Level output
        m.d.comb += level_reg.f.level.r_data.eq(table.level)

        # Mode signals
        prog_mode = Signal()
        loop_mode = Signal()
        m.d.comb += [
            prog_mode.eq(loop_prog_n.f.loop_prog_n.data == 0),
            loop_mode.eq(loop_prog_n.f.loop_prog_n.data == 1),
        ]

        # Table write logic
        # We detect a write to the 'we' register by checking w_stb on address_msb
        we_pulse = Signal()
        m.d.comb += we_pulse.eq(we.f.address_msb.port.w_stb)

        with m.If(prog_mode):
            # In Prog mode, fill table from CSR writes
            m.d.sync += [
                table.i_stream.payload.address[:32].eq(value.f.address_lsb.data),
                table.i_stream.payload.length.eq(value.f.length.data),
                table.i_stream.payload.irq_disable.eq(value.f.irq_disable.data),
                table.i_stream.payload.last_disable.eq(value.f.last_disable.data),
                table.i_stream.first.eq(table.level == 0),
                table.i_stream.valid.eq(we_pulse),
            ]
            if address_width == 64:
                m.d.sync += table.i_stream.payload.address[32:64].eq(
                    we.f.address_msb.data
                )
        with m.Else():
            # In Loop mode, refill from output back to input
            m.d.sync += [
                table.i_stream.payload.eq(table.o_stream.payload),
                table.i_stream.first.eq(table.o_stream.first),
                table.i_stream.last.eq(table.o_stream.last),
                table.i_stream.valid.eq(table.o_stream.valid & table.o_stream.ready),
            ]

        # Table read logic: connect table output to source
        m.d.comb += [
            self.source.payload.eq(table.o_stream.payload),
            self.source.valid.eq(table.o_stream.valid),
            self.source.first.eq(table.o_stream.first),
            self.source.last.eq(table.o_stream.last),
            table.o_stream.ready.eq(self.source.ready),
        ]

        # Loop status tracking
        loop_first = Signal(init=1)
        loop_index = Signal(16)
        loop_count = Signal(16)

        m.d.comb += [
            loop_status.f.index.r_data.eq(loop_index),
            loop_status.f.count.r_data.eq(loop_count),
        ]

        with m.If(table_reset):
            m.d.sync += [
                loop_first.eq(1),
                loop_index.eq(0),
                loop_count.eq(0),
            ]
        with m.Elif(table.o_stream.valid & table.o_stream.ready):
            with m.If(loop_mode & table.o_stream.first):
                # Reset index on loop wrap
                m.d.sync += loop_index.eq(0)
                # Increment count (except on very first)
                m.d.sync += loop_first.eq(0)
                m.d.sync += loop_count.eq(loop_count + ~loop_first)
            with m.Else():
                # Increment index
                m.d.sync += loop_index.eq(loop_index + 1)
                # Increment count on index overflow
                with m.If(loop_index == 0xFFFF):
                    m.d.sync += loop_count.eq(loop_count + 1)

        return m
