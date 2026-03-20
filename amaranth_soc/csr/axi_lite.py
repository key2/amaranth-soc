from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, flipped
from amaranth.utils import exact_log2

from amaranth_soc.csr.bus import Interface as CSRInterface
from amaranth_soc.memory import MemoryMap

from ..axi.bus import AXI4LiteSignature, AXIResp


__all__ = ["AXI4LiteCSRBridge"]


class AXI4LiteCSRBridge(wiring.Component):
    """AXI4-Lite to CSR bus bridge.

    A bus bridge for accessing CSR registers from AXI4-Lite. This bridge supports any AXI4-Lite
    data width greater or equal to CSR data width and performs appropriate address translation.

    Latency
    -------

    Reads and writes take ``data_width // csr_bus.data_width + 1`` cycles to complete.
    Write side effects occur simultaneously with the write response.

    Parameters
    ----------
    csr_bus : :class:`amaranth_soc.csr.Interface`
        CSR bus driven by the bridge.
    data_width : int
        AXI4-Lite bus data width. Optional. If ``None``, defaults to ``csr_bus.data_width``.
    name : :class:`..memory.MemoryMap.Name`
        Window name. Optional.

    Attributes
    ----------
    axi_bus : :class:`..axi.bus.AXI4LiteInterface`
        AXI4-Lite bus provided by the bridge.
    """
    def __init__(self, csr_bus, *, data_width=None, name=None):
        if isinstance(csr_bus, wiring.FlippedInterface):
            csr_bus_unflipped = flipped(csr_bus)
        else:
            csr_bus_unflipped = csr_bus
        if not isinstance(csr_bus_unflipped, CSRInterface):
            raise TypeError(f"CSR bus must be an instance of csr.Interface, not "
                            f"{csr_bus_unflipped!r}")
        if csr_bus.data_width not in (8, 16, 32, 64):
            raise ValueError(f"CSR bus data width must be one of 8, 16, 32, 64, not "
                             f"{csr_bus.data_width!r}")
        if data_width is None:
            data_width = csr_bus.data_width

        # Number of CSR beats per AXI transaction
        ratio = data_width // csr_bus.data_width

        # AXI4-Lite uses byte addressing. The CSR bus uses word addressing with
        # data_width-sized words. We need to compute the AXI address width.
        # The CSR address space has 2^csr_addr_width words of csr_data_width bits each.
        # When accessed through AXI with data_width bits, each AXI word covers `ratio`
        # CSR words. So the number of AXI words is 2^csr_addr_width / ratio.
        # AXI byte address width = log2(num_axi_words) + log2(data_width/8)
        # = (csr_addr_width - log2(ratio)) + log2(data_width/8)
        # But for the memory map, we use the CSR memory map's addressing.
        axi_addr_width = max(1, csr_bus.addr_width - exact_log2(ratio) + exact_log2(data_width // 8))

        axi_sig = AXI4LiteSignature(addr_width=axi_addr_width, data_width=data_width)

        super().__init__({"axi_bus": In(axi_sig)})

        # The memory map for the AXI bus uses byte addressing (data_width=8).
        # The CSR memory map uses csr_data_width addressing.
        # We add the CSR memory map as a window.
        self.axi_bus.memory_map = MemoryMap(addr_width=axi_addr_width, data_width=8)
        self.axi_bus.memory_map.add_window(csr_bus.memory_map, name=name)

        self._csr_bus = csr_bus

    @property
    def csr_bus(self):
        return self._csr_bus

    def elaborate(self, platform):
        csr_bus = self.csr_bus
        axi_bus = self.axi_bus

        m = Module()

        # Number of CSR beats per AXI transaction
        n_beats = axi_bus.data_width // csr_bus.data_width

        # Beat counter: counts from 0 to n_beats (inclusive; n_beats is the "done" state)
        beat = Signal(range(n_beats + 1))

        # Byte offset for word address conversion
        byte_shift = exact_log2(axi_bus.data_width // 8)

        # Latched AXI address (word address, shifted right by byte_shift)
        latched_addr = Signal(axi_bus.addr_width - byte_shift)

        # CSR address: concatenate beat counter (low bits) with latched AXI word address (high bits)
        if n_beats > 1:
            beat_bits = exact_log2(n_beats)
            m.d.comb += csr_bus.addr.eq(Cat(beat[:beat_bits], latched_addr))
        else:
            m.d.comb += csr_bus.addr.eq(latched_addr)

        # Read data accumulator
        r_data = Signal(axi_bus.data_width)

        # Write data register (latched from AXI wdata)
        w_data = Signal(axi_bus.data_width)

        def csr_segment(index):
            """Return the slice of AXI data corresponding to CSR beat `index`."""
            return slice(index * csr_bus.data_width, (index + 1) * csr_bus.data_width)

        with m.FSM(name="fsm"):
            with m.State("IDLE"):
                # Accept write address + write data
                m.d.comb += axi_bus.awready.eq(1)
                m.d.comb += axi_bus.wready.eq(1)
                # Accept read address
                m.d.comb += axi_bus.arready.eq(1)

                # Writes take priority
                with m.If(axi_bus.awvalid & axi_bus.wvalid):
                    m.d.sync += [
                        latched_addr.eq(axi_bus.awaddr[byte_shift:]),
                        w_data.eq(axi_bus.wdata),
                        beat.eq(0),
                    ]
                    m.next = "WRITE"
                with m.Elif(axi_bus.arvalid):
                    m.d.sync += [
                        latched_addr.eq(axi_bus.araddr[byte_shift:]),
                        beat.eq(0),
                    ]
                    m.next = "READ"

            with m.State("WRITE"):
                # Drive CSR write for current beat using Switch to select the right data segment
                m.d.comb += csr_bus.w_stb.eq(1)
                with m.Switch(beat):
                    for i in range(n_beats):
                        with m.Case(i):
                            m.d.comb += csr_bus.w_data.eq(w_data[csr_segment(i)])
                            if i == n_beats - 1:
                                m.next = "WRITE_RESP"
                            else:
                                m.d.sync += beat.eq(i + 1)

            with m.State("WRITE_RESP"):
                m.d.comb += [
                    axi_bus.bvalid.eq(1),
                    axi_bus.bresp.eq(AXIResp.OKAY),
                ]
                with m.If(axi_bus.bready):
                    m.next = "IDLE"

            with m.State("READ"):
                # Drive CSR read for current beat
                m.d.comb += csr_bus.r_stb.eq(1)

                with m.Switch(beat):
                    for i in range(n_beats):
                        with m.Case(i):
                            # CSR reads are registered: data appears one cycle after r_stb.
                            # So we capture the data from the *previous* beat here.
                            if i > 0:
                                m.d.sync += r_data[csr_segment(i - 1)].eq(csr_bus.r_data)
                            m.d.sync += beat.eq(i + 1)

                    with m.Default():
                        # beat == n_beats: capture the last beat's data and move to response
                        m.d.sync += r_data[csr_segment(n_beats - 1)].eq(csr_bus.r_data)
                        m.next = "READ_RESP"

            with m.State("READ_RESP"):
                m.d.comb += [
                    axi_bus.rvalid.eq(1),
                    axi_bus.rdata.eq(r_data),
                    axi_bus.rresp.eq(AXIResp.OKAY),
                ]
                with m.If(axi_bus.rready):
                    m.next = "IDLE"

        return m
