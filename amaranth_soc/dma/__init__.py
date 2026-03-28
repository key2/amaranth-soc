"""DMA subsystem for amaranth-soc.

Provides both AXI4-based DMA engines (DMAReader, DMAWriter, ScatterGatherDMA)
and bus-agnostic DMA controllers (DMAReadController, DMAWriteController,
DMADescriptorTable, DMADescriptorSplitter) with plugins (DMALoopback,
DMASynchronizer, DMABuffering).
"""

from .common import *
from .reader import *
from .writer import *
from .scatter_gather import *
from .descriptor_table import *
from .splitter import *
from .read_controller import *
from .write_controller import *
from .loopback import *
from .synchronizer import *
from .buffering import *
