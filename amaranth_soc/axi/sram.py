from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In
from amaranth.lib.memory import MemoryData, Memory
from amaranth.utils import exact_log2

from amaranth_soc.memory import MemoryMap

from .bus import AXI4LiteSignature, AXIResp


__all__ = ["AXI4LiteSRAM"]


class AXI4LiteSRAM(wiring.Component):
    """SRAM with AXI4-Lite interface.

    AXI4-Lite bus accesses have a latency of one clock cycle.

    Parameters
    ----------
    size : :class:`int`, power of two
        SRAM size in bytes.
    data_width : ``32`` or ``64``
        AXI4-Lite bus data width.
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
        If ``data_width`` is not 32 or 64.
    """
    def __init__(self, *, size, data_width=32, writable=True, init=()):
        if not isinstance(size, int) or size <= 0 or size & (size - 1):
            raise TypeError(f"Size must be an integer power of two, not {size!r}")
        if data_width not in (32, 64):
            raise ValueError(f"Data width must be 32 or 64, not {data_width!r}")

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
