from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In
from amaranth.lib.memory import MemoryData, Memory
from amaranth.utils import exact_log2

from amaranth_soc.memory import MemoryMap

from .bus import AXI4LiteSignature, AXI4Signature, AXIResp
from .burst import AXIBurst2Beat


__all__ = ["AXI4LiteSRAM", "AXI4SRAM"]


class AXI4LiteSRAM(wiring.Component):
    """SRAM with AXI4-Lite interface.

    AXI4-Lite bus accesses have a latency of one clock cycle.

    Parameters
    ----------
    size : :class:`int`, power of two
        SRAM size in bytes.
    data_width : int, power of 2, >= 32
        AXI4-Lite bus data width. Must be a power of 2 and at least 32.
    writable : bool
        Write capability. If disabled, writes are ignored. Enabled by default.
    init : iterable of initial values, optional
        Initial values for memory rows. There are ``size // (data_width // 8)`` rows,
        and each row has a shape of ``unsigned(data_width)``.

    Members
    -------
    bus : ``In(AXI4LiteSignature(...))``
        AXI4-Lite bus interface.

    Raises
    ------
    :exc:`TypeError`
        If ``size`` is not a positive power of two.
    :exc:`ValueError`
        If ``data_width`` is not a power of 2 >= 32.
    """
    def __init__(self, *, size, data_width=32, writable=True, init=()):
        if not isinstance(size, int) or size <= 0 or size & (size - 1):
            raise TypeError(f"Size must be an integer power of two, not {size!r}")
        if not isinstance(data_width, int) or data_width < 32:
            raise ValueError(f"Data width must be a positive integer >= 32, not {data_width!r}")
        if data_width & (data_width - 1) != 0:
            raise ValueError(f"Data width must be a power of 2, not {data_width!r}")

        self._size     = size
        self._writable = bool(writable)

        # Number of bytes per word
        bytes_per_word = data_width // 8
        depth = size // bytes_per_word

        if depth < 1:
            raise ValueError(f"Size {size} is too small for data width {data_width}")

        self._mem_data = MemoryData(depth=depth, shape=unsigned(data_width), init=init)
        self._mem      = Memory(self._mem_data)

        # AXI4-Lite uses byte addresses. The addr_width must cover the full byte
        # address space of the SRAM.
        addr_width = exact_log2(size)

        super().__init__({"bus": In(AXI4LiteSignature(addr_width=addr_width,
                                                      data_width=data_width))})

        # Memory map uses byte addressing (data_width=8)
        self.bus.memory_map = MemoryMap(addr_width=addr_width, data_width=8)
        self.bus.memory_map.add_resource(self._mem, name=("mem",), size=size)
        self.bus.memory_map.freeze()

    @property
    def size(self):
        return self._size

    @property
    def writable(self):
        return self._writable

    @property
    def init(self):
        return self._mem_data.init

    @init.setter
    def init(self, init):
        self._mem_data.init = init

    def elaborate(self, platform):
        m = Module()
        m.submodules.mem = self._mem

        bus = self.bus
        bytes_per_word = bus.data_width // 8
        word_addr_shift = exact_log2(bytes_per_word)

        # Memory ports
        read_port = self._mem.read_port()
        m.d.comb += read_port.addr.eq(bus.araddr[word_addr_shift:])

        if self.writable:
            write_port = self._mem.write_port(granularity=8)
            m.d.comb += [
                write_port.addr.eq(bus.awaddr[word_addr_shift:]),
                write_port.data.eq(bus.wdata),
            ]

        # Registered address for read (we latch araddr when we accept AR)
        read_addr = Signal(bus.addr_width)

        with m.FSM(name="fsm"):
            with m.State("IDLE"):
                # Accept write address + write data simultaneously
                m.d.comb += bus.awready.eq(1)
                m.d.comb += bus.wready.eq(1)
                # Accept read address
                m.d.comb += bus.arready.eq(1)

                # Writes take priority (AW+W valid simultaneously)
                with m.If(bus.awvalid & bus.wvalid):
                    if self.writable:
                        m.d.comb += write_port.en.eq(bus.wstrb)
                    m.next = "WRITE_RESP"
                with m.Elif(bus.arvalid):
                    m.d.comb += read_port.en.eq(1)
                    m.d.sync += read_addr.eq(bus.araddr)
                    m.next = "READ"

            with m.State("READ"):
                m.d.comb += [
                    bus.rvalid.eq(1),
                    bus.rdata.eq(read_port.data),
                    bus.rresp.eq(AXIResp.OKAY),
                ]
                with m.If(bus.rready):
                    m.next = "IDLE"

            with m.State("WRITE_RESP"):
                m.d.comb += [
                    bus.bvalid.eq(1),
                    bus.bresp.eq(AXIResp.OKAY),
                ]
                with m.If(bus.bready):
                    m.next = "IDLE"

        return m


class AXI4SRAM(wiring.Component):
    """AXI4 Full SRAM with native burst support.

    Handles INCR, WRAP, and FIXED burst types natively using
    AXIBurst2Beat for address generation.

    Parameters
    ----------
    size : int
        Memory size in bytes.
    data_width : int, power of 2, >= 8
        Data width in bits.
    id_width : int
        ID signal width (default 0).
    granularity : int
        Byte granularity for write strobes (default 8).

    Members
    -------
    bus : ``In(AXI4Signature(...))``
        AXI4 bus interface.

    Raises
    ------
    :exc:`ValueError`
        If ``size`` is not positive.
    :exc:`ValueError`
        If ``data_width`` is not a power of 2 >= 8.
    """

    def __init__(self, *, size, data_width=32, id_width=0, granularity=8):
        if not isinstance(size, int) or size <= 0:
            raise ValueError(f"Size must be a positive integer, not {size!r}")
        if not isinstance(data_width, int) or data_width < 8:
            raise ValueError(f"Data width must be an integer >= 8, not {data_width!r}")
        if data_width & (data_width - 1) != 0:
            raise ValueError(f"Data width must be a power of 2, not {data_width!r}")

        self._size       = size
        self._data_width = data_width
        self._id_width   = id_width
        self._granularity = granularity

        bytes_per_word = data_width // 8
        depth = (size * granularity) // data_width

        if depth < 1:
            raise ValueError(f"Size {size} is too small for data width {data_width}")

        # Calculate addr_width: enough bits to address all bytes
        addr_width = (size - 1).bit_length()
        if addr_width < 1:
            addr_width = 1

        self._addr_width = addr_width
        self._depth = depth

        self._mem_data = MemoryData(depth=depth, shape=unsigned(data_width), init=[])
        self._mem      = Memory(self._mem_data)

        super().__init__({"bus": In(AXI4Signature(addr_width=addr_width,
                                                   data_width=data_width,
                                                   id_width=id_width))})

        # Memory map uses byte addressing (data_width=8)
        self.bus.memory_map = MemoryMap(addr_width=addr_width, data_width=8)
        self.bus.memory_map.add_resource(self._mem, name=("mem",), size=size)
        self.bus.memory_map.freeze()

    @property
    def size(self):
        return self._size

    @property
    def data_width(self):
        return self._data_width

    @property
    def id_width(self):
        return self._id_width

    def elaborate(self, platform):
        m = Module()
        m.submodules.mem = self._mem

        bus = self.bus
        data_width = self._data_width
        bytes_per_word = data_width // 8
        word_addr_shift = exact_log2(bytes_per_word)

        # Memory ports
        read_port  = self._mem.read_port()
        write_port = self._mem.write_port(granularity=8)

        # Burst-to-beat converters
        m.submodules.wr_b2b = wr_b2b = AXIBurst2Beat(
            addr_width=self._addr_width, data_width=data_width)
        m.submodules.rd_b2b = rd_b2b = AXIBurst2Beat(
            addr_width=self._addr_width, data_width=data_width)

        # --- Write path ---
        wr_id = Signal(max(1, self._id_width), name="wr_id")

        # Default: no handshake, no burst2beat pulses
        m.d.comb += [
            bus.awready.eq(0),
            bus.wready.eq(0),
            bus.bvalid.eq(0),
            bus.bresp.eq(AXIResp.OKAY),
            wr_b2b.first.eq(0),
            wr_b2b.next.eq(0),
            write_port.en.eq(0),
        ]
        if self._id_width > 0:
            m.d.comb += bus.bid.eq(wr_id)

        with m.FSM(name="wr_fsm"):
            with m.State("WR_IDLE"):
                with m.If(bus.awvalid):
                    m.d.comb += bus.awready.eq(1)
                    if self._id_width > 0:
                        m.d.sync += wr_id.eq(bus.awid)
                    # Load burst2beat with burst parameters
                    m.d.comb += [
                        wr_b2b.addr.eq(bus.awaddr),
                        wr_b2b.len.eq(bus.awlen),
                        wr_b2b.size.eq(bus.awsize),
                        wr_b2b.burst.eq(bus.awburst),
                        wr_b2b.first.eq(1),
                    ]
                    m.next = "WR_DATA"

            with m.State("WR_DATA"):
                # Accept W beats and write to memory using burst2beat address
                m.d.comb += [
                    write_port.addr.eq(wr_b2b.next_addr[word_addr_shift:]),
                    write_port.data.eq(bus.wdata),
                ]
                with m.If(bus.wvalid):
                    m.d.comb += [
                        bus.wready.eq(1),
                        write_port.en.eq(bus.wstrb),
                    ]
                    with m.If(bus.wlast):
                        m.next = "WR_RESP"
                    with m.Else():
                        # Advance burst2beat to next address
                        m.d.comb += wr_b2b.next.eq(1)

            with m.State("WR_RESP"):
                m.d.comb += [
                    bus.bvalid.eq(1),
                    bus.bresp.eq(AXIResp.OKAY),
                ]
                with m.If(bus.bready):
                    m.next = "WR_IDLE"

        # --- Read path ---
        rd_id      = Signal(max(1, self._id_width), name="rd_id")
        rd_len     = Signal(8, name="rd_len")
        rd_beat    = Signal(8, name="rd_beat")
        rd_data    = Signal(data_width, name="rd_data")

        m.d.comb += [
            bus.arready.eq(0),
            bus.rvalid.eq(0),
            bus.rdata.eq(0),
            bus.rresp.eq(AXIResp.OKAY),
            bus.rlast.eq(0),
            rd_b2b.first.eq(0),
            rd_b2b.next.eq(0),
            read_port.en.eq(0),
        ]
        if self._id_width > 0:
            m.d.comb += bus.rid.eq(rd_id)

        # Connect read port address from burst2beat
        m.d.comb += read_port.addr.eq(rd_b2b.next_addr[word_addr_shift:])

        with m.FSM(name="rd_fsm"):
            with m.State("RD_IDLE"):
                with m.If(bus.arvalid):
                    m.d.comb += bus.arready.eq(1)
                    if self._id_width > 0:
                        m.d.sync += rd_id.eq(bus.arid)
                    m.d.sync += [
                        rd_len.eq(bus.arlen),
                        rd_beat.eq(0),
                    ]
                    # Load burst2beat
                    m.d.comb += [
                        rd_b2b.addr.eq(bus.araddr),
                        rd_b2b.len.eq(bus.arlen),
                        rd_b2b.size.eq(bus.arsize),
                        rd_b2b.burst.eq(bus.arburst),
                        rd_b2b.first.eq(1),
                    ]
                    m.next = "RD_MEM"

            with m.State("RD_MEM"):
                # Memory read is synchronous - issue read enable, data available next cycle
                m.d.comb += read_port.en.eq(1)
                m.next = "RD_DATA"

            with m.State("RD_DATA"):
                # Data is now available from memory read port
                m.d.comb += [
                    bus.rvalid.eq(1),
                    bus.rdata.eq(read_port.data),
                    bus.rresp.eq(AXIResp.OKAY),
                    bus.rlast.eq(rd_beat == rd_len),
                ]
                if self._id_width > 0:
                    m.d.comb += bus.rid.eq(rd_id)
                with m.If(bus.rready):
                    with m.If(rd_beat == rd_len):
                        # Last beat
                        m.next = "RD_IDLE"
                    with m.Else():
                        # Advance to next beat
                        m.d.comb += rd_b2b.next.eq(1)
                        m.d.sync += rd_beat.eq(rd_beat + 1)
                        m.next = "RD_MEM"

        return m
