GPIO Peripheral
###############

.. py:module:: amaranth_soc.gpio

The GPIO peripheral provides a configurable general-purpose I/O controller with CSR register
access. Each pin can be independently configured for input, push-pull output, open-drain output,
or alternate function mode.

Overview
========

The GPIO peripheral provides the following CSR registers:

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Register
     - Access
     - Description
   * - **Mode**
     - R/W
     - 2-bit mode field per pin (INPUT_ONLY, PUSH_PULL, OPEN_DRAIN, ALTERNATE).
   * - **Input**
     - R
     - 1-bit input value per pin (after synchronization stages).
   * - **Output**
     - R/W
     - 1-bit output value per pin.
   * - **SetClr**
     - W
     - 2-bit set/clear field per pin for atomic output modification.

Pin Modes
=========

.. autoclass:: PinMode
   :members:

Pin Signature
=============

.. autoclass:: PinSignature
   :members:

Peripheral
==========

.. autoclass:: Peripheral
   :members:

Peripheral Registers
--------------------

.. autoclass:: amaranth_soc.gpio.Peripheral.Mode
   :members:

.. autoclass:: amaranth_soc.gpio.Peripheral.Input
   :members:

.. autoclass:: amaranth_soc.gpio.Peripheral.Output
   :members:

.. autoclass:: amaranth_soc.gpio.Peripheral.SetClr
   :members:

Example
=======

.. code-block:: python

   from amaranth_soc.gpio import Peripheral as GPIOPeripheral

   # Create an 8-pin GPIO peripheral
   gpio = GPIOPeripheral(
       pin_count=8,
       addr_width=4,
       data_width=8,
       input_stages=2,  # 2 synchronization stages
   )

   # In elaborate():
   # Connect gpio.bus to your CSR bus
   # Connect gpio.pins[n].i/o/oe to platform pins
   # Read gpio.alt_mode to determine which pins are in alternate mode
