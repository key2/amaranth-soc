"""Bus protocol checkers for simulation verification.

These checkers monitor bus signals during simulation and flag protocol
violations. They are designed to be added as submodules during testing.
"""

from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out

__all__ = ["WishboneChecker", "AXI4LiteChecker", "AXI4Checker"]


class WishboneChecker(wiring.Component):
    """Wishbone protocol checker for simulation.

    Monitors a Wishbone bus and counts protocol violations.

    Checked rules:
    - Rule 1: ``stb`` must not be asserted without ``cyc``.
    - Rule 2: ``ack`` should only appear when both ``stb`` and ``cyc`` are asserted.
    - Rule 3: ``ack`` and ``err`` must not be asserted simultaneously
      (only checked when the bus has the ``err`` feature).

    Parameters
    ----------
    addr_width : int
        Address width.
    data_width : int
        Data width.
    granularity : int or None
        Bus granularity. Defaults to *data_width*.
    features : frozenset
        Optional Wishbone features (e.g. ``err``, ``rty``).
    """

    def __init__(self, *, addr_width, data_width, granularity=None, features=frozenset()):
        from ..wishbone.bus import Signature as WBSignature
        self._addr_width = addr_width
        self._data_width = data_width
        self._granularity = granularity
        self._features = frozenset(features)
        super().__init__({
            "bus": In(WBSignature(addr_width=addr_width, data_width=data_width,
                                  granularity=granularity, features=features)),
            "violations": Out(16),
        })

    @property
    def addr_width(self):
        return self._addr_width

    @property
    def data_width(self):
        return self._data_width

    def elaborate(self, platform):
        m = Module()

        violations = Signal(16, name="violation_cnt")
        m.d.comb += self.violations.eq(violations)

        # Rule 1: stb without cyc is a violation
        with m.If(self.bus.stb & ~self.bus.cyc):
            m.d.sync += violations.eq(violations + 1)

        # Rule 2: ack without (stb & cyc) is a violation
        with m.If(self.bus.ack & ~(self.bus.stb & self.bus.cyc)):
            m.d.sync += violations.eq(violations + 1)

        # Rule 3: ack and err simultaneously is a violation
        if hasattr(self.bus, "err"):
            with m.If(self.bus.ack & self.bus.err):
                m.d.sync += violations.eq(violations + 1)

        return m


class AXI4LiteChecker(wiring.Component):
    """AXI4-Lite protocol checker for simulation.

    Monitors an AXI4-Lite bus and counts protocol violations.

    Checked rules:
    - Rule 1: ``rvalid`` must not be asserted without a prior AR handshake
      (``arvalid`` & ``arready``).
    - Rule 2: ``bvalid`` must not be asserted without a prior AW handshake
      (``awvalid`` & ``awready``).

    Parameters
    ----------
    addr_width : int
        Address width.
    data_width : int
        Data width (must be >= 32 and a power of 2).
    """

    def __init__(self, *, addr_width, data_width):
        from ..axi.bus import AXI4LiteSignature
        self._addr_width = addr_width
        self._data_width = data_width
        super().__init__({
            "bus": In(AXI4LiteSignature(addr_width=addr_width, data_width=data_width)),
            "violations": Out(16),
        })

    @property
    def addr_width(self):
        return self._addr_width

    @property
    def data_width(self):
        return self._data_width

    def elaborate(self, platform):
        m = Module()

        violations = Signal(16, name="violation_cnt")
        m.d.comb += self.violations.eq(violations)

        # Track outstanding read address handshakes
        ar_outstanding = Signal(8, name="ar_outstanding")
        with m.If(self.bus.arvalid & self.bus.arready):
            with m.If(self.bus.rvalid & self.bus.rready):
                # Handshake and response in same cycle — net zero
                pass
            with m.Else():
                m.d.sync += ar_outstanding.eq(ar_outstanding + 1)
        with m.Elif(self.bus.rvalid & self.bus.rready):
            m.d.sync += ar_outstanding.eq(ar_outstanding - 1)

        # Rule 1: rvalid without outstanding AR handshake
        with m.If(self.bus.rvalid & (ar_outstanding == 0)
                  & ~(self.bus.arvalid & self.bus.arready)):
            m.d.sync += violations.eq(violations + 1)

        # Track outstanding write address handshakes
        aw_outstanding = Signal(8, name="aw_outstanding")
        with m.If(self.bus.awvalid & self.bus.awready):
            with m.If(self.bus.bvalid & self.bus.bready):
                pass
            with m.Else():
                m.d.sync += aw_outstanding.eq(aw_outstanding + 1)
        with m.Elif(self.bus.bvalid & self.bus.bready):
            m.d.sync += aw_outstanding.eq(aw_outstanding - 1)

        # Rule 2: bvalid without outstanding AW handshake
        with m.If(self.bus.bvalid & (aw_outstanding == 0)
                  & ~(self.bus.awvalid & self.bus.awready)):
            m.d.sync += violations.eq(violations + 1)

        return m


class AXI4Checker(wiring.Component):
    """AXI4 (full) protocol checker for simulation.

    Monitors an AXI4 bus and counts protocol violations.

    Checked rules:
    - Rule 1: ``wlast`` must be asserted on the correct beat (matching ``awlen``).
    - Rule 2: ``rlast`` must be asserted on the correct beat (matching ``arlen``).

    Parameters
    ----------
    addr_width : int
        Address width.
    data_width : int
        Data width (must be >= 8 and a power of 2).
    id_width : int
        ID signal width (default 0).
    """

    def __init__(self, *, addr_width, data_width, id_width=0):
        from ..axi.bus import AXI4Signature
        self._addr_width = addr_width
        self._data_width = data_width
        self._id_width = id_width
        super().__init__({
            "bus": In(AXI4Signature(addr_width=addr_width, data_width=data_width,
                                    id_width=id_width)),
            "violations": Out(16),
        })

    @property
    def addr_width(self):
        return self._addr_width

    @property
    def data_width(self):
        return self._data_width

    @property
    def id_width(self):
        return self._id_width

    def elaborate(self, platform):
        m = Module()

        violations = Signal(16, name="violation_cnt")
        m.d.comb += self.violations.eq(violations)

        # --- Write channel: track wlast vs awlen ---
        w_beat_cnt = Signal(9, name="w_beat_cnt")  # up to 256 beats
        w_expected_len = Signal(8, name="w_expected_len")
        w_active = Signal(name="w_active")

        # Capture awlen on AW handshake
        with m.If(self.bus.awvalid & self.bus.awready):
            m.d.sync += [
                w_expected_len.eq(self.bus.awlen),
                w_beat_cnt.eq(0),
                w_active.eq(1),
            ]

        # Count W beats
        with m.If(self.bus.wvalid & self.bus.wready & w_active):
            m.d.sync += w_beat_cnt.eq(w_beat_cnt + 1)

            # Rule 1: wlast on wrong beat
            with m.If(self.bus.wlast):
                with m.If(w_beat_cnt != w_expected_len):
                    m.d.sync += violations.eq(violations + 1)
                m.d.sync += w_active.eq(0)

        # --- Read channel: track rlast vs arlen ---
        r_beat_cnt = Signal(9, name="r_beat_cnt")
        r_expected_len = Signal(8, name="r_expected_len")
        r_active = Signal(name="r_active")

        # Capture arlen on AR handshake
        with m.If(self.bus.arvalid & self.bus.arready):
            m.d.sync += [
                r_expected_len.eq(self.bus.arlen),
                r_beat_cnt.eq(0),
                r_active.eq(1),
            ]

        # Count R beats
        with m.If(self.bus.rvalid & self.bus.rready & r_active):
            m.d.sync += r_beat_cnt.eq(r_beat_cnt + 1)

            # Rule 2: rlast on wrong beat
            with m.If(self.bus.rlast):
                with m.If(r_beat_cnt != r_expected_len):
                    m.d.sync += violations.eq(violations + 1)
                m.d.sync += r_active.eq(0)

        return m
