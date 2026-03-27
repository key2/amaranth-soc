from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out, connect, flipped

from amaranth_soc.memory import MemoryMap

from .bus import AXI4LiteSignature, AXI4LiteInterface, AXI4Signature, AXI4Interface


__all__ = ["AXI4LiteArbiter", "AXI4Arbiter"]


class AXI4LiteArbiter(wiring.Component):
    """AXI4-Lite round-robin arbiter.

    Arbitrates between multiple upstream (master) ports for access to
    a single downstream (slave) port.

    Parameters
    ----------
    addr_width : int
        Address width in bits.
    data_width : int, power of 2, >= 32
        Data width. Must be a power of 2 and at least 32.
    """
    def __init__(self, *, addr_width, data_width):
        if not isinstance(addr_width, int) or addr_width < 0:
            raise TypeError(f"Address width must be a non-negative integer, not {addr_width!r}")
        if not isinstance(data_width, int) or data_width < 32:
            raise ValueError(f"Data width must be a positive integer >= 32, not {data_width!r}")
        if data_width & (data_width - 1) != 0:
            raise ValueError(f"Data width must be a power of 2, not {data_width!r}")

        self._addr_width = addr_width
        self._data_width = data_width

        super().__init__({"bus": Out(AXI4LiteSignature(addr_width=addr_width,
                                                        data_width=data_width))})
        self._masters = []

    def add(self, master_bus, *, name=None):
        """Add a master bus to arbitrate.

        Parameters
        ----------
        master_bus : AXI4LiteInterface
            The master bus interface.
        name : str or None
            Optional name for this master.
        """
        if isinstance(master_bus, wiring.FlippedInterface):
            master_bus_unflipped = flipped(master_bus)
        else:
            master_bus_unflipped = master_bus
        if not isinstance(master_bus_unflipped, AXI4LiteInterface):
            raise TypeError(f"Master bus must be an instance of AXI4LiteInterface, not "
                            f"{master_bus_unflipped!r}")
        if master_bus.addr_width != self.bus.addr_width:
            raise ValueError(f"Master bus has address width {master_bus.addr_width}, which is "
                             f"not the same as arbiter address width {self.bus.addr_width}")
        if master_bus.data_width != self.bus.data_width:
            raise ValueError(f"Master bus has data width {master_bus.data_width}, which is "
                             f"not the same as arbiter data width {self.bus.data_width}")
        self._masters.append(master_bus)

    def elaborate(self, platform):
        m = Module()

        n_masters = len(self._masters)
        if n_masters == 0:
            # No masters: tie off the bus
            m.d.comb += [
                self.bus.awaddr.eq(0),
                self.bus.awprot.eq(0),
                self.bus.awvalid.eq(0),
                self.bus.wdata.eq(0),
                self.bus.wstrb.eq(0),
                self.bus.wvalid.eq(0),
                self.bus.bready.eq(0),
                self.bus.araddr.eq(0),
                self.bus.arprot.eq(0),
                self.bus.arvalid.eq(0),
                self.bus.rready.eq(0),
            ]
            return m

        # --- Grant and lock signals ---
        grant = Signal(range(n_masters), name="grant")
        wr_locked = Signal(name="wr_locked")
        rd_locked = Signal(name="rd_locked")
        locked = Signal(name="locked")
        m.d.comb += locked.eq(wr_locked | rd_locked)

        # --- Request signals ---
        # A master is requesting if it has awvalid or arvalid asserted
        requests = Signal(n_masters, name="requests")
        for i, master_bus in enumerate(self._masters):
            m.d.comb += requests[i].eq(master_bus.awvalid | master_bus.arvalid)

        # --- Round-robin grant selection ---
        # Only update grant when not locked in a transaction
        with m.If(~locked):
            with m.Switch(grant):
                for i in range(n_masters):
                    with m.Case(i):
                        # Check successors first (round-robin), then predecessors
                        for pred in reversed(range(i)):
                            with m.If(requests[pred]):
                                m.d.sync += grant.eq(pred)
                        for succ in reversed(range(i + 1, n_masters)):
                            with m.If(requests[succ]):
                                m.d.sync += grant.eq(succ)

        # --- Transaction locking ---
        # Lock on AW handshake, unlock on B handshake
        with m.If(self.bus.awvalid & self.bus.awready):
            m.d.sync += wr_locked.eq(1)
        with m.If(self.bus.bvalid & self.bus.bready):
            m.d.sync += wr_locked.eq(0)

        # Lock on AR handshake, unlock on R handshake
        with m.If(self.bus.arvalid & self.bus.arready):
            m.d.sync += rd_locked.eq(1)
        with m.If(self.bus.rvalid & self.bus.rready):
            m.d.sync += rd_locked.eq(0)

        # --- Mux master signals to slave, demux slave responses ---
        with m.Switch(grant):
            for i, master_bus in enumerate(self._masters):
                with m.Case(i):
                    # Forward master -> slave (AW channel)
                    m.d.comb += [
                        self.bus.awaddr.eq(master_bus.awaddr),
                        self.bus.awprot.eq(master_bus.awprot),
                        self.bus.awvalid.eq(master_bus.awvalid),
                        master_bus.awready.eq(self.bus.awready),
                    ]
                    # Forward master -> slave (W channel)
                    m.d.comb += [
                        self.bus.wdata.eq(master_bus.wdata),
                        self.bus.wstrb.eq(master_bus.wstrb),
                        self.bus.wvalid.eq(master_bus.wvalid),
                        master_bus.wready.eq(self.bus.wready),
                    ]
                    # Forward slave -> master (B channel)
                    m.d.comb += [
                        master_bus.bresp.eq(self.bus.bresp),
                        master_bus.bvalid.eq(self.bus.bvalid),
                        self.bus.bready.eq(master_bus.bready),
                    ]
                    # Forward master -> slave (AR channel)
                    m.d.comb += [
                        self.bus.araddr.eq(master_bus.araddr),
                        self.bus.arprot.eq(master_bus.arprot),
                        self.bus.arvalid.eq(master_bus.arvalid),
                        master_bus.arready.eq(self.bus.arready),
                    ]
                    # Forward slave -> master (R channel)
                    m.d.comb += [
                        master_bus.rdata.eq(self.bus.rdata),
                        master_bus.rresp.eq(self.bus.rresp),
                        master_bus.rvalid.eq(self.bus.rvalid),
                        self.bus.rready.eq(master_bus.rready),
                    ]

        return m


class AXI4Arbiter(wiring.Component):
    """AXI4 Full round-robin arbiter.

    Arbitrates between multiple AXI4 managers using round-robin priority.
    Handles burst transactions with proper locking until WLAST/RLAST.

    Parameters
    ----------
    addr_width : int
        Address width.
    data_width : int, power of 2, >= 8
        Data width.
    id_width : int
        ID signal width (default 0).
    """
    def __init__(self, *, addr_width, data_width, id_width=0):
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

        super().__init__({"bus": Out(AXI4Signature(addr_width=addr_width,
                                                    data_width=data_width,
                                                    id_width=id_width))})
        self._masters = []

    def add(self, master_bus, *, name=None):
        """Add a master bus to arbitrate.

        Parameters
        ----------
        master_bus : AXI4Interface
            The master bus interface.
        name : str or None
            Optional name for this master.
        """
        if isinstance(master_bus, wiring.FlippedInterface):
            master_bus_unflipped = flipped(master_bus)
        else:
            master_bus_unflipped = master_bus
        if not isinstance(master_bus_unflipped, AXI4Interface):
            raise TypeError(f"Master bus must be an instance of AXI4Interface, not "
                            f"{master_bus_unflipped!r}")
        if master_bus.data_width != self.bus.data_width:
            raise ValueError(f"Master bus has data width {master_bus.data_width}, which is "
                             f"not the same as arbiter data width {self.bus.data_width}")
        if master_bus.id_width != self.bus.id_width:
            raise ValueError(f"Master bus has ID width {master_bus.id_width}, which is "
                             f"not the same as arbiter ID width {self.bus.id_width}")
        self._masters.append(master_bus)

    def elaborate(self, platform):
        m = Module()

        n_masters = len(self._masters)
        has_id = self._id_width > 0

        if n_masters == 0:
            # No masters: tie off the bus
            m.d.comb += [
                self.bus.awaddr.eq(0),
                self.bus.awprot.eq(0),
                self.bus.awvalid.eq(0),
                self.bus.awlen.eq(0),
                self.bus.awsize.eq(0),
                self.bus.awburst.eq(0),
                self.bus.awlock.eq(0),
                self.bus.awcache.eq(0),
                self.bus.awqos.eq(0),
                self.bus.awregion.eq(0),
                self.bus.wdata.eq(0),
                self.bus.wstrb.eq(0),
                self.bus.wlast.eq(0),
                self.bus.wvalid.eq(0),
                self.bus.bready.eq(0),
                self.bus.araddr.eq(0),
                self.bus.arprot.eq(0),
                self.bus.arvalid.eq(0),
                self.bus.arlen.eq(0),
                self.bus.arsize.eq(0),
                self.bus.arburst.eq(0),
                self.bus.arlock.eq(0),
                self.bus.arcache.eq(0),
                self.bus.arqos.eq(0),
                self.bus.arregion.eq(0),
                self.bus.rready.eq(0),
            ]
            if has_id:
                m.d.comb += [
                    self.bus.awid.eq(0),
                    self.bus.arid.eq(0),
                ]
            return m

        # --- Grant and lock signals ---
        grant = Signal(range(n_masters), name="grant")
        wr_locked = Signal(name="wr_locked")
        rd_locked = Signal(name="rd_locked")
        locked = Signal(name="locked")
        m.d.comb += locked.eq(wr_locked | rd_locked)

        # --- Request signals ---
        # A master is requesting if it has awvalid or arvalid asserted
        requests = Signal(n_masters, name="requests")
        for i, master_bus in enumerate(self._masters):
            m.d.comb += requests[i].eq(master_bus.awvalid | master_bus.arvalid)

        # --- Round-robin grant selection ---
        # Only update grant when not locked in a transaction
        with m.If(~locked):
            with m.Switch(grant):
                for i in range(n_masters):
                    with m.Case(i):
                        # Check successors first (round-robin), then predecessors
                        for pred in reversed(range(i)):
                            with m.If(requests[pred]):
                                m.d.sync += grant.eq(pred)
                        for succ in reversed(range(i + 1, n_masters)):
                            with m.If(requests[succ]):
                                m.d.sync += grant.eq(succ)

        # --- Transaction locking ---
        # Write lock: set on AW handshake, clear on W handshake with WLAST
        with m.If(self.bus.awvalid & self.bus.awready):
            m.d.sync += wr_locked.eq(1)
        with m.Elif(self.bus.wvalid & self.bus.wready & self.bus.wlast):
            m.d.sync += wr_locked.eq(0)

        # Read lock: set on AR handshake, clear on R handshake with RLAST
        with m.If(self.bus.arvalid & self.bus.arready):
            m.d.sync += rd_locked.eq(1)
        with m.Elif(self.bus.rvalid & self.bus.rready & self.bus.rlast):
            m.d.sync += rd_locked.eq(0)

        # --- Mux master signals to slave, demux slave responses ---
        with m.Switch(grant):
            for i, master_bus in enumerate(self._masters):
                with m.Case(i):
                    # Forward master -> slave (AW channel)
                    aw_signals = [
                        self.bus.awaddr.eq(master_bus.awaddr),
                        self.bus.awprot.eq(master_bus.awprot),
                        self.bus.awvalid.eq(master_bus.awvalid),
                        master_bus.awready.eq(self.bus.awready),
                        self.bus.awlen.eq(master_bus.awlen),
                        self.bus.awsize.eq(master_bus.awsize),
                        self.bus.awburst.eq(master_bus.awburst),
                        self.bus.awlock.eq(master_bus.awlock),
                        self.bus.awcache.eq(master_bus.awcache),
                        self.bus.awqos.eq(master_bus.awqos),
                        self.bus.awregion.eq(master_bus.awregion),
                    ]
                    if has_id:
                        aw_signals.append(self.bus.awid.eq(master_bus.awid))
                    m.d.comb += aw_signals

                    # Forward master -> slave (W channel)
                    m.d.comb += [
                        self.bus.wdata.eq(master_bus.wdata),
                        self.bus.wstrb.eq(master_bus.wstrb),
                        self.bus.wlast.eq(master_bus.wlast),
                        self.bus.wvalid.eq(master_bus.wvalid),
                        master_bus.wready.eq(self.bus.wready),
                    ]

                    # Forward slave -> master (B channel)
                    b_signals = [
                        master_bus.bresp.eq(self.bus.bresp),
                        master_bus.bvalid.eq(self.bus.bvalid),
                        self.bus.bready.eq(master_bus.bready),
                    ]
                    if has_id:
                        b_signals.append(master_bus.bid.eq(self.bus.bid))
                    m.d.comb += b_signals

                    # Forward master -> slave (AR channel)
                    ar_signals = [
                        self.bus.araddr.eq(master_bus.araddr),
                        self.bus.arprot.eq(master_bus.arprot),
                        self.bus.arvalid.eq(master_bus.arvalid),
                        master_bus.arready.eq(self.bus.arready),
                        self.bus.arlen.eq(master_bus.arlen),
                        self.bus.arsize.eq(master_bus.arsize),
                        self.bus.arburst.eq(master_bus.arburst),
                        self.bus.arlock.eq(master_bus.arlock),
                        self.bus.arcache.eq(master_bus.arcache),
                        self.bus.arqos.eq(master_bus.arqos),
                        self.bus.arregion.eq(master_bus.arregion),
                    ]
                    if has_id:
                        ar_signals.append(self.bus.arid.eq(master_bus.arid))
                    m.d.comb += ar_signals

                    # Forward slave -> master (R channel)
                    r_signals = [
                        master_bus.rdata.eq(self.bus.rdata),
                        master_bus.rresp.eq(self.bus.rresp),
                        master_bus.rlast.eq(self.bus.rlast),
                        master_bus.rvalid.eq(self.bus.rvalid),
                        self.bus.rready.eq(master_bus.rready),
                    ]
                    if has_id:
                        r_signals.append(master_bus.rid.eq(self.bus.rid))
                    m.d.comb += r_signals

        return m
