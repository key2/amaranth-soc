"""AXI4-Lite and AXI4 Full NxM crossbar interconnects.

Composes N decoders (one per master) and M arbiters (one per slave)
to create a full NxM crossbar fabric.
"""

from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out, connect, flipped

from amaranth_soc.memory import MemoryMap

from .bus import AXI4LiteSignature, AXI4LiteInterface, AXI4Signature, AXI4Interface
from .decoder import AXI4LiteDecoder, AXI4Decoder
from .arbiter import AXI4LiteArbiter, AXI4Arbiter


__all__ = ["AXI4LiteCrossbar", "AXI4Crossbar"]


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


class AXI4Crossbar(wiring.Component):
    """AXI4 Full crossbar interconnect.

    Composes AXI4 Decoders and Arbiters to create an N×M crossbar.

    Each manager gets its own decoder (for address routing).
    Each subordinate gets its own arbiter (for manager selection).

    The crossbar is built by:
    1. Creating N decoders (one per manager), each with M subordinate windows
    2. Creating M arbiters (one per subordinate), each with N manager inputs
    3. Wiring decoder[i].sub[j] → arbiter[j].manager[i]

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
        self._alignment = alignment
        self._managers = []
        self._subordinates = []
        self._built = False

        super().__init__({})

    @property
    def addr_width(self):
        return self._addr_width

    @property
    def data_width(self):
        return self._data_width

    @property
    def id_width(self):
        return self._id_width

    def add_manager(self, bus, *, name=None):
        """Add a manager (master) port.

        Parameters
        ----------
        bus : AXI4Interface
            The manager bus interface to connect.
        name : str or None
            Optional name for this manager.
        """
        if self._built:
            raise RuntimeError("Cannot add managers after elaborate() has been called")
        if isinstance(bus, wiring.FlippedInterface):
            bus_unflipped = flipped(bus)
        else:
            bus_unflipped = bus
        if not isinstance(bus_unflipped, AXI4Interface):
            raise TypeError(f"Manager bus must be an instance of AXI4Interface, not "
                            f"{bus_unflipped!r}")
        if bus.data_width != self._data_width:
            raise ValueError(f"Manager bus has data width {bus.data_width}, which is "
                             f"not the same as crossbar data width {self._data_width}")
        if bus.id_width != self._id_width:
            raise ValueError(f"Manager bus has ID width {bus.id_width}, which is "
                             f"not the same as crossbar ID width {self._id_width}")
        idx = len(self._managers)
        if name is None:
            name = f"manager_{idx}"
        self._managers.append((bus, name))

    def add_subordinate(self, bus, *, name=None, addr=None):
        """Add a subordinate (slave) port with address mapping.

        Parameters
        ----------
        bus : AXI4Interface
            The subordinate bus interface to connect.
        name : str or None
            Name for this subordinate in the memory map.
        addr : int or None
            Base address. If None, auto-allocated.
        """
        if self._built:
            raise RuntimeError("Cannot add subordinates after elaborate() has been called")
        if isinstance(bus, wiring.FlippedInterface):
            bus_unflipped = flipped(bus)
        else:
            bus_unflipped = bus
        if not isinstance(bus_unflipped, AXI4Interface):
            raise TypeError(f"Subordinate bus must be an instance of AXI4Interface, not "
                            f"{bus_unflipped!r}")
        if bus.data_width != self._data_width:
            raise ValueError(f"Subordinate bus has data width {bus.data_width}, which is "
                             f"not the same as crossbar data width {self._data_width}")
        if bus.id_width != self._id_width:
            raise ValueError(f"Subordinate bus has ID width {bus.id_width}, which is "
                             f"not the same as crossbar ID width {self._id_width}")
        idx = len(self._subordinates)
        if name is None:
            name = f"subordinate_{idx}"
        self._subordinates.append((bus, name, addr))

    def elaborate(self, platform):
        m = Module()
        self._built = True

        n_managers = len(self._managers)
        n_subordinates = len(self._subordinates)
        has_id = self._id_width > 0

        if n_managers == 0 or n_subordinates == 0:
            return m

        # --- Create one decoder per manager ---
        decoders = []
        for i, (mgr_bus, mgr_name) in enumerate(self._managers):
            dec = AXI4Decoder(addr_width=self._addr_width,
                              data_width=self._data_width,
                              id_width=self._id_width,
                              alignment=self._alignment)
            m.submodules[f"dec_{mgr_name}"] = dec
            decoders.append(dec)

        # --- Create one arbiter per subordinate ---
        arbiters = []
        for j, (sub_bus, sub_name, sub_addr) in enumerate(self._subordinates):
            sub_aw = sub_bus.memory_map.addr_width
            arb = AXI4Arbiter(addr_width=sub_aw,
                              data_width=self._data_width,
                              id_width=self._id_width)
            m.submodules[f"arb_{sub_name}"] = arb
            arbiters.append(arb)

        # --- Create intermediate interfaces for decoder→arbiter connections ---
        inter_buses = {}
        for i in range(n_managers):
            for j, (sub_bus, sub_name, sub_addr) in enumerate(self._subordinates):
                sub_map = sub_bus.memory_map
                sub_aw = sub_map.addr_width
                inter = AXI4Interface(addr_width=sub_aw,
                                      data_width=self._data_width,
                                      id_width=self._id_width,
                                      path=["xbar", f"m{i}_s{j}"])
                inter.memory_map = MemoryMap(addr_width=sub_aw,
                                             data_width=sub_map.data_width)
                inter_buses[(i, j)] = inter

        # --- Add subordinate windows to each decoder ---
        for i, dec in enumerate(decoders):
            for j, (sub_bus, sub_name, sub_addr) in enumerate(self._subordinates):
                inter = inter_buses[(i, j)]
                dec.add(inter, name=f"{sub_name}", addr=sub_addr)

        # --- Add manager inputs to each arbiter ---
        for j, arb in enumerate(arbiters):
            for i in range(n_managers):
                inter = inter_buses[(i, j)]
                arb.add(inter, name=f"m{i}")

        # --- Wire manager buses to decoder inputs ---
        for i, (mgr_bus, mgr_name) in enumerate(self._managers):
            dec = decoders[i]
            # AW channel: manager → decoder
            aw_signals = [
                dec.bus.awaddr.eq(mgr_bus.awaddr),
                dec.bus.awprot.eq(mgr_bus.awprot),
                dec.bus.awlen.eq(mgr_bus.awlen),
                dec.bus.awsize.eq(mgr_bus.awsize),
                dec.bus.awburst.eq(mgr_bus.awburst),
                dec.bus.awlock.eq(mgr_bus.awlock),
                dec.bus.awcache.eq(mgr_bus.awcache),
                dec.bus.awqos.eq(mgr_bus.awqos),
                dec.bus.awregion.eq(mgr_bus.awregion),
                dec.bus.awvalid.eq(mgr_bus.awvalid),
                mgr_bus.awready.eq(dec.bus.awready),
            ]
            if has_id:
                aw_signals.append(dec.bus.awid.eq(mgr_bus.awid))
            m.d.comb += aw_signals

            # W channel: manager → decoder
            m.d.comb += [
                dec.bus.wdata.eq(mgr_bus.wdata),
                dec.bus.wstrb.eq(mgr_bus.wstrb),
                dec.bus.wlast.eq(mgr_bus.wlast),
                dec.bus.wvalid.eq(mgr_bus.wvalid),
                mgr_bus.wready.eq(dec.bus.wready),
            ]

            # B channel: decoder → manager
            b_signals = [
                mgr_bus.bresp.eq(dec.bus.bresp),
                mgr_bus.bvalid.eq(dec.bus.bvalid),
                dec.bus.bready.eq(mgr_bus.bready),
            ]
            if has_id:
                b_signals.append(mgr_bus.bid.eq(dec.bus.bid))
            m.d.comb += b_signals

            # AR channel: manager → decoder
            ar_signals = [
                dec.bus.araddr.eq(mgr_bus.araddr),
                dec.bus.arprot.eq(mgr_bus.arprot),
                dec.bus.arlen.eq(mgr_bus.arlen),
                dec.bus.arsize.eq(mgr_bus.arsize),
                dec.bus.arburst.eq(mgr_bus.arburst),
                dec.bus.arlock.eq(mgr_bus.arlock),
                dec.bus.arcache.eq(mgr_bus.arcache),
                dec.bus.arqos.eq(mgr_bus.arqos),
                dec.bus.arregion.eq(mgr_bus.arregion),
                dec.bus.arvalid.eq(mgr_bus.arvalid),
                mgr_bus.arready.eq(dec.bus.arready),
            ]
            if has_id:
                ar_signals.append(dec.bus.arid.eq(mgr_bus.arid))
            m.d.comb += ar_signals

            # R channel: decoder → manager
            r_signals = [
                mgr_bus.rdata.eq(dec.bus.rdata),
                mgr_bus.rresp.eq(dec.bus.rresp),
                mgr_bus.rlast.eq(dec.bus.rlast),
                mgr_bus.rvalid.eq(dec.bus.rvalid),
                dec.bus.rready.eq(mgr_bus.rready),
            ]
            if has_id:
                r_signals.append(mgr_bus.rid.eq(dec.bus.rid))
            m.d.comb += r_signals

        # --- Wire arbiter outputs to subordinate buses ---
        for j, (sub_bus, sub_name, sub_addr) in enumerate(self._subordinates):
            arb = arbiters[j]
            # AW channel: arbiter → subordinate
            aw_signals = [
                sub_bus.awaddr.eq(arb.bus.awaddr),
                sub_bus.awprot.eq(arb.bus.awprot),
                sub_bus.awlen.eq(arb.bus.awlen),
                sub_bus.awsize.eq(arb.bus.awsize),
                sub_bus.awburst.eq(arb.bus.awburst),
                sub_bus.awlock.eq(arb.bus.awlock),
                sub_bus.awcache.eq(arb.bus.awcache),
                sub_bus.awqos.eq(arb.bus.awqos),
                sub_bus.awregion.eq(arb.bus.awregion),
                sub_bus.awvalid.eq(arb.bus.awvalid),
                arb.bus.awready.eq(sub_bus.awready),
            ]
            if has_id:
                aw_signals.append(sub_bus.awid.eq(arb.bus.awid))
            m.d.comb += aw_signals

            # W channel: arbiter → subordinate
            m.d.comb += [
                sub_bus.wdata.eq(arb.bus.wdata),
                sub_bus.wstrb.eq(arb.bus.wstrb),
                sub_bus.wlast.eq(arb.bus.wlast),
                sub_bus.wvalid.eq(arb.bus.wvalid),
                arb.bus.wready.eq(sub_bus.wready),
            ]

            # B channel: subordinate → arbiter
            b_signals = [
                arb.bus.bresp.eq(sub_bus.bresp),
                arb.bus.bvalid.eq(sub_bus.bvalid),
                sub_bus.bready.eq(arb.bus.bready),
            ]
            if has_id:
                b_signals.append(arb.bus.bid.eq(sub_bus.bid))
            m.d.comb += b_signals

            # AR channel: arbiter → subordinate
            ar_signals = [
                sub_bus.araddr.eq(arb.bus.araddr),
                sub_bus.arprot.eq(arb.bus.arprot),
                sub_bus.arlen.eq(arb.bus.arlen),
                sub_bus.arsize.eq(arb.bus.arsize),
                sub_bus.arburst.eq(arb.bus.arburst),
                sub_bus.arlock.eq(arb.bus.arlock),
                sub_bus.arcache.eq(arb.bus.arcache),
                sub_bus.arqos.eq(arb.bus.arqos),
                sub_bus.arregion.eq(arb.bus.arregion),
                sub_bus.arvalid.eq(arb.bus.arvalid),
                arb.bus.arready.eq(sub_bus.arready),
            ]
            if has_id:
                ar_signals.append(sub_bus.arid.eq(arb.bus.arid))
            m.d.comb += ar_signals

            # R channel: subordinate → arbiter
            r_signals = [
                arb.bus.rdata.eq(sub_bus.rdata),
                arb.bus.rresp.eq(sub_bus.rresp),
                arb.bus.rlast.eq(sub_bus.rlast),
                arb.bus.rvalid.eq(sub_bus.rvalid),
                sub_bus.rready.eq(arb.bus.rready),
            ]
            if has_id:
                r_signals.append(arb.bus.rid.eq(sub_bus.rid))
            m.d.comb += r_signals

        return m
