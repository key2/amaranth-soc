from enum import Enum

from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out


__all__ = ["Endianness", "byte_swap", "EndianAdapter"]


class Endianness(Enum):
    """Bus byte ordering."""
    LITTLE = "little"
    BIG = "big"


def byte_swap(m, data_in, data_width):
    """Generate combinational byte-swap logic for a data signal.

    Parameters
    ----------
    m : :class:`Module`
        The module to add combinational logic to.
    data_in : :class:`Signal`
        Input data signal to byte-swap.
    data_width : int
        Width of the data in bits. Must be a multiple of 8.

    Returns
    -------
    :class:`Signal`
        A signal with bytes reversed.
    """
    if data_width % 8 != 0:
        raise ValueError(f"data_width must be a multiple of 8, not {data_width}")
    n_bytes = data_width // 8
    data_out = Signal(data_width, name="byte_swapped")
    for i in range(n_bytes):
        m.d.comb += data_out[i*8:(i+1)*8].eq(data_in[(n_bytes-1-i)*8:(n_bytes-i)*8])
    return data_out


class EndianAdapter(wiring.Component):
    """Byte-swap adapter for crossing endianness boundaries.

    Parameters
    ----------
    data_width : int
        Width of the data bus in bits. Must be a multiple of 8.
    """
    def __init__(self, data_width):
        if not isinstance(data_width, int) or data_width <= 0:
            raise ValueError(f"data_width must be a positive integer, not {data_width!r}")
        if data_width % 8 != 0:
            raise ValueError(f"data_width must be a multiple of 8, not {data_width}")
        self._data_width = data_width
        super().__init__({
            "i_data": In(data_width),
            "o_data": Out(data_width),
        })

    @property
    def data_width(self):
        return self._data_width

    def elaborate(self, platform):
        m = Module()
        n_bytes = self._data_width // 8
        for i in range(n_bytes):
            m.d.comb += self.o_data[i*8:(i+1)*8].eq(
                self.i_data[(n_bytes-1-i)*8:(n_bytes-i)*8]
            )
        return m
