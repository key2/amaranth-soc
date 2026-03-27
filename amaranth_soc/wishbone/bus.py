from amaranth import *
from amaranth.lib import enum, wiring
from amaranth.lib.wiring import In, Out, connect, flipped
from amaranth.utils import exact_log2

from ..bus_common import Endianness
from ..memory import MemoryMap


__all__ = ["CycleType", "BurstTypeExt", "Feature", "Signature", "Interface", "Decoder", "Arbiter",
           "Crossbar"]


class CycleType(enum.Enum):
    """Wishbone Registered Feedback cycle type."""
    CLASSIC      = 0b000
    CONST_BURST  = 0b001
    INCR_BURST   = 0b010
    END_OF_BURST = 0b111


class BurstTypeExt(enum.Enum):
    """Wishbone Registered Feedback burst type extension."""
    LINEAR  = 0b00
    WRAP_4  = 0b01
    WRAP_8  = 0b10
    WRAP_16 = 0b11


class Feature(enum.Enum):
    """Optional Wishbone interface signals."""
    ERR   = "err"
    RTY   = "rty"
    STALL = "stall"
    LOCK  = "lock"
    CTI   = "cti"
    BTE   = "bte"


class Signature(wiring.Signature):
    """Wishbone interface signature.

    See the `Wishbone specification <https://opencores.org/howto/wishbone>`_ for description
    of the Wishbone signals. The ``RST_I`` and ``CLK_I`` signals are provided as a part of
    the clock domain that drives the interface.

    Parameters
    ----------
    addr_width : int
        Width of the address signal.
    data_width : ``8``, ``16``, ``32`` or ``64``
        Width of the data signals ("port size" in Wishbone terminology).
    granularity : ``8``, ``16``, ``32``, ``64`` or ``None``
        Granularity of select signals ("port granularity" in Wishbone terminology).
        Optional. If ``None`` (by default), the granularity is equal to ``data_width``.
    features : iter(:class:`Feature`)
        Selects additional signals that will be a part of this interface.
        Optional.

    Interface attributes
    --------------------
    The correspondence between the Amaranth-SoC signals and the Wishbone signals changes depending
    on whether the interface acts as an initiator or a target.

    adr : Signal(addr_width)
        Corresponds to Wishbone signal ``ADR_O`` (initiator) or ``ADR_I`` (target).
    dat_w : Signal(data_width)
        Corresponds to Wishbone signal ``DAT_O`` (initiator) or ``DAT_I`` (target).
    dat_r : Signal(data_width)
        Corresponds to Wishbone signal ``DAT_I`` (initiator) or ``DAT_O`` (target).
    sel : Signal(data_width // granularity)
        Corresponds to Wishbone signal ``SEL_O`` (initiator) or ``SEL_I`` (target).
    cyc : Signal()
        Corresponds to Wishbone signal ``CYC_O`` (initiator) or ``CYC_I`` (target).
    stb : Signal()
        Corresponds to Wishbone signal ``STB_O`` (initiator) or ``STB_I`` (target).
    we : Signal()
        Corresponds to Wishbone signal ``WE_O``  (initiator) or ``WE_I``  (target).
    ack : Signal()
        Corresponds to Wishbone signal ``ACK_I`` (initiator) or ``ACK_O`` (target).
    err : Signal()
        Optional. Corresponds to Wishbone signal ``ERR_I`` (initiator) or ``ERR_O`` (target).
    rty : Signal()
        Optional. Corresponds to Wishbone signal ``RTY_I`` (initiator) or ``RTY_O`` (target).
    stall : Signal()
        Optional. Corresponds to Wishbone signal ``STALL_I`` (initiator) or ``STALL_O`` (target).
    lock : Signal()
        Optional. Corresponds to Wishbone signal ``LOCK_O`` (initiator) or ``LOCK_I`` (target).
    cti : Signal()
        Optional. Corresponds to Wishbone signal ``CTI_O`` (initiator) or ``CTI_I`` (target).
    bte : Signal()
        Optional. Corresponds to Wishbone signal ``BTE_O`` (initiator) or ``BTE_I`` (target).
    """
    def __init__(self, *, addr_width, data_width, granularity=None, features=frozenset(),
                 endianness=Endianness.LITTLE):
        if granularity is None:
            granularity = data_width

        if not isinstance(addr_width, int) or addr_width < 0:
            raise TypeError(f"Address width must be a non-negative integer, not {addr_width!r}")
        if data_width not in (8, 16, 32, 64):
            raise ValueError(f"Data width must be one of 8, 16, 32, 64, not {data_width!r}")
        if granularity not in (8, 16, 32, 64):
            raise ValueError(f"Granularity must be one of 8, 16, 32, 64, not {granularity!r}")
        if granularity > data_width:
            raise ValueError(f"Granularity {granularity} may not be greater than data width "
                             f"{data_width}")
        for feature in features:
            Feature(feature) # raises ValueError if feature is invalid
        if not isinstance(endianness, Endianness):
            raise ValueError(f"Endianness must be an instance of Endianness, not {endianness!r}")

        self._addr_width  = addr_width
        self._data_width  = data_width
        self._granularity = granularity
        self._features    = frozenset(Feature(f) for f in features)
        self._endianness  = endianness

        members = {
            "adr":   Out(self.addr_width),
            "dat_w": Out(self.data_width),
            "dat_r": In(self.data_width),
            "sel":   Out(self.data_width // self.granularity),
            "cyc":   Out(1),
            "stb":   Out(1),
            "we":    Out(1),
            "ack":   In(1),
        }
        if Feature.ERR in self.features:
            members["err"]   = In(1)
        if Feature.RTY in self.features:
            members["rty"]   = In(1)
        if Feature.STALL in self.features:
            members["stall"] = In(1)
        if Feature.LOCK in self.features:
            members["lock"]  = Out(1)
        if Feature.CTI in self.features:
            members["cti"]   = Out(CycleType)
        if Feature.BTE in self.features:
            members["bte"]   = Out(BurstTypeExt)
        super().__init__(members)

    @property
    def addr_width(self):
        return self._addr_width

    @property
    def data_width(self):
        return self._data_width

    @property
    def granularity(self):
        return self._granularity

    @property
    def features(self):
        return self._features

    @property
    def endianness(self):
        return self._endianness

    def create(self, *, path=None, src_loc_at=0):
        """Create a compatible interface.

        See :meth:`wiring.Signature.create` for details.

        Returns
        -------
        An :class:`Interface` object using this signature.
        """
        return Interface(addr_width=self.addr_width, data_width=self.data_width,
                         granularity=self.granularity, features=self.features,
                         endianness=self.endianness,
                         path=path, src_loc_at=1 + src_loc_at)

    def __eq__(self, other):
        """Compare signatures.

        Two signatures are equal if they have the same address width, data width, granularity,
        features, and endianness.
        """
        return (isinstance(other, Signature) and
                self.addr_width == other.addr_width and
                self.data_width == other.data_width and
                self.granularity == other.granularity and
                self.features == other.features and
                self.endianness == other.endianness)

    def __repr__(self):
        return f"wishbone.Signature({self.members!r})"


class Interface(wiring.PureInterface):
    """Wishbone bus interface.

    Note that the data width of the underlying memory map of the interface is equal to port
    granularity, not port size. If port granularity is less than port size, then the address width
    of the underlying memory map is extended to reflect that.

    Parameters
    ----------
    addr_width : :class:`int`
        Width of the address signal. See :class:`Signature`.
    data_width : :class:`int`
        Width of the data signals. See :class:`Signature`.
    granularity : :class:`int`
        Granularity of select signals. Optional. See :class:`Signature`.
    features : iter(:class:`Feature`)
        Describes additional signals of this interface. Optional. See :class:`Signature`.
    path : iter(:class:`str`)
        Path to this Wishbone interface. Optional. See :class:`wiring.PureInterface`.

    Attributes
    ----------
    memory_map: :class:`MemoryMap`
        Memory map of the bus. Optional.
    """
    def __init__(self, *, addr_width, data_width, granularity=None, features=frozenset(),
                 endianness=Endianness.LITTLE, path=None, src_loc_at=0):
        super().__init__(Signature(addr_width=addr_width, data_width=data_width,
                                   granularity=granularity, features=features,
                                   endianness=endianness),
                         path=path, src_loc_at=1 + src_loc_at)
        self._memory_map = None

    @property
    def addr_width(self):
        return self.signature.addr_width

    @property
    def data_width(self):
        return self.signature.data_width

    @property
    def granularity(self):
        return self.signature.granularity

    @property
    def features(self):
        return self.signature.features

    @property
    def endianness(self):
        return self.signature.endianness

    @property
    def memory_map(self):
        if self._memory_map is None:
            raise AttributeError(f"{self!r} does not have a memory map")
        return self._memory_map

    @memory_map.setter
    def memory_map(self, memory_map):
        if not isinstance(memory_map, MemoryMap):
            raise TypeError(f"Memory map must be an instance of MemoryMap, not {memory_map!r}")
        if memory_map.data_width != self.granularity:
            raise ValueError(f"Memory map has data width {memory_map.data_width}, which is "
                             f"not the same as bus interface granularity {self.granularity}")
        granularity_bits = exact_log2(self.data_width // self.granularity)
        effective_addr_width = self.addr_width + granularity_bits
        if memory_map.addr_width != max(1, effective_addr_width):
            raise ValueError(f"Memory map has address width {memory_map.addr_width}, which is "
                             f"not the same as the bus interface effective address width "
                             f"{effective_addr_width} (= {self.addr_width} address bits + "
                             f"{granularity_bits} granularity bits)")
        self._memory_map = memory_map

    def __repr__(self):
        return f"wishbone.Interface({self.signature!r})"


class _FeatureShim(wiring.Component):
    """A connector for Wishbone bus interfaces with mismatching features."""
    def __init__(self, addr_width, data_width, granularity=None, intr_features=frozenset(),
                 sub_features=frozenset()):
        super().__init__({
            "intr_bus": In(Signature(addr_width=addr_width, data_width=data_width,
                                     granularity=granularity, features=intr_features)),
            "sub_bus": Out(Signature(addr_width=addr_width, data_width=data_width,
                                     granularity=granularity, features=sub_features))})

    def elaborate(self, platform):
        m = Module()

        m.d.comb += [
            self.sub_bus.cyc.eq(self.intr_bus.cyc),
            self.sub_bus.stb.eq(self.intr_bus.stb),
            self.sub_bus.adr.eq(self.intr_bus.adr),
            self.sub_bus.sel.eq(self.intr_bus.sel),
            self.sub_bus.we.eq(self.intr_bus.we),
            self.sub_bus.dat_w.eq(self.intr_bus.dat_w),
            self.intr_bus.dat_r.eq(self.sub_bus.dat_r)
        ]
        if hasattr(self.sub_bus, "lock"):
            m.d.comb += self.sub_bus.lock.eq(getattr(self.intr_bus, "lock", self.intr_bus.cyc))
        if hasattr(self.sub_bus, "cti"):
            m.d.comb += self.sub_bus.cti.eq(getattr(self.intr_bus, "cti", CycleType.CLASSIC))
        if hasattr(self.sub_bus, "bte"):
            m.d.comb += self.sub_bus.bte.eq(getattr(self.intr_bus, "bte", BurstTypeExt.LINEAR))
        if hasattr(self.intr_bus, "err"):
            m.d.comb += self.intr_bus.err.eq(getattr(self.sub_bus, "err", 0))
        if hasattr(self.intr_bus, "rty"):
            m.d.comb += self.intr_bus.rty.eq(getattr(self.sub_bus, "rty", 0))

        # If the initiator doesn't have ERR or RTY, connect them to ACK.
        intr_ack_fanin = self.sub_bus.ack
        if hasattr(self.sub_bus, "err") and not hasattr(self.intr_bus, "err"):
            intr_ack_fanin |= self.sub_bus.err
        if hasattr(self.sub_bus, "rty") and not hasattr(self.intr_bus, "rty"):
            intr_ack_fanin |= self.sub_bus.rty
        m.d.comb += self.intr_bus.ack.eq(intr_ack_fanin)

        sub_ack_err_rty = self.sub_bus.ack \
                        | getattr(self.sub_bus, "err", 0) \
                        | getattr(self.sub_bus, "rty", 0)

        if hasattr(self.intr_bus, "stall") and hasattr(self.sub_bus, "stall"):
            # Pipelined initiator to pipelined subordinate.
            m.d.comb += self.intr_bus.stall.eq(self.sub_bus.stall)
        elif hasattr(self.intr_bus, "stall"):
            # Pipelined initiator to standard subordinate.
            m.d.comb += self.intr_bus.stall.eq(self.intr_bus.cyc & ~sub_ack_err_rty)
        elif hasattr(self.sub_bus, "stall"):
            # Standard initiator to pipelined subordinate.
            # In pipelined mode, a new transfer is initiated every clock cycle where STB is high
            # and STALL is low. To accomodate a standard mode initiator, STB is limited to a one-
            # clock pulse until the subordinate asserts ACK, ERR or RTY.
            with m.FSM():
                with m.State("IDLE"):
                    m.d.comb += self.sub_bus.stb.eq(self.intr_bus.stb)
                    with m.If(self.intr_bus.cyc & self.intr_bus.stb & ~self.sub_bus.stall):
                        m.next = "BUSY"
                with m.State("BUSY"):
                    m.d.comb += self.sub_bus.stb.eq(0)
                    with m.If(~self.intr_bus.cyc | sub_ack_err_rty):
                        m.next = "IDLE"

        return m


class Decoder(wiring.Component):
    """Wishbone bus decoder.

    An address decoder for subordinate Wishbone buses.

    Parameters
    ----------
    addr_width : :class:`int`
        Address width. See :class:`Signature`.
    data_width : :class:`int`
        Data width. See :class:`Signature`.
    granularity : :class:`int`
        Granularity. See :class:`Signature`
    features : iter(:class:`Feature`)
        Optional signal set. See :class:`Signature`.
    alignment : int, power-of-2 exponent
        Window alignment. Optional. See :class:`..memory.MemoryMap`.

    Attributes
    ----------
    bus : :class:`Interface`
        Wishbone bus providing access to subordinate buses.
    """
    def __init__(self, *, addr_width, data_width, granularity=None, features=frozenset(),
                 alignment=0, name=None):
        if granularity is None:
            granularity = data_width
        super().__init__({"bus": In(Signature(addr_width=addr_width, data_width=data_width,
                                              granularity=granularity, features=features))})
        self.bus.memory_map = MemoryMap(
                addr_width=max(1, addr_width + exact_log2(data_width // granularity)),
                data_width=granularity, alignment=alignment)
        self._subs = dict()

    def align_to(self, alignment):
        """Align the implicit address of the next window.

        See :meth:`MemoryMap.align_to` for details.
        """
        return self.bus.memory_map.align_to(alignment)

    def add(self, sub_bus, *, name=None, addr=None, sparse=False):
        """Add a window to a subordinate bus.

        The decoder can perform either sparse or dense address translation. If dense address
        translation is used (the default), the subordinate bus must have the same data width as
        the decoder; the window will be contiguous. If sparse address translation is used,
        the subordinate bus may have data width less than the data width of the decoder;
        the window may be discontiguous. In either case, the granularity of the subordinate bus
        must be equal to or less than the granularity of the decoder.

        See :meth:`MemoryMap.add_resource` for details.
        """
        if isinstance(sub_bus, wiring.FlippedInterface):
            sub_bus_unflipped = flipped(sub_bus)
        else:
            sub_bus_unflipped = sub_bus
        if not isinstance(sub_bus_unflipped, Interface):
            raise TypeError(f"Subordinate bus must be an instance of wishbone.Interface, not "
                            f"{sub_bus_unflipped!r}")
        if sub_bus.granularity > self.bus.granularity:
            raise ValueError(f"Subordinate bus has granularity {sub_bus.granularity}, which is "
                             f"greater than the decoder granularity {self.bus.granularity}")
        if not sparse:
            if sub_bus.data_width != self.bus.data_width:
                raise ValueError(f"Subordinate bus has data width {sub_bus.data_width}, which is "
                                 f"not the same as decoder data width {self.bus.data_width} "
                                 f"(required for dense address translation)")
        else:
            if sub_bus.granularity != sub_bus.data_width:
                raise ValueError(f"Subordinate bus has data width {sub_bus.data_width}, which is "
                                 f"not the same as its granularity {sub_bus.granularity} "
                                 f"(required for sparse address translation)")

        self._subs[sub_bus.memory_map] = sub_bus
        return self.bus.memory_map.add_window(sub_bus.memory_map, name=name, addr=addr,
                                              sparse=sparse)

    def elaborate(self, platform):
        m = Module()

        # Collect all subordinate shims in order for indexed access.
        sub_shims = []
        for sub_map, sub_name, (sub_pattern, ratio) in self.bus.memory_map.window_patterns():
            sub_bus = self._subs[sub_map]
            shim = _FeatureShim(sub_bus.addr_width, sub_bus.data_width, sub_bus.granularity,
                                intr_features=self.bus.features, sub_features=sub_bus.features)
            m.submodules[f"shim_{sub_pattern.replace('-', 'x')}"] = shim
            connect(m, shim.sub_bus, sub_bus)

            m.d.comb += [
                shim.intr_bus.adr.eq(self.bus.adr << exact_log2(ratio)),
                shim.intr_bus.dat_w.eq(self.bus.dat_w),
                shim.intr_bus.sel.eq(Cat(sel.replicate(ratio) for sel in self.bus.sel)),
                shim.intr_bus.we.eq(self.bus.we),
                shim.intr_bus.stb.eq(self.bus.stb)
            ]
            if hasattr(self.bus, "lock"):
                m.d.comb += shim.intr_bus.lock.eq(self.bus.lock)
            if hasattr(self.bus, "cti"):
                m.d.comb += shim.intr_bus.cti.eq(self.bus.cti)
            if hasattr(self.bus, "bte"):
                m.d.comb += shim.intr_bus.bte.eq(self.bus.bte)

            sub_shims.append((sub_pattern, ratio, shim))

        n_subs = len(sub_shims)

        # Combinational address decode: determine which subordinate is selected.
        sub_sel = Signal(range(max(n_subs, 1)), name="sub_sel")
        sub_hit = Signal(name="sub_hit")
        with m.Switch(self.bus.adr):
            for idx, (sub_pattern, ratio, shim) in enumerate(sub_shims):
                granularity_bits = exact_log2(self.bus.data_width // self.bus.granularity)
                with m.Case(sub_pattern[:-granularity_bits if granularity_bits > 0 else None]):
                    m.d.comb += sub_sel.eq(idx)
                    m.d.comb += sub_hit.eq(1)

        # Burst-aware address locking (only when CTI feature is present).
        if hasattr(self.bus, "cti"):
            burst_active = Signal(name="burst_active")
            sub_latched = Signal(range(max(n_subs, 1)), name="sub_latched")
            sub_latched_valid = Signal(name="sub_latched_valid")

            # A burst is active when CTI indicates a burst type.
            m.d.comb += burst_active.eq(
                (self.bus.cti == CycleType.CONST_BURST) |
                (self.bus.cti == CycleType.INCR_BURST)
            )

            # Latch the subordinate on the first cycle of a burst.
            with m.If(self.bus.cyc & self.bus.stb & burst_active & ~sub_latched_valid):
                m.d.sync += sub_latched.eq(sub_sel)
                m.d.sync += sub_latched_valid.eq(1)

            # Clear latch when burst ends or cyc drops.
            with m.If(~self.bus.cyc | (self.bus.stb & (self.bus.cti == CycleType.END_OF_BURST))):
                m.d.sync += sub_latched_valid.eq(0)

            # Use latched subordinate during burst, combinational decode otherwise.
            effective_sub = Signal(range(max(n_subs, 1)), name="effective_sub")
            effective_hit = Signal(name="effective_hit")
            with m.If(sub_latched_valid & burst_active):
                m.d.comb += effective_sub.eq(sub_latched)
                m.d.comb += effective_hit.eq(1)
            with m.Else():
                m.d.comb += effective_sub.eq(sub_sel)
                m.d.comb += effective_hit.eq(sub_hit)
        else:
            effective_sub = sub_sel
            effective_hit = sub_hit

        # Route bus signals to the selected subordinate.
        with m.If(effective_hit):
            with m.Switch(effective_sub):
                for idx, (sub_pattern, ratio, shim) in enumerate(sub_shims):
                    with m.Case(idx):
                        m.d.comb += [
                            shim.intr_bus.cyc.eq(self.bus.cyc),
                            self.bus.dat_r.eq(shim.intr_bus.dat_r),
                            self.bus.ack.eq(shim.intr_bus.ack)
                        ]
                        if hasattr(self.bus, "err"):
                            m.d.comb += self.bus.err.eq(shim.intr_bus.err)
                        if hasattr(self.bus, "rty"):
                            m.d.comb += self.bus.rty.eq(shim.intr_bus.rty)
                        if hasattr(self.bus, "stall"):
                            m.d.comb += self.bus.stall.eq(shim.intr_bus.stall)

        return m


class Arbiter(wiring.Component):
    """Wishbone bus arbiter.

    A round-robin arbiter for initiators accessing a shared Wishbone bus.

    Parameters
    ----------
    addr_width : int
        Address width. See :class:`Signature`.
    data_width : int
        Data width. See :class:`Signature`.
    granularity : int
        Granularity. See :class:`Signature`
    features : iter(:class:`Feature`)
        Optional signal set. See :class:`Signature`.

    Attributes
    ----------
    bus : :class:`Interface`
        Shared Wishbone bus.
    """
    def __init__(self, *, addr_width, data_width, granularity=None, features=frozenset()):
        super().__init__({"bus": Out(Signature(addr_width=addr_width, data_width=data_width,
                                               granularity=granularity, features=features))})
        self._intrs = []

    def add(self, intr_bus):
        """Add an initiator bus to the arbiter.

        The initiator bus must have the same address width and data width as the arbiter. The
        granularity of the initiator bus must be greater than or equal to the granularity of
        the arbiter.
        """
        if not isinstance(intr_bus, Interface):
            raise TypeError(f"Initiator bus must be an instance of wishbone.Interface, not "
                            f"{intr_bus!r}")
        if intr_bus.addr_width != self.bus.addr_width:
            raise ValueError(f"Initiator bus has address width {intr_bus.addr_width}, which is "
                             f"not the same as arbiter address width {self.bus.addr_width}")
        if intr_bus.granularity < self.bus.granularity:
            raise ValueError(f"Initiator bus has granularity {intr_bus.granularity}, which is "
                             f"lesser than the arbiter granularity {self.bus.granularity}")
        if intr_bus.data_width != self.bus.data_width:
            raise ValueError(f"Initiator bus has data width {intr_bus.data_width}, which is not "
                             f"the same as arbiter data width {self.bus.data_width}")
        self._intrs.append(intr_bus)

    def elaborate(self, platform):
        m = Module()

        requests = Signal(len(self._intrs))
        grant    = Signal(range(len(self._intrs)))
        m.d.comb += requests.eq(Cat(intr_bus.cyc for intr_bus in self._intrs))

        # Lock-aware arbitration: when the granted initiator asserts LOCK,
        # do not re-arbitrate even if cyc drops briefly.
        locked_by_initiator = Signal(name="locked_by_initiator")
        if hasattr(self.bus, "lock"):
            with m.Switch(grant):
                for i, intr_bus in enumerate(self._intrs):
                    with m.Case(i):
                        if hasattr(intr_bus, "lock"):
                            m.d.comb += locked_by_initiator.eq(intr_bus.lock)

        with m.If(~self.bus.cyc & ~locked_by_initiator):
            with m.Switch(grant):
                for i in range(len(requests)):
                    with m.Case(i):
                        for pred in reversed(range(i)):
                            with m.If(requests[pred]):
                                m.d.sync += grant.eq(pred)
                        for succ in reversed(range(i + 1, len(requests))):
                            with m.If(requests[succ]):
                                m.d.sync += grant.eq(succ)

        with m.Switch(grant):
            for i, intr_bus in enumerate(self._intrs):
                m.submodules[f"shim_{i}"] = shim = \
                    _FeatureShim(intr_bus.addr_width, intr_bus.data_width, intr_bus.granularity,
                                 intr_features=intr_bus.features, sub_features=self.bus.features)
                connect(m, intr_bus, shim.intr_bus)

                m.d.comb += shim.sub_bus.dat_r.eq(self.bus.dat_r)
                if hasattr(self.bus, "stall"):
                    m.d.comb += shim.sub_bus.stall.eq(1)

                with m.Case(i):
                    ratio = intr_bus.granularity // self.bus.granularity
                    m.d.comb += [
                        self.bus.adr.eq(shim.sub_bus.adr),
                        self.bus.dat_w.eq(shim.sub_bus.dat_w),
                        self.bus.sel.eq(Cat(sel.replicate(ratio) for sel in shim.sub_bus.sel)),
                        self.bus.we.eq(shim.sub_bus.we),
                        self.bus.cyc.eq(shim.sub_bus.cyc),
                        self.bus.stb.eq(shim.sub_bus.stb),
                        shim.sub_bus.ack.eq(self.bus.ack)
                    ]
                    if hasattr(self.bus, "lock"):
                        m.d.comb += self.bus.lock.eq(shim.sub_bus.lock)
                    if hasattr(self.bus, "cti"):
                        m.d.comb += self.bus.cti.eq(shim.sub_bus.cti)
                    if hasattr(self.bus, "bte"):
                        m.d.comb += self.bus.bte.eq(shim.sub_bus.bte)
                    if hasattr(self.bus, "err"):
                        m.d.comb += shim.sub_bus.err.eq(self.bus.err)
                    if hasattr(self.bus, "rty"):
                        m.d.comb += shim.sub_bus.rty.eq(self.bus.rty)
                    if hasattr(self.bus, "stall"):
                        m.d.comb += shim.sub_bus.stall.eq(self.bus.stall)

        return m


class Crossbar(wiring.Component):
    """Wishbone crossbar interconnect.

    Composes Decoders and Arbiters to create an N×M crossbar that routes
    transactions from multiple initiators to multiple subordinates based
    on address decoding.

    For each initiator, a Decoder is created to route its transactions.
    For each subordinate, an Arbiter is created to handle concurrent access.

    The crossbar is built by:
    1. Creating N decoders (one per initiator), each with M subordinate windows
    2. Creating M arbiters (one per subordinate), each with N initiator inputs
    3. Wiring initiator → decoder → arbiter → subordinate

    Parameters
    ----------
    addr_width : int
        Address width.
    data_width : int
        Data width (8, 16, 32, or 64).
    granularity : int
        Bus granularity (default: same as data_width).
    features : frozenset of Feature
        Optional bus features.
    alignment : int
        Memory map alignment (default 0).
    """

    def __init__(self, *, addr_width, data_width, granularity=None, features=frozenset(),
                 alignment=0):
        if granularity is None:
            granularity = data_width
        if not isinstance(addr_width, int) or addr_width < 0:
            raise TypeError(f"Address width must be a non-negative integer, not {addr_width!r}")
        if data_width not in (8, 16, 32, 64):
            raise ValueError(f"Data width must be one of 8, 16, 32, 64, not {data_width!r}")
        if granularity not in (8, 16, 32, 64):
            raise ValueError(f"Granularity must be one of 8, 16, 32, 64, not {granularity!r}")
        if granularity > data_width:
            raise ValueError(f"Granularity {granularity} may not be greater than data width "
                             f"{data_width}")

        self._addr_width  = addr_width
        self._data_width  = data_width
        self._granularity = granularity
        self._features    = frozenset(Feature(f) for f in features)
        self._alignment   = alignment
        self._initiators  = []
        self._subordinates = []
        self._built = False

        # Dynamic configuration — no signature at construction time.
        super().__init__({})

    @property
    def addr_width(self):
        return self._addr_width

    @property
    def data_width(self):
        return self._data_width

    @property
    def granularity(self):
        return self._granularity

    @property
    def features(self):
        return self._features

    @property
    def alignment(self):
        return self._alignment

    def add_initiator(self, intr_bus, *, name=None):
        """Add an initiator (master) port.

        Parameters
        ----------
        intr_bus : Interface
            The initiator bus interface to connect.
        name : str or None
            Optional name for this initiator.
        """
        if self._built:
            raise RuntimeError("Cannot add initiators after elaborate() has been called")
        if isinstance(intr_bus, wiring.FlippedInterface):
            intr_bus_check = flipped(intr_bus)
        else:
            intr_bus_check = intr_bus
        if not isinstance(intr_bus_check, Interface):
            raise TypeError(f"Initiator bus must be an instance of wishbone.Interface, not "
                            f"{intr_bus_check!r}")
        if intr_bus.data_width != self._data_width:
            raise ValueError(f"Initiator bus has data width {intr_bus.data_width}, which is "
                             f"not the same as crossbar data width {self._data_width}")
        if intr_bus.granularity != self._granularity:
            raise ValueError(f"Initiator bus has granularity {intr_bus.granularity}, which is "
                             f"not the same as crossbar granularity {self._granularity}")
        idx = len(self._initiators)
        if name is None:
            name = f"initiator_{idx}"
        self._initiators.append((intr_bus, name))

    def add_subordinate(self, sub_bus, *, name=None, addr=None):
        """Add a subordinate (slave) port with address mapping.

        Parameters
        ----------
        sub_bus : Interface
            The subordinate bus interface to connect.
        name : str or None
            Name for this subordinate in the memory map.
        addr : int or None
            Base address. If None, auto-allocated.
        """
        if self._built:
            raise RuntimeError("Cannot add subordinates after elaborate() has been called")
        if isinstance(sub_bus, wiring.FlippedInterface):
            sub_bus_check = flipped(sub_bus)
        else:
            sub_bus_check = sub_bus
        if not isinstance(sub_bus_check, Interface):
            raise TypeError(f"Subordinate bus must be an instance of wishbone.Interface, not "
                            f"{sub_bus_check!r}")
        if sub_bus.data_width != self._data_width:
            raise ValueError(f"Subordinate bus has data width {sub_bus.data_width}, which is "
                             f"not the same as crossbar data width {self._data_width}")
        idx = len(self._subordinates)
        if name is None:
            name = f"subordinate_{idx}"
        self._subordinates.append((sub_bus, name, addr))

    def elaborate(self, platform):
        m = Module()
        self._built = True

        n_initiators = len(self._initiators)
        n_subordinates = len(self._subordinates)

        if n_initiators == 0 or n_subordinates == 0:
            return m

        # --- Create one Decoder per initiator ---
        decoders = []
        for i, (intr_bus, intr_name) in enumerate(self._initiators):
            dec = Decoder(addr_width=self._addr_width, data_width=self._data_width,
                          granularity=self._granularity, features=self._features,
                          alignment=self._alignment)
            m.submodules[f"dec_{intr_name}"] = dec
            decoders.append(dec)

        # --- Create intermediate interfaces ---
        # For each (initiator_i, subordinate_j) pair, create one Interface.
        # Pass flipped(inter) to the decoder (target-side) and the normal inter
        # to the arbiter (initiator-side). The decoder's connect() and arbiter's
        # connect() will both work because the directions are correct.
        inter_buses = {}  # (i, j) → Interface

        for i, dec in enumerate(decoders):
            for j, (sub_bus, sub_name, sub_addr) in enumerate(self._subordinates):
                sub_map = sub_bus.memory_map
                sub_aw = sub_map.addr_width
                granularity_bits = exact_log2(self._data_width // self._granularity)
                iface_addr_width = sub_aw - granularity_bits if granularity_bits > 0 else sub_aw
                if iface_addr_width < 0:
                    iface_addr_width = 0

                inter = Interface(addr_width=iface_addr_width,
                                  data_width=self._data_width,
                                  granularity=self._granularity,
                                  features=self._features,
                                  path=["xbar", f"i{i}_s{j}"])
                inter.memory_map = MemoryMap(addr_width=sub_aw,
                                             data_width=sub_map.data_width)
                # Pass flipped to decoder (target-side)
                dec.add(flipped(inter), name=sub_name, addr=sub_addr)
                inter_buses[(i, j)] = inter

        # --- Create one Arbiter per subordinate ---
        arbiters = []
        for j, (sub_bus, sub_name, sub_addr) in enumerate(self._subordinates):
            sub_map = sub_bus.memory_map
            sub_aw = sub_map.addr_width
            granularity_bits = exact_log2(self._data_width // self._granularity)
            arb_addr_width = sub_aw - granularity_bits if granularity_bits > 0 else sub_aw
            if arb_addr_width < 0:
                arb_addr_width = 0
            arb = Arbiter(addr_width=arb_addr_width,
                          data_width=self._data_width,
                          granularity=self._granularity,
                          features=self._features)
            m.submodules[f"arb_{sub_name}"] = arb
            arbiters.append(arb)

            # Pass normal (initiator-side) interfaces to arbiter
            for i in range(n_initiators):
                arb.add(inter_buses[(i, j)])

        # --- Wire initiator buses to decoder inputs ---
        for i, (intr_bus, intr_name) in enumerate(self._initiators):
            dec = decoders[i]
            m.d.comb += [
                dec.bus.adr.eq(intr_bus.adr),
                dec.bus.dat_w.eq(intr_bus.dat_w),
                dec.bus.sel.eq(intr_bus.sel),
                dec.bus.cyc.eq(intr_bus.cyc),
                dec.bus.stb.eq(intr_bus.stb),
                dec.bus.we.eq(intr_bus.we),
                intr_bus.dat_r.eq(dec.bus.dat_r),
                intr_bus.ack.eq(dec.bus.ack),
            ]
            if hasattr(dec.bus, "err") and hasattr(intr_bus, "err"):
                m.d.comb += intr_bus.err.eq(dec.bus.err)
            if hasattr(dec.bus, "rty") and hasattr(intr_bus, "rty"):
                m.d.comb += intr_bus.rty.eq(dec.bus.rty)
            if hasattr(dec.bus, "stall") and hasattr(intr_bus, "stall"):
                m.d.comb += intr_bus.stall.eq(dec.bus.stall)
            if hasattr(intr_bus, "lock") and hasattr(dec.bus, "lock"):
                m.d.comb += dec.bus.lock.eq(intr_bus.lock)
            if hasattr(intr_bus, "cti") and hasattr(dec.bus, "cti"):
                m.d.comb += dec.bus.cti.eq(intr_bus.cti)
            if hasattr(intr_bus, "bte") and hasattr(dec.bus, "bte"):
                m.d.comb += dec.bus.bte.eq(intr_bus.bte)

        # --- Wire arbiter outputs to subordinate buses ---
        for j, (sub_bus, sub_name, sub_addr) in enumerate(self._subordinates):
            arb = arbiters[j]
            m.d.comb += [
                sub_bus.adr.eq(arb.bus.adr),
                sub_bus.dat_w.eq(arb.bus.dat_w),
                sub_bus.sel.eq(arb.bus.sel),
                sub_bus.cyc.eq(arb.bus.cyc),
                sub_bus.stb.eq(arb.bus.stb),
                sub_bus.we.eq(arb.bus.we),
                arb.bus.dat_r.eq(sub_bus.dat_r),
                arb.bus.ack.eq(sub_bus.ack),
            ]
            if hasattr(sub_bus, "err") and hasattr(arb.bus, "err"):
                m.d.comb += arb.bus.err.eq(sub_bus.err)
            if hasattr(sub_bus, "rty") and hasattr(arb.bus, "rty"):
                m.d.comb += arb.bus.rty.eq(sub_bus.rty)
            if hasattr(sub_bus, "stall") and hasattr(arb.bus, "stall"):
                m.d.comb += arb.bus.stall.eq(sub_bus.stall)
            if hasattr(arb.bus, "lock") and hasattr(sub_bus, "lock"):
                m.d.comb += sub_bus.lock.eq(arb.bus.lock)
            if hasattr(arb.bus, "cti") and hasattr(sub_bus, "cti"):
                m.d.comb += sub_bus.cti.eq(arb.bus.cti)
            if hasattr(arb.bus, "bte") and hasattr(sub_bus, "bte"):
                m.d.comb += sub_bus.bte.eq(arb.bus.bte)

        return m
