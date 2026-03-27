from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out, connect, flipped

from amaranth_soc.memory import MemoryMap

from .bus import AXI4LiteSignature, AXI4LiteInterface, AXI4Signature, AXI4Interface, AXIResp


__all__ = ["AXI4LiteDecoder", "AXI4Decoder"]


class AXI4LiteDecoder(wiring.Component):
    """AXI4-Lite address decoder.

    Routes transactions from a single upstream (master) port to multiple
    downstream (slave) ports based on address decoding using MemoryMap.

    Parameters
    ----------
    addr_width : int
        Address width in bits.
    data_width : int, power of 2, >= 32
        Data width. Must be a power of 2 and at least 32.
    alignment : int, power-of-2 exponent
        Window alignment. Optional. See :class:`MemoryMap`.
    pipelined : bool
        When True, allows the address phase of the next transaction to overlap
        with the response phase of the current transaction, improving throughput.
        Default is False, which preserves the original serialized behavior.
    """
    def __init__(self, *, addr_width, data_width, alignment=0, pipelined=False):
        if not isinstance(addr_width, int) or addr_width < 0:
            raise TypeError(f"Address width must be a non-negative integer, not {addr_width!r}")
        if not isinstance(data_width, int) or data_width < 32:
            raise ValueError(f"Data width must be a positive integer >= 32, not {data_width!r}")
        if data_width & (data_width - 1) != 0:
            raise ValueError(f"Data width must be a power of 2, not {data_width!r}")

        self._addr_width = addr_width
        self._data_width = data_width
        self._pipelined = pipelined

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

    @property
    def pipelined(self):
        return self._pipelined

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

        # --- Pipelined mode: next-transaction registers ---
        if self._pipelined:
            wr_next_target = Signal(range(n_subs + 1), name="wr_next_target")
            wr_next_no_match = Signal(name="wr_next_no_match")
            wr_next_valid = Signal(name="wr_next_valid")
            rd_next_target = Signal(range(n_subs + 1), name="rd_next_target")
            rd_next_no_match = Signal(name="rd_next_no_match")
            rd_next_valid = Signal(name="rd_next_valid")

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
                        if self._pipelined:
                            m.d.sync += wr_next_valid.eq(0)
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
                        if self._pipelined:
                            m.d.sync += wr_next_valid.eq(0)

            with m.State("WR_RESP"):
                # Mux B channel back from selected subordinate
                with m.If(wr_no_match):
                    # No match: generate DECERR response
                    m.d.comb += [
                        self.bus.bresp.eq(AXIResp.DECERR),
                        self.bus.bvalid.eq(1),
                    ]
                    with m.If(self.bus.bready):
                        if self._pipelined:
                            with m.If(wr_next_valid):
                                # Pre-latched next transaction: skip IDLE
                                m.d.sync += wr_target_latched.eq(wr_next_target)
                                m.d.sync += wr_no_match.eq(wr_next_no_match)
                                m.d.sync += wr_next_valid.eq(0)
                                m.next = "WR_ADDR"
                            with m.Else():
                                m.next = "WR_IDLE"
                        else:
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
                        if self._pipelined:
                            with m.If(wr_next_valid):
                                # Pre-latched next transaction: skip IDLE
                                m.d.sync += wr_target_latched.eq(wr_next_target)
                                m.d.sync += wr_no_match.eq(wr_next_no_match)
                                m.d.sync += wr_next_valid.eq(0)
                                m.next = "WR_ADDR"
                            with m.Else():
                                m.next = "WR_IDLE"
                        else:
                            m.next = "WR_IDLE"

                # Pipelined: accept new AW while waiting for B response
                if self._pipelined:
                    with m.If(self.bus.awvalid & ~wr_next_valid):
                        m.d.sync += wr_next_target.eq(wr_target)
                        m.d.sync += wr_next_no_match.eq(wr_target == n_subs)
                        m.d.sync += wr_next_valid.eq(1)

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
                        if self._pipelined:
                            m.d.sync += rd_next_valid.eq(0)

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
                        if self._pipelined:
                            with m.If(rd_next_valid):
                                m.d.sync += rd_target_latched.eq(rd_next_target)
                                m.d.sync += rd_no_match.eq(rd_next_no_match)
                                m.d.sync += rd_next_valid.eq(0)
                                m.next = "RD_ADDR"
                            with m.Else():
                                m.next = "RD_IDLE"
                        else:
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
                        if self._pipelined:
                            with m.If(rd_next_valid):
                                m.d.sync += rd_target_latched.eq(rd_next_target)
                                m.d.sync += rd_no_match.eq(rd_next_no_match)
                                m.d.sync += rd_next_valid.eq(0)
                                m.next = "RD_ADDR"
                            with m.Else():
                                m.next = "RD_IDLE"
                        else:
                            m.next = "RD_IDLE"

                # Pipelined: accept new AR while waiting for R response
                if self._pipelined:
                    with m.If(self.bus.arvalid & ~rd_next_valid):
                        m.d.sync += rd_next_target.eq(rd_target)
                        m.d.sync += rd_next_no_match.eq(rd_target == n_subs)
                        m.d.sync += rd_next_valid.eq(1)

        return m


class AXI4Decoder(wiring.Component):
    """AXI4 Full address decoder.

    Routes AXI4 transactions to subordinates based on address decoding.
    Handles burst transactions, ID forwarding, and WLAST/RLAST tracking.
    Generates DECERR for unmapped addresses.

    Parameters
    ----------
    addr_width : int
        Address width.
    data_width : int, power of 2, >= 8
        Data width.
    id_width : int
        ID signal width (default 0).
    alignment : int
        Memory map alignment (default 0).
    """
    def __init__(self, *, addr_width, data_width, id_width=0, alignment=0):
        if not isinstance(addr_width, int) or addr_width < 0:
            raise TypeError(f"Address width must be a non-negative integer, not {addr_width!r}")
        if not isinstance(data_width, int) or data_width < 8:
            raise ValueError(f"Data width must be an integer >= 8, not {data_width!r}")
        if data_width & (data_width - 1) != 0:
            raise ValueError(f"Data width must be a power of 2, not {data_width!r}")
        if not isinstance(id_width, int) or id_width < 0:
            raise TypeError(f"ID width must be a non-negative integer, not {id_width!r}")

        self._addr_width = addr_width
        self._data_width = data_width
        self._id_width = id_width

        super().__init__({"bus": In(AXI4Signature(addr_width=addr_width,
                                                   data_width=data_width,
                                                   id_width=id_width))})
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
        sub_bus : AXI4Interface
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
        if not isinstance(sub_bus_unflipped, AXI4Interface):
            raise TypeError(f"Subordinate bus must be an instance of AXI4Interface, not "
                            f"{sub_bus_unflipped!r}")
        if sub_bus.data_width != self.bus.data_width:
            raise ValueError(f"Subordinate bus has data width {sub_bus.data_width}, which is "
                             f"not the same as decoder data width {self.bus.data_width}")
        if sub_bus.id_width != self._id_width:
            raise ValueError(f"Subordinate bus has id width {sub_bus.id_width}, which is "
                             f"not the same as decoder id width {self._id_width}")

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
        has_id = self._id_width > 0

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
                self.bus.rlast.eq(0),
            ]
            if has_id:
                m.d.comb += [
                    self.bus.bid.eq(0),
                    self.bus.rid.eq(0),
                ]
            return m

        # --- Address decode signals ---
        wr_target = Signal(range(n_subs + 1), name="wr_target")  # +1 for "no match"
        rd_target = Signal(range(n_subs + 1), name="rd_target")
        wr_target_latched = Signal(range(n_subs + 1), name="wr_target_latched")
        rd_target_latched = Signal(range(n_subs + 1), name="rd_target_latched")
        wr_no_match = Signal(name="wr_no_match")
        rd_no_match = Signal(name="rd_no_match")

        # Latched ID signals for DECERR responses
        if has_id:
            wr_id_latched = Signal(self._id_width, name="wr_id_latched")
            rd_id_latched = Signal(self._id_width, name="rd_id_latched")
        # Latched arlen for DECERR read response beat counting
        rd_len_latched = Signal(8, name="rd_len_latched")
        rd_decerr_cnt = Signal(8, name="rd_decerr_cnt")

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
        with m.FSM(init="WR_IDLE", domain="sync") as wr_fsm:
            with m.State("WR_IDLE"):
                # Wait for write address valid
                with m.If(self.bus.awvalid):
                    m.d.sync += wr_target_latched.eq(wr_target)
                    m.d.sync += wr_no_match.eq(wr_target == n_subs)
                    if has_id:
                        m.d.sync += wr_id_latched.eq(self.bus.awid)
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
                                sub_bus.awlen.eq(self.bus.awlen),
                                sub_bus.awsize.eq(self.bus.awsize),
                                sub_bus.awburst.eq(self.bus.awburst),
                                sub_bus.awlock.eq(self.bus.awlock),
                                sub_bus.awcache.eq(self.bus.awcache),
                                sub_bus.awqos.eq(self.bus.awqos),
                                sub_bus.awregion.eq(self.bus.awregion),
                                sub_bus.awvalid.eq(self.bus.awvalid),
                                self.bus.awready.eq(sub_bus.awready),
                            ]
                            if has_id:
                                m.d.comb += sub_bus.awid.eq(self.bus.awid)
                    with m.If(self.bus.awvalid & self.bus.awready):
                        m.next = "WR_DATA"

            with m.State("WR_DATA"):
                # Forward W channel to selected subordinate
                with m.If(wr_no_match):
                    # No match: sink data until wlast
                    m.d.comb += self.bus.wready.eq(1)
                    with m.If(self.bus.wvalid & self.bus.wlast):
                        m.next = "WR_RESP"
                with m.Else():
                    for i, (sub_bus, *_) in enumerate(subs):
                        with m.If(wr_target_latched == i):
                            m.d.comb += [
                                sub_bus.wdata.eq(self.bus.wdata),
                                sub_bus.wstrb.eq(self.bus.wstrb),
                                sub_bus.wlast.eq(self.bus.wlast),
                                sub_bus.wvalid.eq(self.bus.wvalid),
                                self.bus.wready.eq(sub_bus.wready),
                            ]
                    with m.If(self.bus.wvalid & self.bus.wready & self.bus.wlast):
                        m.next = "WR_RESP"

            with m.State("WR_RESP"):
                # Mux B channel back from selected subordinate
                with m.If(wr_no_match):
                    # No match: generate DECERR response
                    m.d.comb += [
                        self.bus.bresp.eq(AXIResp.DECERR),
                        self.bus.bvalid.eq(1),
                    ]
                    if has_id:
                        m.d.comb += self.bus.bid.eq(wr_id_latched)
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
                            if has_id:
                                m.d.comb += self.bus.bid.eq(sub_bus.bid)
                    with m.If(self.bus.bvalid & self.bus.bready):
                        m.next = "WR_IDLE"

        # --- Read path FSM ---
        with m.FSM(init="RD_IDLE", domain="sync") as rd_fsm:
            with m.State("RD_IDLE"):
                # Wait for read address valid
                with m.If(self.bus.arvalid):
                    m.d.sync += rd_target_latched.eq(rd_target)
                    m.d.sync += rd_no_match.eq(rd_target == n_subs)
                    if has_id:
                        m.d.sync += rd_id_latched.eq(self.bus.arid)
                    m.d.sync += rd_len_latched.eq(self.bus.arlen)
                    m.d.sync += rd_decerr_cnt.eq(0)
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
                                sub_bus.arlen.eq(self.bus.arlen),
                                sub_bus.arsize.eq(self.bus.arsize),
                                sub_bus.arburst.eq(self.bus.arburst),
                                sub_bus.arlock.eq(self.bus.arlock),
                                sub_bus.arcache.eq(self.bus.arcache),
                                sub_bus.arqos.eq(self.bus.arqos),
                                sub_bus.arregion.eq(self.bus.arregion),
                                sub_bus.arvalid.eq(self.bus.arvalid),
                                self.bus.arready.eq(sub_bus.arready),
                            ]
                            if has_id:
                                m.d.comb += sub_bus.arid.eq(self.bus.arid)
                    with m.If(self.bus.arvalid & self.bus.arready):
                        m.next = "RD_RESP"

            with m.State("RD_RESP"):
                # Mux R channel back from selected subordinate
                with m.If(rd_no_match):
                    # No match: generate DECERR response with rlast=1 on last beat
                    m.d.comb += [
                        self.bus.rdata.eq(0),
                        self.bus.rresp.eq(AXIResp.DECERR),
                        self.bus.rvalid.eq(1),
                        self.bus.rlast.eq(rd_decerr_cnt == rd_len_latched),
                    ]
                    if has_id:
                        m.d.comb += self.bus.rid.eq(rd_id_latched)
                    with m.If(self.bus.rready):
                        with m.If(rd_decerr_cnt == rd_len_latched):
                            m.next = "RD_IDLE"
                        with m.Else():
                            m.d.sync += rd_decerr_cnt.eq(rd_decerr_cnt + 1)
                with m.Else():
                    for i, (sub_bus, *_) in enumerate(subs):
                        with m.If(rd_target_latched == i):
                            m.d.comb += [
                                self.bus.rdata.eq(sub_bus.rdata),
                                self.bus.rresp.eq(sub_bus.rresp),
                                self.bus.rvalid.eq(sub_bus.rvalid),
                                self.bus.rlast.eq(sub_bus.rlast),
                                sub_bus.rready.eq(self.bus.rready),
                            ]
                            if has_id:
                                m.d.comb += self.bus.rid.eq(sub_bus.rid)
                    with m.If(self.bus.rvalid & self.bus.rready & self.bus.rlast):
                        m.next = "RD_IDLE"

        return m
