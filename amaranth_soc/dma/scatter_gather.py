"""Scatter-Gather DMA controller.

Manages a table of DMA descriptors and executes them sequentially,
piping data from a DMAReader to a DMAWriter for each descriptor.
"""

from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out

from ..axi.bus import AXI4Signature
from .reader import DMAReader
from .writer import DMAWriter

__all__ = ["ScatterGatherDMA"]


class ScatterGatherDMA(wiring.Component):
    """Scatter-Gather DMA controller.

    Manages a table of DMA descriptors, executing them sequentially.
    Each descriptor specifies a source address, destination address,
    and transfer length.

    Parameters
    ----------
    addr_width : int
        Address width for AXI4 buses.
    data_width : int
        Data width for AXI4 buses (must be power of 2, >= 8).
    max_descriptors : int
        Maximum number of descriptors in the table (default 16).
    max_burst_len : int
        Maximum AXI burst length per descriptor (default 16).

    Members
    -------
    read_bus : ``Out(AXI4Signature(...))``
        AXI4 master port for reads.
    write_bus : ``Out(AXI4Signature(...))``
        AXI4 master port for writes.
    start : ``In(1)``
        Pulse to start executing descriptors from index 0.
    abort : ``In(1)``
        Pulse to abort the current transfer and return to IDLE.
    busy : ``Out(1)``
        High while descriptors are being executed.
    done : ``Out(1)``
        Pulsed high for one cycle when all descriptors complete.
    irq : ``Out(1)``
        Pulsed high when a descriptor with IRQ flag completes.
    current_desc : ``Out(range(max_descriptors))``
        Index of the descriptor currently being executed.
    num_descriptors : ``In(range(max_descriptors + 1))``
        Number of valid descriptors loaded (set before *start*).
    desc_src_addr : ``In(addr_width)``
        Source address for descriptor write port.
    desc_dst_addr : ``In(addr_width)``
        Destination address for descriptor write port.
    desc_length : ``In(24)``
        Transfer length for descriptor write port.
    desc_control : ``In(8)``
        Control flags for descriptor write port.
    desc_index : ``In(range(max_descriptors))``
        Index to write the descriptor to.
    desc_we : ``In(1)``
        Write-enable for the descriptor table.
    """

    def __init__(self, *, addr_width=32, data_width=32,
                 max_descriptors=16, max_burst_len=16):
        if not isinstance(addr_width, int) or addr_width < 1:
            raise TypeError(
                f"Address width must be a positive integer, not {addr_width!r}")
        if not isinstance(data_width, int) or data_width < 8:
            raise ValueError(
                f"Data width must be an integer >= 8, not {data_width!r}")
        if data_width & (data_width - 1) != 0:
            raise ValueError(
                f"Data width must be a power of 2, not {data_width!r}")
        if not isinstance(max_descriptors, int) or max_descriptors < 1:
            raise ValueError(
                f"max_descriptors must be >= 1, not {max_descriptors!r}")
        if not isinstance(max_burst_len, int) or not (1 <= max_burst_len <= 256):
            raise ValueError(
                f"max_burst_len must be 1..256, not {max_burst_len!r}")

        self._addr_width = addr_width
        self._data_width = data_width
        self._max_descriptors = max_descriptors
        self._max_burst_len = max_burst_len

        super().__init__({
            # AXI4 master ports
            "read_bus":  Out(AXI4Signature(addr_width=addr_width,
                                           data_width=data_width)),
            "write_bus": Out(AXI4Signature(addr_width=addr_width,
                                           data_width=data_width)),
            # Control
            "start":     In(1),
            "abort":     In(1),
            # Status
            "busy":         Out(1),
            "done":         Out(1),
            "irq":          Out(1),
            "current_desc": Out(range(max_descriptors)),
            # Descriptor table write port
            "num_descriptors": In(range(max_descriptors + 1)),
            "desc_src_addr":   In(addr_width),
            "desc_dst_addr":   In(addr_width),
            "desc_length":     In(24),
            "desc_control":    In(8),
            "desc_index":      In(range(max_descriptors)),
            "desc_we":         In(1),
        })

    @property
    def addr_width(self):
        return self._addr_width

    @property
    def data_width(self):
        return self._data_width

    @property
    def max_descriptors(self):
        return self._max_descriptors

    @property
    def max_burst_len(self):
        return self._max_burst_len

    def elaborate(self, platform):
        m = Module()

        addr_width = self._addr_width
        data_width = self._data_width
        max_desc = self._max_descriptors

        # --- Descriptor table (register-based) ---
        desc_src_addrs = Array([Signal(addr_width, name=f"desc_src_{i}")
                                for i in range(max_desc)])
        desc_dst_addrs = Array([Signal(addr_width, name=f"desc_dst_{i}")
                                for i in range(max_desc)])
        desc_lengths = Array([Signal(24, name=f"desc_len_{i}")
                              for i in range(max_desc)])
        desc_controls = Array([Signal(8, name=f"desc_ctl_{i}")
                               for i in range(max_desc)])

        # Descriptor write port
        with m.If(self.desc_we):
            m.d.sync += [
                desc_src_addrs[self.desc_index].eq(self.desc_src_addr),
                desc_dst_addrs[self.desc_index].eq(self.desc_dst_addr),
                desc_lengths[self.desc_index].eq(self.desc_length),
                desc_controls[self.desc_index].eq(self.desc_control),
            ]

        # --- DMA Reader and Writer sub-modules ---
        reader = DMAReader(
            addr_width=addr_width, data_width=data_width,
            max_burst_len=self._max_burst_len)
        writer = DMAWriter(
            addr_width=addr_width, data_width=data_width,
            max_burst_len=self._max_burst_len)
        m.submodules.reader = reader
        m.submodules.writer = writer

        # --- Wire reader.bus <-> self.read_bus ---
        # Reader is a master (Out), self.read_bus is also Out from our perspective.
        # The reader drives AR and R-ready; the SRAM responds with R data.
        # We forward all reader bus outputs to our read_bus outputs,
        # and all read_bus inputs back to reader bus inputs.
        self._wire_axi4_bus(m, reader.bus, self.read_bus)

        # --- Wire writer.bus <-> self.write_bus ---
        self._wire_axi4_bus(m, writer.bus, self.write_bus)

        # --- Pipe reader output to writer input ---
        m.d.comb += [
            writer.data_in.eq(reader.data_out),
            writer.data_valid.eq(reader.data_valid),
            reader.data_ready.eq(writer.data_ready),
        ]

        # --- Descriptor execution FSM ---
        desc_idx = Signal(range(max_desc))
        num_desc = Signal(range(max_desc + 1))

        # Current descriptor fields (latched)
        cur_src = Signal(addr_width)
        cur_dst = Signal(addr_width)
        cur_len = Signal(24)
        cur_ctl = Signal(8)

        m.d.comb += self.current_desc.eq(desc_idx)

        with m.FSM():
            with m.State("IDLE"):
                m.d.comb += [
                    self.busy.eq(0),
                    self.done.eq(0),
                    self.irq.eq(0),
                ]
                with m.If(self.start):
                    m.d.sync += [
                        desc_idx.eq(0),
                        num_desc.eq(self.num_descriptors),
                    ]
                    m.next = "LOAD_DESC"

            with m.State("LOAD_DESC"):
                m.d.comb += self.busy.eq(1)
                # Latch current descriptor
                m.d.sync += [
                    cur_src.eq(desc_src_addrs[desc_idx]),
                    cur_dst.eq(desc_dst_addrs[desc_idx]),
                    cur_len.eq(desc_lengths[desc_idx]),
                    cur_ctl.eq(desc_controls[desc_idx]),
                ]
                m.next = "START_XFER"

            with m.State("START_XFER"):
                m.d.comb += self.busy.eq(1)
                # Configure and start reader + writer simultaneously
                m.d.comb += [
                    reader.src_addr.eq(cur_src),
                    reader.length.eq(cur_len),
                    reader.start.eq(1),
                    writer.dst_addr.eq(cur_dst),
                    writer.length.eq(cur_len),
                    writer.start.eq(1),
                ]
                m.next = "WAIT_XFER"

            with m.State("WAIT_XFER"):
                m.d.comb += self.busy.eq(1)
                # Use ~busy instead of done, since done is a single-cycle pulse
                # and the reader may finish before the writer.
                # Both engines return to IDLE (busy=0) after their done pulse.
                with m.If(self.abort):
                    m.next = "IDLE"
                with m.Elif(~reader.busy & ~writer.busy):
                    m.next = "DESC_DONE"

            with m.State("DESC_DONE"):
                m.d.comb += self.busy.eq(1)
                # Check IRQ flag (bit 1 of control)
                m.d.comb += self.irq.eq(cur_ctl[1])

                # Check if last descriptor (bit 0) or end of table
                is_last = Signal()
                m.d.comb += is_last.eq(
                    cur_ctl[0] | (desc_idx == (num_desc - 1)))

                with m.If(is_last):
                    m.next = "ALL_DONE"
                with m.Else():
                    m.d.sync += desc_idx.eq(desc_idx + 1)
                    m.next = "LOAD_DESC"

            with m.State("ALL_DONE"):
                m.d.comb += [
                    self.done.eq(1),
                    self.busy.eq(0),
                ]
                m.next = "IDLE"

        return m

    @staticmethod
    def _wire_axi4_bus(m, inner_bus, outer_bus):
        """Wire an inner AXI4 bus (submodule) to an outer AXI4 bus (component port).

        Both buses have the same Out-oriented signature. Signals that are
        Out in the signature (driven by master) are forwarded from inner to outer.
        Signals that are In in the signature (driven by slave) are forwarded
        from outer to inner.
        """
        # AXI4 Out (master-driven) signals
        out_signals = [
            "awaddr", "awprot", "awvalid", "awlen", "awsize", "awburst",
            "awlock", "awcache", "awqos", "awregion",
            "wdata", "wstrb", "wvalid", "wlast",
            "bready",
            "araddr", "arprot", "arvalid", "arlen", "arsize", "arburst",
            "arlock", "arcache", "arqos", "arregion",
            "rready",
        ]
        # AXI4 In (slave-driven) signals
        in_signals = [
            "awready",
            "wready",
            "bresp", "bvalid",
            "arready",
            "rdata", "rresp", "rvalid", "rlast",
        ]

        for name in out_signals:
            if hasattr(inner_bus, name) and hasattr(outer_bus, name):
                m.d.comb += getattr(outer_bus, name).eq(getattr(inner_bus, name))

        for name in in_signals:
            if hasattr(inner_bus, name) and hasattr(outer_bus, name):
                m.d.comb += getattr(inner_bus, name).eq(getattr(outer_bus, name))
