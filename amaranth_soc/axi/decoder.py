from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out, connect, flipped

from amaranth_soc.memory import MemoryMap

from .bus import AXI4LiteSignature, AXI4LiteInterface, AXIResp


__all__ = ["AXI4LiteDecoder"]


class AXI4LiteDecoder(wiring.Component):
    """AXI4-Lite address decoder.

    Routes transactions from a single upstream (master) port to multiple
    downstream (slave) ports based on address decoding using MemoryMap.

    Parameters
    ----------
    addr_width : int
        Address width in bits.
    data_width : int
        Data width (32 or 64).
    alignment : int, power-of-2 exponent
        Window alignment. Optional. See :class:`MemoryMap`.
    """
    def __init__(self, *, addr_width, data_width, alignment=0):
        if not isinstance(addr_width, int) or addr_width < 0:
            raise TypeError(f"Address width must be a non-negative integer, not {addr_width!r}")
        if data_width not in (32, 64):
            raise ValueError(f"Data width must be one of 32, 64, not {data_width!r}")

        self._addr_width = addr_width
        self._data_width = data_width

        super().__init__({"bus": In(AXI4LiteSignature(addr_width=addr_width,
                                                       data_width=data_width))})
        # Create byte-addressable memory map (AXI uses byte addressing)
        self.bus.memory_map = MemoryMap(
            addr_width=max(1, addr_width),
            data_width=8,
            alignment=alignment)
        self._subs = dict()

    @property
    def memory_map(self):
        return self.bus.memory_map

    def align_to(self, alignment):
        """Align the implicit address of the next window.

        See :meth:`MemoryMap.align_to` for details.
        """
        return self.bus.memory_map.align_to(alignment)

    def add(self, sub_bus, *, name=None, addr=None):
        """Add a subordinate bus.

        Parameters
        ----------
        sub_bus : AXI4LiteInterface
            The subordinate bus interface.
        name : str
            Name for this subordinate in the memory map.
        addr : int or None
            Base address. If None, auto-allocated.

        Returns
        -------
        A tuple ``(start, end, ratio)`` describing the address range assigned to the window.
        """
        if isinstance(sub_bus, wiring.FlippedInterface):
            sub_bus_unflipped = flipped(sub_bus)
        else:
            sub_bus_unflipped = sub_bus
        if not isinstance(sub_bus_unflipped, AXI4LiteInterface):
            raise TypeError(f"Subordinate bus must be an instance of AXI4LiteInterface, not "
                            f"{sub_bus_unflipped!r}")
        if sub_bus.data_width != self.bus.data_width:
            raise ValueError(f"Subordinate bus has data width {sub_bus.data_width}, which is "
                             f"not the same as decoder data width {self.bus.data_width}")

        self._subs[sub_bus.memory_map] = sub_bus
        return self.bus.memory_map.add_window(sub_bus.memory_map, name=name, addr=addr)

    def elaborate(self, platform):
        m = Module()

        # Collect subordinate info from memory map window patterns
        subs = []
        for sub_map, sub_name, (sub_pattern, sub_ratio) in self.bus.memory_map.window_patterns():
            sub_bus = self._subs[sub_map]
            subs.append((sub_bus, sub_map, sub_name, sub_pattern, sub_ratio))

        n_subs = len(subs)
        if n_subs == 0:
            # No subordinates: respond with DECERR to everything
            m.d.comb += [
                self.bus.awready.eq(0),
                self.bus.wready.eq(0),
                self.bus.bresp.eq(AXIResp.DECERR),
                self.bus.bvalid.eq(0),
                self.bus.arready.eq(0),
                self.bus.rdata.eq(0),
                self.bus.rresp.eq(AXIResp.DECERR),
                self.bus.rvalid.eq(0),
            ]
            return m

        # --- Address decode signals ---
        wr_target = Signal(range(n_subs + 1), name="wr_target")  # +1 for "no match"
        rd_target = Signal(range(n_subs + 1), name="rd_target")
        wr_target_latched = Signal(range(n_subs + 1), name="wr_target_latched")
        rd_target_latched = Signal(range(n_subs + 1), name="rd_target_latched")
        wr_no_match = Signal(name="wr_no_match")
        rd_no_match = Signal(name="rd_no_match")

        # --- Combinational address decode for write address ---
        m.d.comb += wr_target.eq(n_subs)  # default: no match
        with m.Switch(self.bus.awaddr):
            for i, (sub_bus, sub_map, sub_name, sub_pattern, sub_ratio) in enumerate(subs):
                with m.Case(sub_pattern):
                    m.d.comb += wr_target.eq(i)

        # --- Combinational address decode for read address ---
        m.d.comb += rd_target.eq(n_subs)  # default: no match
        with m.Switch(self.bus.araddr):
            for i, (sub_bus, sub_map, sub_name, sub_pattern, sub_ratio) in enumerate(subs):
                with m.Case(sub_pattern):
                    m.d.comb += rd_target.eq(i)

        # --- Write path FSM ---
        # States: IDLE -> ADDR (latch target, forward AW) -> DATA (forward W) -> RESP (wait B)
        with m.FSM(init="WR_IDLE", domain="sync") as wr_fsm:
            with m.State("WR_IDLE"):
                # Wait for write address valid
                with m.If(self.bus.awvalid):
                    m.d.sync += wr_target_latched.eq(wr_target)
                    m.d.sync += wr_no_match.eq(wr_target == n_subs)
                    m.next = "WR_ADDR"

            with m.State("WR_ADDR"):
                # Forward AW handshake to selected subordinate
                with m.If(wr_no_match):
                    # No match: accept AW immediately, move to data phase
                    m.d.comb += self.bus.awready.eq(1)
                    m.next = "WR_DATA"
                with m.Else():
                    # Forward awvalid to selected sub, wait for awready
                    for i, (sub_bus, *_) in enumerate(subs):
                        with m.If(wr_target_latched == i):
                            m.d.comb += [
                                sub_bus.awaddr.eq(self.bus.awaddr),
                                sub_bus.awprot.eq(self.bus.awprot),
                                sub_bus.awvalid.eq(self.bus.awvalid),
                                self.bus.awready.eq(sub_bus.awready),
                            ]
                    with m.If(self.bus.awvalid & self.bus.awready):
                        m.next = "WR_DATA"

            with m.State("WR_DATA"):
                # Forward W handshake to selected subordinate
                with m.If(wr_no_match):
                    # No match: accept W immediately, move to response
                    m.d.comb += self.bus.wready.eq(1)
                    with m.If(self.bus.wvalid):
                        m.next = "WR_RESP"
                with m.Else():
                    for i, (sub_bus, *_) in enumerate(subs):
                        with m.If(wr_target_latched == i):
                            m.d.comb += [
                                sub_bus.wdata.eq(self.bus.wdata),
                                sub_bus.wstrb.eq(self.bus.wstrb),
                                sub_bus.wvalid.eq(self.bus.wvalid),
                                self.bus.wready.eq(sub_bus.wready),
                            ]
                    with m.If(self.bus.wvalid & self.bus.wready):
                        m.next = "WR_RESP"

            with m.State("WR_RESP"):
                # Mux B channel back from selected subordinate
                with m.If(wr_no_match):
                    # No match: generate DECERR response
                    m.d.comb += [
                        self.bus.bresp.eq(AXIResp.DECERR),
                        self.bus.bvalid.eq(1),
                    ]
                    with m.If(self.bus.bready):
                        m.next = "WR_IDLE"
                with m.Else():
                    for i, (sub_bus, *_) in enumerate(subs):
                        with m.If(wr_target_latched == i):
                            m.d.comb += [
                                self.bus.bresp.eq(sub_bus.bresp),
                                self.bus.bvalid.eq(sub_bus.bvalid),
                                sub_bus.bready.eq(self.bus.bready),
                            ]
                    with m.If(self.bus.bvalid & self.bus.bready):
                        m.next = "WR_IDLE"

        # --- Read path FSM ---
        with m.FSM(init="RD_IDLE", domain="sync") as rd_fsm:
            with m.State("RD_IDLE"):
                # Wait for read address valid
                with m.If(self.bus.arvalid):
                    m.d.sync += rd_target_latched.eq(rd_target)
                    m.d.sync += rd_no_match.eq(rd_target == n_subs)
                    m.next = "RD_ADDR"

            with m.State("RD_ADDR"):
                # Forward AR handshake to selected subordinate
                with m.If(rd_no_match):
                    # No match: accept AR immediately
                    m.d.comb += self.bus.arready.eq(1)
                    m.next = "RD_RESP"
                with m.Else():
                    for i, (sub_bus, *_) in enumerate(subs):
                        with m.If(rd_target_latched == i):
                            m.d.comb += [
                                sub_bus.araddr.eq(self.bus.araddr),
                                sub_bus.arprot.eq(self.bus.arprot),
                                sub_bus.arvalid.eq(self.bus.arvalid),
                                self.bus.arready.eq(sub_bus.arready),
                            ]
                    with m.If(self.bus.arvalid & self.bus.arready):
                        m.next = "RD_RESP"

            with m.State("RD_RESP"):
                # Mux R channel back from selected subordinate
                with m.If(rd_no_match):
                    # No match: generate DECERR response
                    m.d.comb += [
                        self.bus.rdata.eq(0),
                        self.bus.rresp.eq(AXIResp.DECERR),
                        self.bus.rvalid.eq(1),
                    ]
                    with m.If(self.bus.rready):
                        m.next = "RD_IDLE"
                with m.Else():
                    for i, (sub_bus, *_) in enumerate(subs):
                        with m.If(rd_target_latched == i):
                            m.d.comb += [
                                self.bus.rdata.eq(sub_bus.rdata),
                                self.bus.rresp.eq(sub_bus.rresp),
                                self.bus.rvalid.eq(sub_bus.rvalid),
                                sub_bus.rready.eq(self.bus.rready),
                            ]
                    with m.If(self.bus.rvalid & self.bus.rready):
                        m.next = "RD_IDLE"

        return m
