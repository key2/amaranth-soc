"""Generic reusable utilities for amaranth-soc."""

from .wait_timer import WaitTimer
from .reset_inserter import add_reset_domain

__all__ = [
    "WaitTimer",
    "add_reset_domain",
]
