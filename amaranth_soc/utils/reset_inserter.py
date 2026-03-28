"""Reset insertion utilities for Amaranth components.

Provides :func:`add_reset_domain`, the Amaranth equivalent of LiteX/Migen's
``ResetInserter()``.  It creates a new local clock domain whose reset is
OR'd with an additional reset signal, allowing any logic placed in that
domain to be synchronously reset on demand.
"""

from amaranth import *


__all__ = ["add_reset_domain"]


def add_reset_domain(m, reset_signal, *, src_domain="sync", name=None):
    """Create a local clock domain with an additional reset signal.

    This is the Amaranth equivalent of LiteX/Migen's ``ResetInserter()``.
    It creates a new local clock domain that shares the clock of *src_domain*
    but has its reset OR'd with the provided *reset_signal*.

    Parameters
    ----------
    m : :class:`~amaranth.hdl.Module`
        The module to add the domain to.
    reset_signal : :class:`~amaranth.hdl.Signal`
        Additional reset signal to OR with the domain's existing reset.
    src_domain : :class:`str`
        Source clock domain name (default ``"sync"``).
    name : :class:`str` or ``None``
        Name for the new domain.  If ``None``, auto-generated as
        ``"_rst_{src_domain}"``.

    Returns
    -------
    :class:`str`
        The name of the new domain.  Use this with ``m.d[name]`` to place
        synchronous logic that will be reset when *reset_signal* is asserted.

    Examples
    --------
    .. code-block:: python

        m = Module()
        rst = Signal()
        domain = add_reset_domain(m, rst)
        counter = Signal(8)
        m.d[domain] += counter.eq(counter + 1)
        # counter resets to 0 when rst is asserted
    """
    if name is None:
        name = f"_rst_{src_domain}"
    m.domains += ClockDomain(name, local=True)
    m.d.comb += [
        ClockSignal(name).eq(ClockSignal(src_domain)),
        ResetSignal(name).eq(ResetSignal(src_domain) | reset_signal),
    ]
    return name
