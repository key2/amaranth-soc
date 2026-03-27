"""SoC platform wrapper.

Associates an Amaranth platform with SoC configuration, providing
a unified interface for platform-specific resource management.
"""
from amaranth import *

__all__ = ["SoCPlatform"]


class SoCPlatform:
    """Wrapper that associates an Amaranth platform with SoC configuration.

    Parameters
    ----------
    platform : amaranth.hdl.Platform
        The underlying Amaranth platform.
    """
    def __init__(self, platform):
        self._platform = platform

    @property
    def platform(self):
        """Return the underlying Amaranth platform."""
        return self._platform
