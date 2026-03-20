from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out, connect, flipped

from amaranth_soc.memory import MemoryMap

from .bus import AXI4LiteSignature, AXI4LiteInterface


__all__ = ["AXI4LiteArbiter"]


class AXI4LiteArbiter(wiring.Component):
    """AXI4-Lite round-robin arbiter.

    Arbitrates between multiple upstream (master) ports for access to
    a single downstream (slave) port.

    Parameters
    ----------
    addr_width : int
        Address width in bits.
    data_width : int
        Data width (32 or 64).
    """
    def __init__(self, *, addr_width, data_width):
        if not isinstance(addr_width, int) or addr_width < 0:
            raise TypeError(f"Address width must be a non-negative integer, not {addr_width!r}")
        if data_width not in (32, 64):
            raise ValueError(f"Data width must be one of 32, 64, not {data_width!r}")

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
