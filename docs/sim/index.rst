Simulation Helpers
##################

.. py:module:: amaranth_soc.sim

The simulation subsystem provides helper functions and protocol checkers for testing
bus transactions in Amaranth simulations.

Overview
========

The simulation helpers are organized into three categories:

- **Wishbone Helpers** — Functions for performing Wishbone read/write transactions in simulation.
- **AXI Helpers** — Functions for performing AXI4-Lite and AXI4 transactions in simulation.
- **Protocol Checkers** — Passive monitors that verify bus protocol compliance during simulation.

Wishbone Simulation Helpers
===========================

.. py:module:: amaranth_soc.sim.wishbone

These functions are Amaranth process generators that can be used in simulation testbenches
to perform Wishbone bus transactions.

.. autofunction:: amaranth_soc.sim.wishbone.wb_write

.. autofunction:: amaranth_soc.sim.wishbone.wb_read

.. autofunction:: amaranth_soc.sim.wishbone.wb_write_pipelined

.. autofunction:: amaranth_soc.sim.wishbone.wb_read_pipelined

Example
-------

.. code-block:: python

   from amaranth.sim import Simulator
   from amaranth_soc.sim.wishbone import wb_write, wb_read

   async def testbench(ctx):
       # Write 0xDEADBEEF to address 0x100
       await wb_write(ctx, dut.bus, addr=0x100, data=0xDEADBEEF)

       # Read from address 0x100
       value = await wb_read(ctx, dut.bus, addr=0x100)
       assert value == 0xDEADBEEF

AXI Simulation Helpers
======================

.. py:module:: amaranth_soc.sim.axi

These functions perform AXI4-Lite and AXI4 bus transactions in simulation.

AXI4-Lite
---------

.. autofunction:: amaranth_soc.sim.axi.axi_lite_write

.. autofunction:: amaranth_soc.sim.axi.axi_lite_read

AXI4 (Full)
------------

.. autofunction:: amaranth_soc.sim.axi.axi4_write_single

.. autofunction:: amaranth_soc.sim.axi.axi4_read_single

.. autofunction:: amaranth_soc.sim.axi.axi4_write_burst

.. autofunction:: amaranth_soc.sim.axi.axi4_read_burst

Example
-------

.. code-block:: python

   from amaranth.sim import Simulator
   from amaranth_soc.sim.axi import axi_lite_write, axi_lite_read

   async def testbench(ctx):
       # Write via AXI4-Lite
       await axi_lite_write(ctx, dut.bus, addr=0x0, data=0x42, strb=0xF)

       # Read via AXI4-Lite
       value = await axi_lite_read(ctx, dut.bus, addr=0x0)

Protocol Checkers
=================

.. py:module:: amaranth_soc.sim.protocol_checker

Protocol checkers are passive monitors that observe bus transactions and raise assertion
errors if protocol violations are detected. They are useful for catching bugs in bus
implementations during simulation.

.. autoclass:: WishboneChecker
   :members:

.. autoclass:: AXI4LiteChecker
   :members:

.. autoclass:: AXI4Checker
   :members:

Example
-------

.. code-block:: python

   from amaranth_soc.sim.protocol_checker import WishboneChecker

   # Add a protocol checker to your simulation
   checker = WishboneChecker(dut.bus)

   # The checker will automatically monitor all transactions
   # and raise AssertionError on protocol violations
