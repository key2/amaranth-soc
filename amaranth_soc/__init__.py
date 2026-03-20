# Extract version for this package from the environment package metadata. This used to be a lot
# more difficult in earlier Python versions, and the `__version__` field is a legacy of that time.
import importlib.metadata
try:
    __version__ = importlib.metadata.version(__package__)
except importlib.metadata.PackageNotFoundError:
    # No importlib metadata for this package. This shouldn't normally happen, but some people
    # prefer not installing packages via pip at all. Although not recommended we still support it.
    __version__ = "unknown" # :nocov:
del importlib


import enum


__all__ = ["BusStandard", "detect_bus_standard"]


class BusStandard(enum.Enum):
    """Supported bus standards."""
    WISHBONE = "wishbone"
    AXI4_LITE = "axi4-lite"
    AXI4 = "axi4"


def detect_bus_standard(signature):
    """Detect the bus standard from a Signature type.

    Parameters
    ----------
    signature : wiring.Signature
        The bus signature to identify.

    Returns
    -------
    BusStandard
        The detected bus standard.

    Raises
    ------
    TypeError
        If the signature is not a recognized bus standard.
    """
    from amaranth_soc.axi.bus import AXI4LiteSignature, AXI4Signature
    from amaranth_soc.wishbone.bus import Signature as WishboneSignature

    if isinstance(signature, AXI4Signature):
        return BusStandard.AXI4
    elif isinstance(signature, AXI4LiteSignature):
        return BusStandard.AXI4_LITE
    elif isinstance(signature, WishboneSignature):
        return BusStandard.WISHBONE
    else:
        raise TypeError(f"Unrecognized bus signature type: {type(signature)}")
