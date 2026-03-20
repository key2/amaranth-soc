"""IRQ management handler for SoC builder.

Manages IRQ assignment and interrupt controller instantiation.
"""

__all__ = ["IRQHandler"]


class IRQHandler:
    """Handles IRQ assignment and interrupt controller creation.

    Parameters
    ----------
    n_irqs : int
        Number of IRQ lines.
    csr_data_width : int
        CSR bus data width for the interrupt controller. Default 8.
    """

    def __init__(self, *, n_irqs, csr_data_width=8):
        if not isinstance(n_irqs, int) or n_irqs <= 0:
            raise ValueError(f"n_irqs must be a positive integer, not {n_irqs!r}")
        self._n_irqs = n_irqs
        self._csr_data_width = csr_data_width
        self._assignments = []

    @property
    def n_irqs(self):
        return self._n_irqs

    def assign_irq(self, peripheral, *, irq_num):
        """Assign an IRQ number to a peripheral.

        Parameters
        ----------
        peripheral : wiring.Component
            The peripheral component (must have an ``irq`` signal).
        irq_num : int
            The IRQ number to assign.

        Raises
        ------
        ValueError
            If ``irq_num`` is out of range [0, n_irqs).
        """
        if not isinstance(irq_num, int) or irq_num < 0 or irq_num >= self._n_irqs:
            raise ValueError(
                f"IRQ number must be in range [0, {self._n_irqs}), got {irq_num!r}"
            )
        self._assignments.append({"peripheral": peripheral, "irq_num": irq_num})

    def elaborate(self, m, irq_out_signal):
        """Create InterruptController, wire peripheral IRQs, connect output.

        Parameters
        ----------
        m : Module
            The Amaranth module being elaborated.
        irq_out_signal : Signal
            The SoC's IRQ output signal to drive.

        Returns
        -------
        InterruptController
            The created interrupt controller component.
        """
        from ..periph.intc import InterruptController

        intc = InterruptController(self._n_irqs, csr_data_width=self._csr_data_width)
        m.submodules.intc = intc

        # Wire IRQ lines from peripherals
        for assignment in self._assignments:
            periph = assignment["peripheral"]
            irq_num = assignment["irq_num"]
            if hasattr(periph, "irq"):
                m.d.comb += intc.irq_inputs[irq_num].eq(periph.irq)

        # Connect interrupt output
        m.d.comb += irq_out_signal.eq(intc.irq_out)

        return intc
