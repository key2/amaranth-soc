"""Bus adapter registry for automatic bridge selection.

Maintains a registry of available bridges between bus standards.
Supports direct bridges and two-hop chains (via AXI4-Lite hub).
"""


__all__ = ["BusAdapter"]


class BusAdapter:
    """Registry for automatic bus bridge selection.

    Maintains a registry of available bridges between bus standards.
    Supports direct bridges and two-hop chains (via AXI4-Lite hub).

    Usage
    -----
    >>> from amaranth_soc import BusStandard
    >>> BusAdapter.can_adapt(BusStandard.WISHBONE, BusStandard.AXI4_LITE)
    True
    >>> chain = BusAdapter.get_bridge_chain(BusStandard.WISHBONE, BusStandard.AXI4_LITE)
    >>> [(c.__name__, f.value, t.value) for c, f, t in chain]
    [('WishboneToAXI4Lite', 'wishbone', 'axi4-lite')]
    """

    _bridges = {}  # Class-level registry: (from_std, to_std) -> bridge_class

    @classmethod
    def register(cls, from_standard, to_standard, bridge_class):
        """Register a bridge between two bus standards.

        Parameters
        ----------
        from_standard : BusStandard
            Source bus standard.
        to_standard : BusStandard
            Target bus standard.
        bridge_class : class
            Bridge component class.
        """
        cls._bridges[(from_standard, to_standard)] = bridge_class

    @classmethod
    def can_adapt(cls, from_standard, to_standard):
        """Check if adaptation is possible (direct or two-hop).

        Parameters
        ----------
        from_standard : BusStandard
            Source bus standard.
        to_standard : BusStandard
            Target bus standard.

        Returns
        -------
        bool
            True if a bridge path exists.
        """
        if from_standard == to_standard:
            return True
        if (from_standard, to_standard) in cls._bridges:
            return True
        # Check two-hop via AXI4-Lite hub
        from amaranth_soc import BusStandard
        hub = BusStandard.AXI4_LITE
        if ((from_standard, hub) in cls._bridges and
                (hub, to_standard) in cls._bridges):
            return True
        return False

    @classmethod
    def get_bridge_chain(cls, from_standard, to_standard):
        """Get the bridge class(es) needed for adaptation.

        Returns a list of ``(bridge_class, from_std, to_std)`` tuples
        describing the bridge chain needed.

        Parameters
        ----------
        from_standard : BusStandard
            Source bus standard.
        to_standard : BusStandard
            Target bus standard.

        Returns
        -------
        list of tuple
            Each tuple is ``(bridge_class, from_standard, to_standard)``.

        Raises
        ------
        ValueError
            If no bridge path exists.
        """
        if from_standard == to_standard:
            return []
        if (from_standard, to_standard) in cls._bridges:
            return [(cls._bridges[(from_standard, to_standard)],
                     from_standard, to_standard)]
        # Two-hop via AXI4-Lite
        from amaranth_soc import BusStandard
        hub = BusStandard.AXI4_LITE
        if ((from_standard, hub) in cls._bridges and
                (hub, to_standard) in cls._bridges):
            return [
                (cls._bridges[(from_standard, hub)], from_standard, hub),
                (cls._bridges[(hub, to_standard)], hub, to_standard),
            ]
        raise ValueError(f"No bridge path from {from_standard} to {to_standard}")

    @classmethod
    def adapt(cls, interface, from_standard, to_standard, **kwargs):
        """Create bridge instance(s) to adapt between standards.

        Parameters
        ----------
        interface : object
            The source bus interface.
        from_standard : BusStandard
            Source bus standard.
        to_standard : BusStandard
            Target bus standard.
        **kwargs
            Additional keyword arguments passed to bridge constructors.

        Returns
        -------
        object
            A single bridge instance, a list of bridge instances (for two-hop),
            or the original interface (if same standard).
        """
        chain = cls.get_bridge_chain(from_standard, to_standard)
        if not chain:
            return interface  # Same standard, no bridge needed
        # For single bridge
        if len(chain) == 1:
            bridge_cls, _, _ = chain[0]
            return bridge_cls(**kwargs)
        # For two-hop: return list of bridges to be wired by caller
        bridges = []
        for bridge_cls, _, _ in chain:
            bridges.append(bridge_cls(**kwargs))
        return bridges

    @classmethod
    def list_bridges(cls):
        """List all registered bridges.

        Returns
        -------
        dict
            Dictionary mapping ``(from_standard, to_standard)`` to bridge class.
        """
        return dict(cls._bridges)


def _register_defaults():
    """Register the default set of bridges."""
    from amaranth_soc import BusStandard
    from amaranth_soc.bridge.wb_to_axi import WishboneToAXI4Lite
    from amaranth_soc.bridge.axi_to_wb import AXI4LiteToWishbone
    from amaranth_soc.axi.adapter import AXI4ToAXI4Lite

    BusAdapter.register(BusStandard.WISHBONE, BusStandard.AXI4_LITE, WishboneToAXI4Lite)
    BusAdapter.register(BusStandard.AXI4_LITE, BusStandard.WISHBONE, AXI4LiteToWishbone)
    BusAdapter.register(BusStandard.AXI4, BusStandard.AXI4_LITE, AXI4ToAXI4Lite)


_register_defaults()
