"""MSI/MSI-X controller for PCIe interrupt generation."""

from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.lib.memory import MemoryData, Memory


__all__ = ["MSIController"]


class MSIController(wiring.Component):
    """MSI/MSI-X controller for PCIe interrupt generation.

    Converts interrupt sources into MSI write transactions.
    Each vector has a configurable address and data value.

    When an interrupt source fires (rising edge on a masked source),
    the controller latches the pending bit, priority-encodes the
    highest-priority (lowest index) pending vector, looks up its
    configured address and data from internal memory, and presents
    them on the output with valid/ready handshaking.

    When ``msi_ready`` is asserted while ``msi_valid`` is high, the
    acknowledged vector's pending bit is cleared and the controller
    moves to the next pending vector (if any).

    Parameters
    ----------
    n_vectors : int
        Number of MSI vectors (1-2048 for MSI-X).
    addr_width : int
        Address width for MSI write transactions.
    data_width : int
        Data width for MSI write transactions (typically 32).
    """
    def __init__(self, n_vectors, *, addr_width=64, data_width=32):
        if not isinstance(n_vectors, int) or n_vectors <= 0:
            raise ValueError(
                f"Number of vectors must be a positive integer, not {n_vectors!r}")
        if not isinstance(addr_width, int) or addr_width <= 0:
            raise ValueError(
                f"Address width must be a positive integer, not {addr_width!r}")
        if not isinstance(data_width, int) or data_width <= 0:
            raise ValueError(
                f"Data width must be a positive integer, not {data_width!r}")

        self._n_vectors = n_vectors
        self._addr_width = addr_width
        self._data_width = data_width

        super().__init__({
            # Interrupt source inputs
            "sources":    In(n_vectors),
            "enable":     In(n_vectors),
            # Vector configuration port
            "cfg_vector": In(range(n_vectors)),
            "cfg_addr":   In(addr_width),
            "cfg_data":   In(data_width),
            "cfg_we":     In(1),
            # MSI output (stream-like)
            "msi_addr":   Out(addr_width),
            "msi_data":   Out(data_width),
            "msi_valid":  Out(1),
            "msi_ready":  In(1),
        })

    @property
    def n_vectors(self):
        """Number of MSI vectors."""
        return self._n_vectors

    @property
    def addr_width(self):
        """Address width for MSI write transactions."""
        return self._addr_width

    @property
    def data_width(self):
        """Data width for MSI write transactions."""
        return self._data_width

    def elaborate(self, platform):
        m = Module()

        n = self._n_vectors
        aw = self._addr_width
        dw = self._data_width

        # ----- Vector configuration memory (addr + data per vector) -----
        # Use simple register arrays for the configuration store.
        # For large n_vectors, a Memory could be used, but registers
        # are simpler and sufficient for typical MSI/MSI-X sizes.
        cfg_addrs = Array([Signal(aw, name=f"cfg_addr_{i}") for i in range(n)])
        cfg_datas = Array([Signal(dw, name=f"cfg_data_{i}") for i in range(n)])

        # Configuration write port
        with m.If(self.cfg_we):
            m.d.sync += cfg_addrs[self.cfg_vector].eq(self.cfg_addr)
            m.d.sync += cfg_datas[self.cfg_vector].eq(self.cfg_data)

        # ----- Edge detection on masked sources -----
        masked = Signal(n, name="masked")
        m.d.comb += masked.eq(self.sources & self.enable)

        prev = Signal(n, name="prev")
        m.d.sync += prev.eq(masked)

        rising = Signal(n, name="rising")
        m.d.comb += rising.eq(masked & ~prev)

        # ----- Pending register -----
        pending = Signal(n, name="pending", init=0)

        # ----- Priority encoding -----
        vector = Signal(range(max(n, 1)), name="vector")
        found = Signal(name="found")

        m.d.comb += [
            found.eq(0),
            vector.eq(0),
        ]

        # Scan from highest to lowest so lowest index wins
        for i in reversed(range(n)):
            with m.If(pending[i]):
                m.d.comb += [
                    vector.eq(i),
                    found.eq(1),
                ]

        # ----- Output -----
        m.d.comb += [
            self.msi_valid.eq(found),
            self.msi_addr.eq(cfg_addrs[vector]),
            self.msi_data.eq(cfg_datas[vector]),
        ]

        # ----- Pending update -----
        # Determine which bit to clear on acknowledge
        ack_clear = Signal(n, name="ack_clear")
        with m.If(self.msi_ready & self.msi_valid):
            m.d.comb += ack_clear.eq(1 << vector)
        with m.Else():
            m.d.comb += ack_clear.eq(0)

        # Set new edges, clear acknowledged
        m.d.sync += pending.eq((pending | rising) & ~ack_clear)

        return m
