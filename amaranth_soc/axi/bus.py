import enum

from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.utils import exact_log2

from amaranth_soc.memory import MemoryMap


__all__ = [
    "AXIResp", "AXIBurst", "AXISize",
    "AXI4LiteSignature", "AXI4LiteInterface",
    "AXI4Signature", "AXI4Interface",
]


class AXIResp(enum.IntEnum):
    """AXI response type."""
    OKAY   = 0b00
    EXOKAY = 0b01
    SLVERR = 0b10
    DECERR = 0b11


class AXIBurst(enum.IntEnum):
    """AXI burst type."""
    FIXED = 0b00
    INCR  = 0b01
    WRAP  = 0b10


class AXISize(enum.IntEnum):
    """AXI transfer size encoding."""
    B1   = 0b000  # 1 byte
    B2   = 0b001  # 2 bytes
    B4   = 0b010  # 4 bytes
    B8   = 0b011  # 8 bytes
    B16  = 0b100  # 16 bytes
    B32  = 0b101  # 32 bytes
    B64  = 0b110  # 64 bytes
    B128 = 0b111  # 128 bytes


class AXI4LiteSignature(wiring.Signature):
    """AXI4-Lite interface signature.

    Parameters
    ----------
    addr_width : int
        Width of the address signals (``awaddr``, ``araddr``).
    data_width : ``32`` or ``64``
        Width of the data signals (``wdata``, ``rdata``). Per the AXI4-Lite specification,
        only 32-bit and 64-bit data widths are supported.

    Interface attributes
    --------------------
    Write Address channel (AW):
        awaddr, awprot, awvalid, awready
    Write Data channel (W):
        wdata, wstrb, wvalid, wready
    Write Response channel (B):
        bresp, bvalid, bready
    Read Address channel (AR):
        araddr, arprot, arvalid, arready
    Read Data channel (R):
        rdata, rresp, rvalid, rready
    """
    def __init__(self, *, addr_width, data_width):
        if not isinstance(addr_width, int) or addr_width < 0:
            raise TypeError(f"Address width must be a non-negative integer, not {addr_width!r}")
        if data_width not in (32, 64):
            raise ValueError(f"Data width must be one of 32, 64, not {data_width!r}")

        self._addr_width = addr_width
        self._data_width = data_width

        members = {
            # Write Address channel (AW)
            "awaddr":  Out(addr_width),
            "awprot":  Out(3),
            "awvalid": Out(1),
            "awready": In(1),
            # Write Data channel (W)
            "wdata":   Out(data_width),
            "wstrb":   Out(data_width // 8),
            "wvalid":  Out(1),
            "wready":  In(1),
            # Write Response channel (B)
            "bresp":   In(2),
            "bvalid":  In(1),
            "bready":  Out(1),
            # Read Address channel (AR)
            "araddr":  Out(addr_width),
            "arprot":  Out(3),
            "arvalid": Out(1),
            "arready": In(1),
            # Read Data channel (R)
            "rdata":   In(data_width),
            "rresp":   In(2),
            "rvalid":  In(1),
            "rready":  Out(1),
        }
        super().__init__(members)

    @property
    def addr_width(self):
        return self._addr_width

    @property
    def data_width(self):
        return self._data_width

    def create(self, *, path=None, src_loc_at=0):
        """Create a compatible interface.

        See :meth:`wiring.Signature.create` for details.

        Returns
        -------
        An :class:`AXI4LiteInterface` object using this signature.
        """
        return AXI4LiteInterface(addr_width=self.addr_width, data_width=self.data_width,
                                 path=path, src_loc_at=1 + src_loc_at)

    def __eq__(self, other):
        """Compare signatures.

        Two signatures are equal if they have the same address width and data width.
        """
        return (isinstance(other, AXI4LiteSignature) and
                self.addr_width == other.addr_width and
                self.data_width == other.data_width)

    def __repr__(self):
        return f"AXI4LiteSignature({self.members!r})"


class AXI4LiteInterface(wiring.PureInterface):
    """AXI4-Lite bus interface.

    Parameters
    ----------
    addr_width : :class:`int`
        Width of the address signals. See :class:`AXI4LiteSignature`.
    data_width : :class:`int`
        Width of the data signals. See :class:`AXI4LiteSignature`.
    path : iter(:class:`str`)
        Path to this interface. Optional. See :class:`wiring.PureInterface`.

    Attributes
    ----------
    memory_map : :class:`MemoryMap`
        Memory map of the bus. Optional.
    """
    def __init__(self, *, addr_width, data_width, path=None, src_loc_at=0):
        super().__init__(AXI4LiteSignature(addr_width=addr_width, data_width=data_width),
                         path=path, src_loc_at=1 + src_loc_at)
        self._memory_map = None

    @property
    def addr_width(self):
        return self.signature.addr_width

    @property
    def data_width(self):
        return self.signature.data_width

    @property
    def memory_map(self):
        if self._memory_map is None:
            raise AttributeError(f"{self!r} does not have a memory map")
        return self._memory_map

    @memory_map.setter
    def memory_map(self, memory_map):
        if not isinstance(memory_map, MemoryMap):
            raise TypeError(f"Memory map must be an instance of MemoryMap, not {memory_map!r}")
        # AXI4-Lite uses byte addressing. The memory map data_width can be:
        # - 8 (byte-addressable, standard for SoC integration with MemoryMap)
        # - Equal to bus data_width (word-addressed map)
        if memory_map.data_width not in (8, self.data_width):
            raise ValueError(f"Memory map has data width {memory_map.data_width}, which is "
                             f"not 8 (byte-addressable) or {self.data_width} (bus data width)")
        # AXI addresses are byte addresses, so the memory map addr_width
        # should match the interface addr_width directly.
        expected_addr_width = max(1, self.addr_width)
        if memory_map.addr_width != expected_addr_width:
            raise ValueError(f"Memory map has address width {memory_map.addr_width}, which is "
                             f"not the same as the bus interface address width "
                             f"{expected_addr_width}")
        self._memory_map = memory_map

    def __repr__(self):
        return f"AXI4LiteInterface({self.signature!r})"


class AXI4Signature(wiring.Signature):
    """AXI4 (full) interface signature.

    Parameters
    ----------
    addr_width : int
        Width of the address signals (``awaddr``, ``araddr``).
    data_width : int
        Width of the data signals (``wdata``, ``rdata``). Must be a power of 2 and >= 8.
    id_width : int
        Width of the ID signals (``awid``, ``bid``, ``arid``, ``rid``). Default 0.
        Signals with width 0 are omitted.
    user_width : dict
        Dictionary with keys ``'aw'``, ``'w'``, ``'b'``, ``'ar'``, ``'r'`` specifying the
        width of user-defined signals for each channel. Default all 0.
        Signals with width 0 are omitted.

    Interface attributes
    --------------------
    Includes all AXI4-Lite signals plus additional AXI4 signals:

    AW channel additions:
        awid, awlen, awsize, awburst, awlock, awcache, awqos, awregion, awuser
    W channel additions:
        wlast
    B channel additions:
        bid, buser
    AR channel additions:
        arid, arlen, arsize, arburst, arlock, arcache, arqos, arregion, aruser
    R channel additions:
        rid, rlast, ruser
    """
    def __init__(self, *, addr_width, data_width, id_width=0, user_width=None):
        if user_width is None:
            user_width = {"aw": 0, "w": 0, "b": 0, "ar": 0, "r": 0}

        if not isinstance(addr_width, int) or addr_width < 0:
            raise TypeError(f"Address width must be a non-negative integer, not {addr_width!r}")
        if not isinstance(data_width, int) or data_width < 8:
            raise ValueError(f"Data width must be an integer >= 8, not {data_width!r}")
        if data_width & (data_width - 1) != 0:
            raise ValueError(f"Data width must be a power of 2, not {data_width!r}")
        if not isinstance(id_width, int) or id_width < 0:
            raise TypeError(f"ID width must be a non-negative integer, not {id_width!r}")
        if not isinstance(user_width, dict):
            raise TypeError(f"User width must be a dict, not {user_width!r}")
        for key in ("aw", "w", "b", "ar", "r"):
            if key not in user_width:
                raise ValueError(f"User width dict must contain key {key!r}")
            if not isinstance(user_width[key], int) or user_width[key] < 0:
                raise TypeError(f"User width for channel {key!r} must be a non-negative integer, "
                                f"not {user_width[key]!r}")

        self._addr_width  = addr_width
        self._data_width  = data_width
        self._id_width    = id_width
        self._user_width  = dict(user_width)

        members = {}

        # Write Address channel (AW)
        members["awaddr"]  = Out(addr_width)
        members["awprot"]  = Out(3)
        members["awvalid"] = Out(1)
        members["awready"] = In(1)
        if id_width > 0:
            members["awid"] = Out(id_width)
        members["awlen"]   = Out(8)
        members["awsize"]  = Out(3)
        members["awburst"] = Out(2)
        members["awlock"]  = Out(1)
        members["awcache"] = Out(4)
        members["awqos"]   = Out(4)
        members["awregion"] = Out(4)
        if user_width["aw"] > 0:
            members["awuser"] = Out(user_width["aw"])

        # Write Data channel (W)
        members["wdata"]  = Out(data_width)
        members["wstrb"]  = Out(data_width // 8)
        members["wvalid"] = Out(1)
        members["wready"] = In(1)
        members["wlast"]  = Out(1)

        # Write Response channel (B)
        members["bresp"]  = In(2)
        members["bvalid"] = In(1)
        members["bready"] = Out(1)
        if id_width > 0:
            members["bid"] = In(id_width)
        if user_width["b"] > 0:
            members["buser"] = In(user_width["b"])

        # Read Address channel (AR)
        members["araddr"]  = Out(addr_width)
        members["arprot"]  = Out(3)
        members["arvalid"] = Out(1)
        members["arready"] = In(1)
        if id_width > 0:
            members["arid"] = Out(id_width)
        members["arlen"]   = Out(8)
        members["arsize"]  = Out(3)
        members["arburst"] = Out(2)
        members["arlock"]  = Out(1)
        members["arcache"] = Out(4)
        members["arqos"]   = Out(4)
        members["arregion"] = Out(4)
        if user_width["ar"] > 0:
            members["aruser"] = Out(user_width["ar"])

        # Read Data channel (R)
        members["rdata"]  = In(data_width)
        members["rresp"]  = In(2)
        members["rvalid"] = In(1)
        members["rready"] = Out(1)
        if id_width > 0:
            members["rid"] = In(id_width)
        members["rlast"]  = In(1)
        if user_width["r"] > 0:
            members["ruser"] = In(user_width["r"])

        super().__init__(members)

    @property
    def addr_width(self):
        return self._addr_width

    @property
    def data_width(self):
        return self._data_width

    @property
    def id_width(self):
        return self._id_width

    @property
    def user_width(self):
        return dict(self._user_width)

    def create(self, *, path=None, src_loc_at=0):
        """Create a compatible interface.

        See :meth:`wiring.Signature.create` for details.

        Returns
        -------
        An :class:`AXI4Interface` object using this signature.
        """
        return AXI4Interface(addr_width=self.addr_width, data_width=self.data_width,
                             id_width=self.id_width, user_width=self.user_width,
                             path=path, src_loc_at=1 + src_loc_at)

    def __eq__(self, other):
        """Compare signatures.

        Two signatures are equal if they have the same address width, data width, ID width,
        and user widths.
        """
        return (isinstance(other, AXI4Signature) and
                self.addr_width == other.addr_width and
                self.data_width == other.data_width and
                self.id_width == other.id_width and
                self._user_width == other._user_width)

    def __repr__(self):
        return f"AXI4Signature({self.members!r})"


class AXI4Interface(wiring.PureInterface):
    """AXI4 (full) bus interface.

    Parameters
    ----------
    addr_width : :class:`int`
        Width of the address signals. See :class:`AXI4Signature`.
    data_width : :class:`int`
        Width of the data signals. See :class:`AXI4Signature`.
    id_width : :class:`int`
        Width of the ID signals. See :class:`AXI4Signature`.
    user_width : :class:`dict`
        User signal widths per channel. See :class:`AXI4Signature`.
    path : iter(:class:`str`)
        Path to this interface. Optional. See :class:`wiring.PureInterface`.

    Attributes
    ----------
    memory_map : :class:`MemoryMap`
        Memory map of the bus. Optional.
    """
    def __init__(self, *, addr_width, data_width, id_width=0, user_width=None,
                 path=None, src_loc_at=0):
        super().__init__(AXI4Signature(addr_width=addr_width, data_width=data_width,
                                       id_width=id_width, user_width=user_width),
                         path=path, src_loc_at=1 + src_loc_at)
        self._memory_map = None

    @property
    def addr_width(self):
        return self.signature.addr_width

    @property
    def data_width(self):
        return self.signature.data_width

    @property
    def id_width(self):
        return self.signature.id_width

    @property
    def user_width(self):
        return self.signature.user_width

    @property
    def memory_map(self):
        if self._memory_map is None:
            raise AttributeError(f"{self!r} does not have a memory map")
        return self._memory_map

    @memory_map.setter
    def memory_map(self, memory_map):
        if not isinstance(memory_map, MemoryMap):
            raise TypeError(f"Memory map must be an instance of MemoryMap, not {memory_map!r}")
        if memory_map.data_width != self.data_width:
            raise ValueError(f"Memory map has data width {memory_map.data_width}, which is "
                             f"not the same as bus interface data width {self.data_width}")
        if memory_map.addr_width != max(1, self.addr_width):
            raise ValueError(f"Memory map has address width {memory_map.addr_width}, which is "
                             f"not the same as bus interface address width "
                             f"{max(1, self.addr_width)}")
        self._memory_map = memory_map

    def __repr__(self):
        return f"AXI4Interface({self.signature!r})"
