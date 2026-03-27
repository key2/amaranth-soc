"""Base class for SoC peripherals.

Provides a standard interface pattern for peripherals that expose
CSR registers and optionally generate interrupts.
"""
from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out, connect, flipped

__all__ = ["Peripheral"]


class Peripheral(wiring.Component):
    """Base class for SoC peripherals.

    Provides a standard interface pattern for peripherals that expose
    CSR registers and optionally generate interrupts.

    Parameters
    ----------
    name : str
        Peripheral name, used for register naming.
    signature : dict
        Wiring signature for the component. Optional.
    """
    def __init__(self, name, signature={}):
        if not isinstance(name, str):
            raise TypeError(f"Peripheral name must be a string, not {name!r}")
        self._periph_name = name
        super().__init__(signature)

    @property
    def periph_name(self):
        """Return the peripheral name."""
        return self._periph_name
