"""CSR management handler for SoC builder.

Manages CSR peripheral registration, decoder creation, and bridge
instantiation for connecting CSR peripherals to the system bus.
"""

__all__ = ["CSRHandler"]


class CSRHandler:
    """Handles CSR peripheral registration and bridge creation.

    Parameters
    ----------
    csr_addr_width : int
        CSR bus address width.
    csr_data_width : int
        CSR bus data width.
    bus_standard : BusStandard
        The system bus standard (determines which bridge to use).
    bus_data_width : int
        System bus data width (passed to the bridge).
    """

    def __init__(self, *, csr_addr_width, csr_data_width, bus_standard, bus_data_width):
        self._csr_addr_width = csr_addr_width
        self._csr_data_width = csr_data_width
        self._bus_standard = bus_standard
        self._bus_data_width = bus_data_width
        self._peripherals = []

    def add_peripheral(self, peripheral, *, name):
        """Register a peripheral with a CSR interface.

        Parameters
        ----------
        peripheral : wiring.Component
            The peripheral component (must have a ``bus`` CSR interface).
        name : str
            Name for the peripheral.
        """
        self._peripherals.append({"peripheral": peripheral, "name": name})

    @property
    def has_peripherals(self):
        """Whether any peripherals have been registered."""
        return len(self._peripherals) > 0

    def elaborate(self, m):
        """Create CSR decoder, add peripherals, create bridge, return bus interface.

        Parameters
        ----------
        m : Module
            The Amaranth module being elaborated.

        Returns
        -------
        interface
            The bridge's bus interface (AXI4-Lite or Wishbone) to be added
            to the system bus decoder.
        """
        from amaranth_soc import csr
        from .. import BusStandard

        # Create CSR decoder for all peripherals
        csr_decoder = csr.Decoder(
            addr_width=self._csr_addr_width,
            data_width=self._csr_data_width,
        )

        for periph_cfg in self._peripherals:
            periph = periph_cfg["peripheral"]
            name = periph_cfg["name"]
            csr_decoder.add(periph.bus, name=name)
            m.submodules[f"periph_{name}"] = periph

        m.submodules.csr_decoder = csr_decoder

        # Create the appropriate bridge based on bus standard
        if self._bus_standard == BusStandard.AXI4_LITE:
            from ..csr.axi_lite import AXI4LiteCSRBridge
            csr_bridge = AXI4LiteCSRBridge(
                csr_decoder.bus,
                data_width=self._bus_data_width,
                name="csr",
            )
            m.submodules.csr_bridge = csr_bridge
            return csr_bridge.axi_bus

        elif self._bus_standard == BusStandard.WISHBONE:
            from ..csr.wishbone import WishboneCSRBridge
            csr_bridge = WishboneCSRBridge(
                csr_decoder.bus,
                data_width=self._bus_data_width,
                name="csr",
            )
            m.submodules.csr_bridge = csr_bridge
            return csr_bridge.wb_bus

        else:
            raise NotImplementedError(
                f"CSR bridge for bus standard {self._bus_standard} is not yet supported"
            )
