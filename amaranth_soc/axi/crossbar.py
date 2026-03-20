"""AXI4-Lite NxM crossbar interconnect.

Composes N decoders (one per master) and M arbiters (one per slave)
to create a full NxM crossbar fabric.
"""

from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out, connect, flipped

from amaranth_soc.memory import MemoryMap

from .bus import AXI4LiteSignature, AXI4LiteInterface
from .decoder import AXI4LiteDecoder
from .arbiter import AXI4LiteArbiter


__all__ = ["AXI4LiteCrossbar"]


class AXI4LiteCrossbar(wiring.Component):
    """AXI4-Lite NxM crossbar interconnect.

    Each master gets its own decoder (for address routing).
    Each slave gets its own arbiter (for master selection).

    The crossbar is built by:
    1. Creating N decoders (one per master), each with M slave windows
    2. Creating M arbiters (one per slave), each with N master inputs
    3. Wiring decoder[i].sub[j] → arbiter[j].master[i]

    Parameters
    ----------
    addr_width : int
        Address width.
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
        self._masters = []
        self._slaves = []
        self._built = False

        # We don't call super().__init__() with a signature here because
        # the crossbar is configured dynamically via add_master/add_slave.
        # The elaborate() method will build the internal structure.
        super().__init__({})

    @property
    def addr_width(self):
        return self._addr_width

    @property
    def data_width(self):
        return self._data_width

    def add_master(self, master_bus, *, name=None):
        """Add a master port.

        Parameters
        ----------
        master_bus : AXI4LiteInterface
            The master bus interface to connect.
        name : str or None
            Optional name for this master.
        """
        if self._built:
            raise RuntimeError("Cannot add masters after elaborate() has been called")
        if isinstance(master_bus, wiring.FlippedInterface):
            master_bus_unflipped = flipped(master_bus)
        else:
            master_bus_unflipped = master_bus
        if not isinstance(master_bus_unflipped, AXI4LiteInterface):
            raise TypeError(f"Master bus must be an instance of AXI4LiteInterface, not "
                            f"{master_bus_unflipped!r}")
        if master_bus.data_width != self._data_width:
            raise ValueError(f"Master bus has data width {master_bus.data_width}, which is "
                             f"not the same as crossbar data width {self._data_width}")
        idx = len(self._masters)
        if name is None:
            name = f"master_{idx}"
        self._masters.append((master_bus, name))

    def add_slave(self, slave_bus, *, name=None, addr=None):
        """Add a slave port with address mapping.

        Parameters
        ----------
        slave_bus : AXI4LiteInterface
            The slave bus interface to connect.
        name : str or None
            Name for this slave in the memory map.
        addr : int or None
            Base address. If None, auto-allocated.
        """
        if self._built:
            raise RuntimeError("Cannot add slaves after elaborate() has been called")
        if isinstance(slave_bus, wiring.FlippedInterface):
            slave_bus_unflipped = flipped(slave_bus)
        else:
            slave_bus_unflipped = slave_bus
        if not isinstance(slave_bus_unflipped, AXI4LiteInterface):
            raise TypeError(f"Slave bus must be an instance of AXI4LiteInterface, not "
                            f"{slave_bus_unflipped!r}")
        if slave_bus.data_width != self._data_width:
            raise ValueError(f"Slave bus has data width {slave_bus.data_width}, which is "
                             f"not the same as crossbar data width {self._data_width}")
        idx = len(self._slaves)
        if name is None:
            name = f"slave_{idx}"
        self._slaves.append((slave_bus, name, addr))

    def elaborate(self, platform):
        m = Module()
        self._built = True

        n_masters = len(self._masters)
        n_slaves = len(self._slaves)

        if n_masters == 0 or n_slaves == 0:
            return m

        # --- Create one decoder per master ---
        decoders = []
        for i, (master_bus, master_name) in enumerate(self._masters):
            dec = AXI4LiteDecoder(addr_width=self._addr_width,
                                  data_width=self._data_width)
            m.submodules[f"dec_{master_name}"] = dec
            decoders.append(dec)

        # --- Create one arbiter per slave ---
        # Each arbiter uses the slave's addr_width so intermediate buses match.
        arbiters = []
        for j, (slave_bus, slave_name, slave_addr) in enumerate(self._slaves):
            slave_aw = slave_bus.memory_map.addr_width
            arb = AXI4LiteArbiter(addr_width=slave_aw,
                                  data_width=self._data_width)
            m.submodules[f"arb_{slave_name}"] = arb
            arbiters.append(arb)

        # --- Create intermediate interfaces for decoder→arbiter connections ---
        # For each (master_i, slave_j) pair, we need an intermediate bus.
        # The intermediate bus uses the slave's addr_width so it can be placed
        # as a window in the decoder and accepted by the arbiter.
        inter_buses = {}
        for i in range(n_masters):
            for j, (slave_bus, slave_name, slave_addr) in enumerate(self._slaves):
                slave_map = slave_bus.memory_map
                slave_aw = slave_map.addr_width
                inter = AXI4LiteInterface(addr_width=slave_aw,
                                          data_width=self._data_width,
                                          path=["xbar", f"m{i}_s{j}"])
                inter.memory_map = MemoryMap(addr_width=slave_aw,
                                             data_width=slave_map.data_width)
                inter_buses[(i, j)] = inter

        # --- Add slave windows to each decoder ---
        for i, dec in enumerate(decoders):
            for j, (slave_bus, slave_name, slave_addr) in enumerate(self._slaves):
                inter = inter_buses[(i, j)]
                dec.add(inter, name=f"{slave_name}", addr=slave_addr)

        # --- Add master inputs to each arbiter ---
        for j, arb in enumerate(arbiters):
            for i in range(n_masters):
                inter = inter_buses[(i, j)]
                arb.add(inter, name=f"m{i}")

        # --- Wire master buses to decoder inputs ---
        for i, (master_bus, master_name) in enumerate(self._masters):
            dec = decoders[i]
            # Connect master_bus → decoder.bus
            # master_bus is an initiator (Out), decoder.bus is In (target)
            # We need to wire all signals manually since they may not be
            # directly connectable via wiring.connect()
            m.d.comb += [
                # AW channel: master → decoder
                dec.bus.awaddr.eq(master_bus.awaddr),
                dec.bus.awprot.eq(master_bus.awprot),
                dec.bus.awvalid.eq(master_bus.awvalid),
                master_bus.awready.eq(dec.bus.awready),
                # W channel: master → decoder
                dec.bus.wdata.eq(master_bus.wdata),
                dec.bus.wstrb.eq(master_bus.wstrb),
                dec.bus.wvalid.eq(master_bus.wvalid),
                master_bus.wready.eq(dec.bus.wready),
                # B channel: decoder → master
                master_bus.bresp.eq(dec.bus.bresp),
                master_bus.bvalid.eq(dec.bus.bvalid),
                dec.bus.bready.eq(master_bus.bready),
                # AR channel: master → decoder
                dec.bus.araddr.eq(master_bus.araddr),
                dec.bus.arprot.eq(master_bus.arprot),
                dec.bus.arvalid.eq(master_bus.arvalid),
                master_bus.arready.eq(dec.bus.arready),
                # R channel: decoder → master
                master_bus.rdata.eq(dec.bus.rdata),
                master_bus.rresp.eq(dec.bus.rresp),
                master_bus.rvalid.eq(dec.bus.rvalid),
                dec.bus.rready.eq(master_bus.rready),
            ]

        # --- Wire arbiter outputs to slave buses ---
        for j, (slave_bus, slave_name, slave_addr) in enumerate(self._slaves):
            arb = arbiters[j]
            # Connect arbiter.bus → slave_bus
            # arbiter.bus is Out (initiator), slave_bus is In (target)
            m.d.comb += [
                # AW channel: arbiter → slave
                slave_bus.awaddr.eq(arb.bus.awaddr),
                slave_bus.awprot.eq(arb.bus.awprot),
                slave_bus.awvalid.eq(arb.bus.awvalid),
                arb.bus.awready.eq(slave_bus.awready),
                # W channel: arbiter → slave
                slave_bus.wdata.eq(arb.bus.wdata),
                slave_bus.wstrb.eq(arb.bus.wstrb),
                slave_bus.wvalid.eq(arb.bus.wvalid),
                arb.bus.wready.eq(slave_bus.wready),
                # B channel: slave → arbiter
                arb.bus.bresp.eq(slave_bus.bresp),
                arb.bus.bvalid.eq(slave_bus.bvalid),
                slave_bus.bready.eq(arb.bus.bready),
                # AR channel: arbiter → slave
                slave_bus.araddr.eq(arb.bus.araddr),
                slave_bus.arprot.eq(arb.bus.arprot),
                slave_bus.arvalid.eq(arb.bus.arvalid),
                arb.bus.arready.eq(slave_bus.arready),
                # R channel: slave → arbiter
                arb.bus.rdata.eq(slave_bus.rdata),
                arb.bus.rresp.eq(slave_bus.rresp),
                arb.bus.rvalid.eq(slave_bus.rvalid),
                slave_bus.rready.eq(arb.bus.rready),
            ]

        return m
