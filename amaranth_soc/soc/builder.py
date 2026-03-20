"""Bus-agnostic SoC builder and SoC component."""

from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out, connect, flipped
from amaranth.utils import exact_log2

from amaranth_soc import csr
from amaranth_soc.memory import MemoryMap

from .. import BusStandard
from ..periph.intc import InterruptController
from .bus_handler import AXI4LiteBusHandler, WishboneBusHandler
from .csr_handler import CSRHandler
from .irq_handler import IRQHandler


__all__ = ["SoCBuilder", "SoC"]


class SoCBuilder:
    """Bus-agnostic SoC builder.

    A configuration object that collects SoC components (ROM, RAM, peripherals)
    and produces a :class:`SoC` component via :meth:`build`.

    Parameters
    ----------
    bus_standard : BusStandard
        System bus standard (WISHBONE, AXI4_LITE, AXI4).
    bus_addr_width : int
        System bus address width.
    bus_data_width : int
        System bus data width.
    csr_data_width : int
        CSR bus data width (default 8).
    csr_addr_width : int
        CSR bus address width (default 14).
    n_irqs : int
        Number of IRQ lines (default 32).
    """

    def __init__(self, *, bus_standard, bus_addr_width, bus_data_width,
                 csr_data_width=8, csr_addr_width=14, n_irqs=32):
        if not isinstance(bus_standard, BusStandard):
            raise TypeError(f"bus_standard must be a BusStandard, not {bus_standard!r}")
        if not isinstance(bus_addr_width, int) or bus_addr_width <= 0:
            raise ValueError(f"bus_addr_width must be a positive integer, not {bus_addr_width!r}")
        if not isinstance(bus_data_width, int) or bus_data_width <= 0:
            raise ValueError(f"bus_data_width must be a positive integer, not {bus_data_width!r}")

        self._bus_standard = bus_standard
        self._bus_addr_width = bus_addr_width
        self._bus_data_width = bus_data_width
        self._csr_data_width = csr_data_width
        self._csr_addr_width = csr_addr_width
        self._n_irqs = n_irqs
        self._rom = None
        self._ram = None
        self._peripherals = []
        self._cpu = None

    @property
    def bus_standard(self):
        return self._bus_standard

    @property
    def bus_addr_width(self):
        return self._bus_addr_width

    @property
    def bus_data_width(self):
        return self._bus_data_width

    @property
    def csr_data_width(self):
        return self._csr_data_width

    @property
    def csr_addr_width(self):
        return self._csr_addr_width

    @property
    def n_irqs(self):
        return self._n_irqs

    def add_rom(self, *, name="rom", size, init=None, addr=None):
        """Add ROM (read-only SRAM).

        Parameters
        ----------
        name : str
            Name for the ROM region.
        size : int
            Size in bytes (must be power of 2).
        init : iterable, optional
            Initial memory contents.
        addr : int, optional
            Base address. Auto-allocated if None.

        Returns
        -------
        self
            For method chaining.
        """
        self._rom = {"name": name, "size": size, "init": init, "addr": addr}
        return self

    def add_ram(self, *, name="ram", size, addr=None):
        """Add RAM (read-write SRAM).

        Parameters
        ----------
        name : str
            Name for the RAM region.
        size : int
            Size in bytes (must be power of 2).
        addr : int, optional
            Base address. Auto-allocated if None.

        Returns
        -------
        self
            For method chaining.
        """
        self._ram = {"name": name, "size": size, "addr": addr}
        return self

    def add_peripheral(self, peripheral, *, name, addr=None, irq=None):
        """Add a peripheral with CSR interface.

        Parameters
        ----------
        peripheral : wiring.Component
            The peripheral component (must have a ``bus`` CSR interface).
        name : str
            Name for the peripheral.
        addr : int, optional
            Base address. Auto-allocated if None.
        irq : int, optional
            IRQ number assignment.

        Returns
        -------
        self
            For method chaining.
        """
        self._peripherals.append({
            "peripheral": peripheral,
            "name": name,
            "addr": addr,
            "irq": irq,
        })
        return self

    def build(self):
        """Build the SoC and return a SoC component.

        Returns
        -------
        SoC
            The built SoC component.
        """
        return SoC(self)


class SoC(wiring.Component):
    """Built SoC component.

    Created by :meth:`SoCBuilder.build`. Contains the bus fabric,
    memory, peripherals, and interrupt controller.

    This is a configuration/metadata holder. The actual hardware
    elaboration happens in :meth:`elaborate`.

    Parameters
    ----------
    builder : SoCBuilder
        The builder configuration to use.
    """

    def __init__(self, builder):
        if not isinstance(builder, SoCBuilder):
            raise TypeError(f"Expected SoCBuilder, not {builder!r}")

        self._builder = builder
        self._bus_standard = builder.bus_standard
        self._bus_addr_width = builder.bus_addr_width
        self._bus_data_width = builder.bus_data_width
        self._csr_data_width = builder.csr_data_width
        self._csr_addr_width = builder.csr_addr_width
        self._n_irqs = builder.n_irqs
        self._rom_config = builder._rom
        self._ram_config = builder._ram
        self._peripherals = list(builder._peripherals)

        # Create the appropriate bus handler
        if self._bus_standard == BusStandard.AXI4_LITE:
            self._bus_handler = AXI4LiteBusHandler(
                addr_width=self._bus_addr_width,
                data_width=self._bus_data_width,
            )
        elif self._bus_standard == BusStandard.WISHBONE:
            self._bus_handler = WishboneBusHandler(
                addr_width=self._bus_addr_width,
                data_width=self._bus_data_width,
            )
        else:
            raise NotImplementedError(
                f"Bus standard {self._bus_standard} is not yet supported by SoC builder"
            )

        # Create CSR handler
        self._csr_handler = CSRHandler(
            csr_addr_width=self._csr_addr_width,
            csr_data_width=self._csr_data_width,
            bus_standard=self._bus_standard,
            bus_data_width=self._bus_data_width,
        )

        # Register peripherals with CSR handler
        for periph_cfg in self._peripherals:
            self._csr_handler.add_peripheral(
                periph_cfg["peripheral"], name=periph_cfg["name"]
            )

        # Create IRQ handler
        self._irq_handler = IRQHandler(
            n_irqs=self._n_irqs,
            csr_data_width=self._csr_data_width,
        )

        # Register IRQ assignments
        for periph_cfg in self._peripherals:
            irq_num = periph_cfg.get("irq")
            if irq_num is not None:
                self._irq_handler.assign_irq(
                    periph_cfg["peripheral"], irq_num=irq_num
                )

        # Build the signature based on bus handler
        bus_sig = self._bus_handler.bus_signature()

        super().__init__({
            "bus": In(bus_sig),
            "irq_out": Out(1),
        })

    @property
    def bus_standard(self):
        return self._bus_standard

    @property
    def bus_handler(self):
        """The bus handler used by this SoC."""
        return self._bus_handler

    @property
    def csr_handler(self):
        """The CSR handler used by this SoC."""
        return self._csr_handler

    @property
    def irq_handler(self):
        """The IRQ handler used by this SoC."""
        return self._irq_handler

    def elaborate(self, platform):
        m = Module()

        # Create the main bus decoder via bus handler
        decoder = self._bus_handler.create_decoder()
        m.submodules.decoder = decoder

        # Add ROM if configured
        if self._rom_config is not None:
            rom_cfg = self._rom_config
            rom = self._bus_handler.create_sram(
                size=rom_cfg["size"],
                writable=False,
                init=rom_cfg["init"] or (),
            )
            m.submodules.rom = rom
            decoder.add(
                self._bus_handler.get_sram_bus(rom),
                name=rom_cfg["name"],
                addr=rom_cfg["addr"],
            )

        # Add RAM if configured
        if self._ram_config is not None:
            ram_cfg = self._ram_config
            ram = self._bus_handler.create_sram(
                size=ram_cfg["size"],
                writable=True,
            )
            m.submodules.ram = ram
            decoder.add(
                self._bus_handler.get_sram_bus(ram),
                name=ram_cfg["name"],
                addr=ram_cfg["addr"],
            )

        # Add peripherals via CSR handler
        if self._csr_handler.has_peripherals:
            bridge_bus = self._csr_handler.elaborate(m)
            decoder.add(bridge_bus, name="csr")

        # Create interrupt controller via IRQ handler
        self._irq_handler.elaborate(m, self.irq_out)

        # Connect upstream bus to decoder via bus handler
        self._bus_handler.connect_upstream(m, self.bus, decoder.bus)

        # Store memory map for export
        self.bus.memory_map = decoder.bus.memory_map

        return m
