"""Bus handler abstraction for SoC builder.

Provides an abstract base class and concrete implementations for different
bus standards (AXI4-Lite, Wishbone), encapsulating bus-specific logic for
decoder creation, SRAM creation, and upstream bus wiring.
"""

from abc import ABC, abstractmethod


__all__ = ["BusHandler", "AXI4LiteBusHandler", "WishboneBusHandler"]


class BusHandler(ABC):
    """Abstract base class for bus-standard-specific SoC operations.

    Parameters
    ----------
    addr_width : int
        System bus address width.
    data_width : int
        System bus data width.
    """

    def __init__(self, *, addr_width, data_width):
        if not isinstance(addr_width, int) or addr_width <= 0:
            raise ValueError(f"addr_width must be a positive integer, not {addr_width!r}")
        if not isinstance(data_width, int) or data_width <= 0:
            raise ValueError(f"data_width must be a positive integer, not {data_width!r}")
        self._addr_width = addr_width
        self._data_width = data_width

    @property
    def addr_width(self):
        return self._addr_width

    @property
    def data_width(self):
        return self._data_width

    @abstractmethod
    def bus_signature(self):
        """Return the bus Signature for this bus standard.

        Returns
        -------
        wiring.Signature
            The appropriate bus signature.
        """
        ...

    @abstractmethod
    def create_decoder(self):
        """Create a bus decoder component.

        Returns
        -------
        wiring.Component
            The bus decoder.
        """
        ...

    @abstractmethod
    def create_sram(self, *, size, writable, init=()):
        """Create an SRAM component for this bus standard.

        Parameters
        ----------
        size : int
            SRAM size in bytes (power of 2).
        writable : bool
            Whether the SRAM is writable.
        init : iterable
            Initial memory contents.

        Returns
        -------
        wiring.Component
            The SRAM component.
        """
        ...

    @abstractmethod
    def get_sram_bus(self, sram):
        """Return the bus interface from an SRAM component.

        Parameters
        ----------
        sram : wiring.Component
            The SRAM component.

        Returns
        -------
        The bus interface of the SRAM.
        """
        ...

    @abstractmethod
    def connect_upstream(self, m, soc_bus, decoder_bus):
        """Wire the SoC's upstream bus port to the decoder's bus.

        Parameters
        ----------
        m : Module
            The Amaranth module being elaborated.
        soc_bus : interface
            The SoC component's bus interface (In direction).
        decoder_bus : interface
            The decoder's bus interface.
        """
        ...


class AXI4LiteBusHandler(BusHandler):
    """Bus handler for AXI4-Lite bus standard.

    Parameters
    ----------
    addr_width : int
        AXI4-Lite address width.
    data_width : int
        AXI4-Lite data width (32 or 64).
    """

    def bus_signature(self):
        from ..axi.bus import AXI4LiteSignature
        return AXI4LiteSignature(
            addr_width=self._addr_width,
            data_width=self._data_width,
        )

    def create_decoder(self):
        from ..axi.decoder import AXI4LiteDecoder
        return AXI4LiteDecoder(
            addr_width=self._addr_width,
            data_width=self._data_width,
        )

    def create_sram(self, *, size, writable, init=()):
        from ..axi.sram import AXI4LiteSRAM
        return AXI4LiteSRAM(
            size=size,
            data_width=self._data_width,
            writable=writable,
            init=init,
        )

    def get_sram_bus(self, sram):
        return sram.bus

    def connect_upstream(self, m, soc_bus, decoder_bus):
        """Wire AXI4-Lite 5-channel signals between SoC port and decoder.

        This performs explicit signal-by-signal wiring for all five AXI4-Lite
        channels (AW, W, B, AR, R).
        """
        m.d.comb += [
            # Write address channel
            decoder_bus.awaddr.eq(soc_bus.awaddr),
            decoder_bus.awprot.eq(soc_bus.awprot),
            decoder_bus.awvalid.eq(soc_bus.awvalid),
            soc_bus.awready.eq(decoder_bus.awready),
            # Write data channel
            decoder_bus.wdata.eq(soc_bus.wdata),
            decoder_bus.wstrb.eq(soc_bus.wstrb),
            decoder_bus.wvalid.eq(soc_bus.wvalid),
            soc_bus.wready.eq(decoder_bus.wready),
            # Write response channel
            soc_bus.bresp.eq(decoder_bus.bresp),
            soc_bus.bvalid.eq(decoder_bus.bvalid),
            decoder_bus.bready.eq(soc_bus.bready),
            # Read address channel
            decoder_bus.araddr.eq(soc_bus.araddr),
            decoder_bus.arprot.eq(soc_bus.arprot),
            decoder_bus.arvalid.eq(soc_bus.arvalid),
            soc_bus.arready.eq(decoder_bus.arready),
            # Read data channel
            soc_bus.rdata.eq(decoder_bus.rdata),
            soc_bus.rresp.eq(decoder_bus.rresp),
            soc_bus.rvalid.eq(decoder_bus.rvalid),
            decoder_bus.rready.eq(soc_bus.rready),
        ]


class WishboneBusHandler(BusHandler):
    """Bus handler for Wishbone bus standard.

    Parameters
    ----------
    addr_width : int
        Wishbone address width.
    data_width : int
        Wishbone data width (8, 16, 32, or 64).
    granularity : int or None
        Wishbone granularity. Defaults to data_width.
    features : frozenset
        Optional Wishbone features.
    """

    def __init__(self, *, addr_width, data_width, granularity=None, features=frozenset()):
        super().__init__(addr_width=addr_width, data_width=data_width)
        self._granularity = granularity
        self._features = frozenset(features)

    @property
    def granularity(self):
        return self._granularity

    @property
    def features(self):
        return self._features

    def bus_signature(self):
        from ..wishbone.bus import Signature as WBSignature
        return WBSignature(
            addr_width=self._addr_width,
            data_width=self._data_width,
            granularity=self._granularity,
            features=self._features,
        )

    def create_decoder(self):
        from ..wishbone.bus import Decoder as WBDecoder
        return WBDecoder(
            addr_width=self._addr_width,
            data_width=self._data_width,
            granularity=self._granularity,
            features=self._features,
        )

    def create_sram(self, *, size, writable, init=()):
        from ..wishbone.sram import WishboneSRAM
        return WishboneSRAM(
            size=size,
            data_width=self._data_width,
            granularity=self._granularity,
            writable=writable,
            init=init,
        )

    def get_sram_bus(self, sram):
        return sram.wb_bus

    def connect_upstream(self, m, soc_bus, decoder_bus):
        """Wire Wishbone bus using amaranth.lib.wiring.connect().

        The SoC bus port (In direction) acts as the initiator, and the
        decoder bus port (also In direction) acts as the target. We use
        flipped() on the SoC bus to present it as an initiator (Out direction)
        for the connect() call.
        """
        from amaranth.lib.wiring import connect, flipped
        connect(m, flipped(soc_bus), decoder_bus)
