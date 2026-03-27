# amaranth-soc

**Unified System-on-Chip toolkit for Amaranth HDL.**

`amaranth-soc` provides a complete SoC infrastructure for [Amaranth HDL](https://github.com/amaranth-lang/amaranth), combining the original upstream amaranth-soc foundations (CSR registers, memory maps, event handling, Wishbone bus, GPIO peripheral) with a full AXI4/AXI4-Lite bus infrastructure, AXI4 Full interconnect, DMA engines, MSI interrupt controllers, cross-bus bridges, endianness support, bus protocol checkers, CPU wrappers, export utilities, and a bus-agnostic SoC builder.

> **All 18 roadmap items have been implemented.** See [`TODO.md`](TODO.md) and [`STATUS.md`](STATUS.md) for details.

## Core Components (from upstream amaranth-soc)

| Component | Description |
|-----------|-------------|
| **CSR registers** | `csr.Register`, `csr.Field`, `csr.Multiplexer`, `csr.Decoder` — control/status register infrastructure with field-level access control and element-based ownership model |
| **Memory maps** | `MemoryMap` — hierarchical address space management with windows, resources, and BAR-relative addressing |
| **Event handling** | `event.Source`, `event.EventMap`, `event.Monitor` — interrupt event aggregation |
| **Wishbone bus** | `wishbone.Signature`, `wishbone.Interface`, `wishbone.Decoder`, `wishbone.Arbiter`, `wishbone.Crossbar` — Wishbone B4 pipelined bus with burst support |
| **GPIO peripheral** | `gpio.Peripheral` — general-purpose I/O with CSR interface |

## Extended Components

| Layer | Components |
|-------|-----------|
| **AXI4-Lite bus** | `AXI4LiteSignature`, `AXI4LiteInterface` — with relaxed data width support |
| **AXI4-Lite interconnect** | `AXI4LiteDecoder` (1→N, pipelined), `AXI4LiteArbiter` (N→1), `AXI4LiteCrossbar` (N×M) |
| **AXI4 Full bus** | `AXI4Signature`, `AXI4Interface` — with ID, burst, and user signals |
| **AXI4 Full interconnect** | `AXI4Decoder` (burst-aware), `AXI4Arbiter` (ID remapping), `AXI4Crossbar` (N×M) |
| **Memory** | `AXI4LiteSRAM`, `AXI4SRAM` (native burst), `WishboneSRAM` |
| **AXI4 adapters** | `AXIBurst2Beat` — burst address generator, `AXI4ToAXI4Lite` — burst decomposition |
| **Bridges** | `WishboneToAXI4Lite`, `AXI4LiteToWishbone`, `AXI4LiteCSRBridge`, `BusAdapter` registry |
| **DMA** | `DMAReader`, `DMAWriter`, `ScatterGatherDMA` — DMA engines with scatter-gather |
| **Peripherals** | `TimerPeripheral`, `InterruptController`, `MSIController`, GPIO, UART |
| **CPU wrappers** | `CPUWrapper`, `AXICPUWrapper`, `WishboneCPUWrapper`, `VexRiscvCPU` |
| **SoC builder** | `SoCBuilder` / `SoC` — bus-agnostic configuration with DMA, BAR mapping, auto bridges |
| **Export** | `CHeaderGenerator`, `SVDGenerator`, `LinkerScriptGenerator`, `DeviceTreeGenerator` |
| **Simulation** | AXI4-Lite + AXI4 Full + Wishbone async testbench helpers |
| **Verification** | Bus protocol checkers for Wishbone, AXI4-Lite, AXI4 Full |
| **Timeout** | `AXI4LiteTimeout`, `AXI4Timeout` — bus watchdog with SLVERR generation |
| **Endianness** | `Endianness` enum, byte-swap utilities, automatic bridge byte-swap |

---

## Installation

```bash
# Clone the repository (with local amaranth dependency)
git clone <repo-url>
cd amaranth-soc

# Install with PDM
pdm install

# Install with dev/test dependencies
pdm install -G dev
```

### Dependencies

- Python ≥ 3.10
- [Amaranth](https://github.com/amaranth-lang/amaranth) (local path dependency)

---

## Quick Start

A minimal example: create an AXI4-Lite SRAM, write to it, and read back via simulation.

```python
from amaranth import *
from amaranth.sim import Simulator

from amaranth_soc.axi import AXI4LiteSRAM
from amaranth_soc.sim import axi_lite_write, axi_lite_read

# Create a 1 KiB SRAM with 32-bit AXI4-Lite interface
sram = AXI4LiteSRAM(size=1024, data_width=32)

sim = Simulator(sram)
sim.add_clock(1e-6)

async def testbench(ctx):
    # Write 0xDEADBEEF to address 0x00
    await axi_lite_write(ctx, sram.bus, addr=0x00, data=0xDEADBEEF)
    # Read it back
    data, resp = await axi_lite_read(ctx, sram.bus, addr=0x00)
    print(f"Read back: 0x{data:08X}")  # → 0xDEADBEEF

sim.add_testbench(testbench)
with sim.write_vcd("sram_test.vcd"):
    sim.run()
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        SoCBuilder                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐  │
│  │   ROM    │  │   RAM    │  │  Timer   │  │    INTC    │  │
│  │ (SRAM)  │  │ (SRAM)  │  │ (periph) │  │  (periph)  │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └─────┬──────┘  │
│       │              │             │               │         │
│       │              │        ┌────┴────┐          │         │
│       │              │        │CSR Mux  │          │         │
│       │              │        └────┬────┘          │         │
│       │              │             │               │         │
│       │              │     ┌───────┴────────┐      │         │
│       │              │     │AXI4LiteCSRBridge│     │         │
│       │              │     └───────┬────────┘      │         │
│       │              │             │               │         │
│  ┌────┴──────────────┴─────────────┴───────────────┘         │
│  │              AXI4LiteDecoder (1→N)                        │
│  └──────────────────────┬────────────────────────────────────┘
│                         │
│                    bus (In)  ← CPU / master connects here
└─────────────────────────────────────────────────────────────┘
```

### Component Hierarchy

```
BusStandard (enum)
├── WISHBONE
├── AXI4_LITE
└── AXI4

AXI4-Lite Layer
├── AXI4LiteSignature / AXI4LiteInterface  (bus definition, relaxed data width)
├── AXI4LiteDecoder                         (address routing, pipelined)
├── AXI4LiteArbiter                         (multi-master arbitration)
├── AXI4LiteCrossbar                        (NxM interconnect)
├── AXI4LiteSRAM                            (memory controller)
└── AXI4LiteTimeout                         (watchdog)

AXI4 Full Layer
├── AXI4Signature / AXI4Interface           (bus definition)
├── AXI4Decoder                             (burst-aware address routing)
├── AXI4Arbiter                             (ID remapping arbitration)
├── AXI4Crossbar                            (NxM interconnect with ID management)
├── AXI4SRAM                                (native burst SRAM)
├── AXI4Timeout                             (burst-level watchdog)
├── AXIBurst2Beat                           (burst address generator)
└── AXI4ToAXI4Lite                          (protocol adapter)

Wishbone Layer
├── wishbone.Signature / wishbone.Interface (bus definition)
├── wishbone.Decoder                        (address routing, burst-aware)
├── wishbone.Arbiter                        (multi-master, burst-locked)
├── wishbone.Crossbar                       (NxM interconnect)
└── WishboneSRAM                            (memory controller)

Bridges
├── WishboneToAXI4Lite                      (WB → AXI4-Lite)
├── AXI4LiteToWishbone                      (AXI4-Lite → WB)
├── AXI4LiteCSRBridge                       (AXI4-Lite → CSR)
├── WishboneCSRBridge                       (WB → CSR)
└── BusAdapter                              (automatic bridge registry)

DMA
├── DMAReader                               (read engine with FIFO)
├── DMAWriter                               (write engine with FIFO)
└── ScatterGatherDMA                        (descriptor-based DMA)

Peripherals
├── TimerPeripheral                         (countdown timer + CSR)
├── InterruptController                     (N-input IRQ aggregator + CSR)
├── MSIController                           (MSI/MSI-X interrupt controller)
├── GPIO                                    (general-purpose I/O)
├── UART                                    (serial communication)
└── PeripheralBase                          (abstract base class)

CPU Wrappers
├── CPUWrapper                              (abstract base)
├── AXICPUWrapper                           (AXI bus wrapper)
├── WishboneCPUWrapper                      (Wishbone bus wrapper)
└── VexRiscvCPU                             (VexRiscv integration)

SoC Builder
├── SoCBuilder                              (configuration)
├── SoC                                     (elaboratable component)
├── BusHandler (ABC)                        (bus topology handler)
│   ├── AXI4LiteBusHandler                  (AXI4-Lite bus topology)
│   ├── AXI4BusHandler                      (AXI4 Full bus topology)
│   └── WishboneBusHandler                  (Wishbone bus topology)
├── CSRHandler                              (CSR map handler)
├── IRQHandler                              (IRQ routing handler)
└── SoCPlatform                             (platform integration)

Export
├── CHeaderGenerator                        (C #define macros)
├── SVDGenerator                            (CMSIS-SVD XML)
├── LinkerScriptGenerator                   (linker scripts)
└── DeviceTreeGenerator                     (Linux device tree)

Simulation
├── axi_lite_write() / axi_lite_read()     (AXI4-Lite helpers)
├── axi4_write_burst() / axi4_read_burst() (AXI4 Full helpers)
├── wb_write() / wb_read()                  (Wishbone Classic helpers)
├── wb_write_pipelined() / wb_read_pipelined() (Wishbone pipelined)
└── Protocol checkers                       (Wishbone, AXI4-Lite, AXI4)

Endianness
└── Endianness enum + byte-swap utilities   (bus_common.py)
```

---

## API Reference

### Bus Standards & Detection

#### `BusStandard` (enum)

Defined in [`__init__.py`](amaranth_soc/__init__.py:8).

```python
from amaranth_soc import BusStandard

BusStandard.WISHBONE   # "wishbone"
BusStandard.AXI4_LITE  # "axi4-lite"
BusStandard.AXI4       # "axi4"
```

#### `detect_bus_standard(signature)`

Defined in [`__init__.py`](amaranth_soc/__init__.py:15). Identifies the bus standard from a `wiring.Signature` instance.

```python
from amaranth_soc import detect_bus_standard, BusStandard
from amaranth_soc.axi import AXI4LiteSignature

sig = AXI4LiteSignature(addr_width=16, data_width=32)
assert detect_bus_standard(sig) == BusStandard.AXI4_LITE
```

**Parameters:**
- `signature` — a `wiring.Signature` instance (`AXI4LiteSignature`, `AXI4Signature`, or Wishbone `Signature`)

**Returns:** `BusStandard`

**Raises:** `TypeError` if the signature is not recognized.

### Endianness Support

#### `Endianness` (enum)

Defined in [`bus_common.py`](amaranth_soc/bus_common.py:1). Byte ordering for bus primitives.

```python
from amaranth_soc.bus_common import Endianness

Endianness.LITTLE  # Little-endian
Endianness.BIG     # Big-endian
```

Endianness parameters are supported on bus signatures and bridges. When crossing endianness boundaries, bridges automatically insert byte-swap logic.

---

### AXI4-Lite Bus Layer

#### `AXIResp` (enum)

Defined in [`axi/bus.py`](amaranth_soc/axi/bus.py:17). AXI response codes per AMBA spec.

| Value | Name | Meaning |
|-------|------|---------|
| `0b00` | `OKAY` | Normal success |
| `0b01` | `EXOKAY` | Exclusive access success |
| `0b10` | `SLVERR` | Slave error |
| `0b11` | `DECERR` | Decode error (no slave at address) |

#### `AXIBurst` (enum)

Defined in [`axi/bus.py`](amaranth_soc/axi/bus.py:25). AXI burst types.

| Value | Name | Meaning |
|-------|------|---------|
| `0b00` | `FIXED` | Same address each beat |
| `0b01` | `INCR` | Incrementing address |
| `0b10` | `WRAP` | Wrapping burst |

#### `AXISize` (enum)

Defined in [`axi/bus.py`](amaranth_soc/axi/bus.py:32). AXI transfer size encoding.

| Value | Name | Bytes per beat |
|-------|------|---------------|
| `0b000` | `B1` | 1 |
| `0b001` | `B2` | 2 |
| `0b010` | `B4` | 4 |
| `0b011` | `B8` | 8 |
| `0b100` | `B16` | 16 |
| `0b101` | `B32` | 32 |
| `0b110` | `B64` | 64 |
| `0b111` | `B128` | 128 |

#### `AXI4LiteSignature`

Defined in [`axi/bus.py`](amaranth_soc/axi/bus.py:44). Amaranth `wiring.Signature` for AXI4-Lite.

```python
from amaranth_soc.axi import AXI4LiteSignature

sig = AXI4LiteSignature(addr_width=16, data_width=32)
sig.addr_width  # 16
sig.data_width  # 32

# Wider data widths are supported (relaxed from strict 32/64 spec)
sig_wide = AXI4LiteSignature(addr_width=16, data_width=256)
```

**Constructor parameters:**
- `addr_width` (`int`) — Width of address signals (`awaddr`, `araddr`). Must be ≥ 0.
- `data_width` (`int`) — Width of data signals (`wdata`, `rdata`). Supports 32, 64, and wider (128, 256, etc.) for high-bandwidth SoCs.

**Signal members (Out = master→slave, In = slave→master):**

| Channel | Signal | Direction | Width |
|---------|--------|-----------|-------|
| AW | `awaddr` | Out | `addr_width` |
| AW | `awprot` | Out | 3 |
| AW | `awvalid` | Out | 1 |
| AW | `awready` | In | 1 |
| W | `wdata` | Out | `data_width` |
| W | `wstrb` | Out | `data_width // 8` |
| W | `wvalid` | Out | 1 |
| W | `wready` | In | 1 |
| B | `bresp` | In | 2 |
| B | `bvalid` | In | 1 |
| B | `bready` | Out | 1 |
| AR | `araddr` | Out | `addr_width` |
| AR | `arprot` | Out | 3 |
| AR | `arvalid` | Out | 1 |
| AR | `arready` | In | 1 |
| R | `rdata` | In | `data_width` |
| R | `rresp` | In | 2 |
| R | `rvalid` | In | 1 |
| R | `rready` | Out | 1 |

#### `AXI4LiteInterface`

Defined in [`axi/bus.py`](amaranth_soc/axi/bus.py:138). A `wiring.PureInterface` with optional `memory_map`.

```python
from amaranth_soc.axi import AXI4LiteInterface
from amaranth_soc.memory import MemoryMap

bus = AXI4LiteInterface(addr_width=16, data_width=32)
bus.addr_width  # 16
bus.data_width  # 32

# Attach a memory map (byte-addressable)
bus.memory_map = MemoryMap(addr_width=16, data_width=8)
```

**Constructor parameters:**
- `addr_width` (`int`) — Address width.
- `data_width` (`int`) — Data width (32 or 64).
- `path` (`iter(str)`, optional) — Interface path for naming.

**Properties:**
- `addr_width` — Address width.
- `data_width` — Data width.
- `memory_map` — Attached `MemoryMap` (raises `AttributeError` if not set).

**Memory map constraints:**
- `data_width` must be 8 (byte-addressable) or equal to bus `data_width`.
- `addr_width` must match the interface `addr_width`.

#### `AXI4Signature`

Defined in [`axi/bus.py`](amaranth_soc/axi/bus.py:197). Full AXI4 signature with burst, ID, and user signals.

```python
from amaranth_soc.axi import AXI4Signature

# Basic AXI4 with 4-bit IDs
sig = AXI4Signature(addr_width=32, data_width=32, id_width=4)

# With user signals
sig = AXI4Signature(
    addr_width=32, data_width=64, id_width=8,
    user_width={"aw": 4, "w": 0, "b": 0, "ar": 4, "r": 0}
)
sig.id_width    # 8
sig.user_width  # {"aw": 4, "w": 0, "b": 0, "ar": 4, "r": 0}
```

**Constructor parameters:**
- `addr_width` (`int`) — Address width. Must be ≥ 0.
- `data_width` (`int`) — Data width. Must be a power of 2 and ≥ 8.
- `id_width` (`int`, default `0`) — ID signal width. Signals with width 0 are omitted.
- `user_width` (`dict`, default all 0) — Per-channel user signal widths. Keys: `"aw"`, `"w"`, `"b"`, `"ar"`, `"r"`.

**Additional signals beyond AXI4-Lite:**

| Channel | Signal | Direction | Width |
|---------|--------|-----------|-------|
| AW | `awid` | Out | `id_width` (if > 0) |
| AW | `awlen` | Out | 8 |
| AW | `awsize` | Out | 3 |
| AW | `awburst` | Out | 2 |
| AW | `awlock` | Out | 1 |
| AW | `awcache` | Out | 4 |
| AW | `awqos` | Out | 4 |
| AW | `awregion` | Out | 4 |
| AW | `awuser` | Out | `user_width["aw"]` (if > 0) |
| W | `wlast` | Out | 1 |
| B | `bid` | In | `id_width` (if > 0) |
| B | `buser` | In | `user_width["b"]` (if > 0) |
| AR | `arid` | Out | `id_width` (if > 0) |
| AR | `arlen` | Out | 8 |
| AR | `arsize` | Out | 3 |
| AR | `arburst` | Out | 2 |
| AR | `arlock` | Out | 1 |
| AR | `arcache` | Out | 4 |
| AR | `arqos` | Out | 4 |
| AR | `arregion` | Out | 4 |
| AR | `aruser` | Out | `user_width["ar"]` (if > 0) |
| R | `rid` | In | `id_width` (if > 0) |
| R | `rlast` | In | 1 |
| R | `ruser` | In | `user_width["r"]` (if > 0) |

#### `AXI4Interface`

Defined in [`axi/bus.py`](amaranth_soc/axi/bus.py:365). Full AXI4 `PureInterface` with optional `memory_map`.

```python
from amaranth_soc.axi import AXI4Interface

bus = AXI4Interface(addr_width=32, data_width=32, id_width=4)
bus.id_width    # 4
bus.user_width  # {"aw": 0, "w": 0, "b": 0, "ar": 0, "r": 0}
```

---

### AXI4-Lite Interconnect

#### `AXI4LiteDecoder`

Defined in [`axi/decoder.py`](amaranth_soc/axi/decoder.py:13). Routes transactions from one master to N slaves based on address. Supports pipelined operation for high throughput.

```python
from amaranth_soc.axi import AXI4LiteDecoder, AXI4LiteSRAM

decoder = AXI4LiteDecoder(addr_width=16, data_width=32)

# Add subordinate devices
rom = AXI4LiteSRAM(size=4096, data_width=32, writable=False)
ram = AXI4LiteSRAM(size=4096, data_width=32)

decoder.add(rom.bus, name="rom", addr=0x0000)
decoder.add(ram.bus, name="ram", addr=0x1000)

# The decoder's memory_map now contains both windows
decoder.memory_map  # MemoryMap with rom @ 0x0000, ram @ 0x1000
```

**Constructor parameters:**
- `addr_width` (`int`) — Address width.
- `data_width` (`32` or `64`) — Data width.
- `alignment` (`int`, default `0`) — Window alignment power-of-2 exponent.

**Members:**
- `bus` — `In(AXI4LiteSignature(...))` — upstream master-facing port.

**Methods:**
- `add(sub_bus, *, name=None, addr=None)` — Add a subordinate bus. Returns `(start, end, ratio)`.
- `align_to(alignment)` — Align the next window address.

**Properties:**
- `memory_map` — The decoder's `MemoryMap`.

**Behavior:**
- Write path FSM: `WR_IDLE` → `WR_ADDR` → `WR_DATA` → `WR_RESP` → `WR_IDLE`
- Read path FSM: `RD_IDLE` → `RD_ADDR` → `RD_RESP` → `RD_IDLE`
- Pipelined: accepts new AW/AR while previous B/R is in flight.
- Unmatched addresses receive `DECERR` response.

#### `AXI4LiteArbiter`

Defined in [`axi/arbiter.py`](amaranth_soc/axi/arbiter.py:13). Round-robin arbitration for N masters accessing one slave.

```python
from amaranth_soc.axi import AXI4LiteArbiter, AXI4LiteInterface

arbiter = AXI4LiteArbiter(addr_width=16, data_width=32)

# Add master ports
master0 = AXI4LiteInterface(addr_width=16, data_width=32)
master1 = AXI4LiteInterface(addr_width=16, data_width=32)
arbiter.add(master0, name="cpu")
arbiter.add(master1, name="dma")

# arbiter.bus is the downstream slave-facing port (Out)
```

**Constructor parameters:**
- `addr_width` (`int`) — Address width.
- `data_width` (`32` or `64`) — Data width.

**Members:**
- `bus` — `Out(AXI4LiteSignature(...))` — downstream slave-facing port.

**Methods:**
- `add(master_bus, *, name=None)` — Add a master bus to arbitrate.

**Behavior:**
- Round-robin grant selection when bus is idle.
- Transaction locking: grant is held from AW/AR handshake until B/R handshake completes.

#### `AXI4LiteCrossbar`

Defined in [`axi/crossbar.py`](amaranth_soc/axi/crossbar.py:21). Full N×M crossbar interconnect.

```python
from amaranth_soc.axi import AXI4LiteCrossbar, AXI4LiteInterface, AXI4LiteSRAM

xbar = AXI4LiteCrossbar(addr_width=16, data_width=32)

# Create master interfaces
cpu = AXI4LiteInterface(addr_width=16, data_width=32)
dma = AXI4LiteInterface(addr_width=16, data_width=32)

# Create slave devices
rom = AXI4LiteSRAM(size=4096, data_width=32, writable=False)
ram = AXI4LiteSRAM(size=4096, data_width=32)

# Add masters and slaves
xbar.add_master(cpu, name="cpu")
xbar.add_master(dma, name="dma")
xbar.add_slave(rom.bus, name="rom", addr=0x0000)
xbar.add_slave(ram.bus, name="ram", addr=0x1000)
```

**Constructor parameters:**
- `addr_width` (`int`) — Address width.
- `data_width` (`32` or `64`) — Data width.

**Methods:**
- `add_master(master_bus, *, name=None)` — Add a master port.
- `add_slave(slave_bus, *, name=None, addr=None)` — Add a slave port with address mapping.

**Internal structure:**
1. Creates N decoders (one per master) for address routing.
2. Creates M arbiters (one per slave) for master selection.
3. Wires `decoder[i].sub[j]` → `arbiter[j].master[i]` via intermediate buses.

#### `AXI4LiteTimeout`

Defined in [`axi/timeout.py`](amaranth_soc/axi/timeout.py:17). Bus watchdog that generates `SLVERR` on timeout.

```python
from amaranth_soc.axi import AXI4LiteTimeout

# 256-cycle timeout watchdog
watchdog = AXI4LiteTimeout(addr_width=16, data_width=32, timeout=256)
# watchdog.bus  — upstream (master-facing) port
# watchdog.sub  — downstream (slave-facing) port
```

**Constructor parameters:**
- `addr_width` (`int`) — Address width.
- `data_width` (`32` or `64`) — Data width.
- `timeout` (`int`, default `1024`) — Timeout in clock cycles.

**Members:**
- `bus` — `In(AXI4LiteSignature(...))` — upstream master-facing port.
- `sub` — `Out(AXI4LiteSignature(...))` — downstream slave-facing port.

**Behavior:**
- Transparent pass-through during normal operation.
- Starts counting on AW/AR handshake.
- If B/R response doesn't arrive within `timeout` cycles, generates `SLVERR`.
- Separate write and read timeout FSMs.

---

### AXI4 Full Support

#### `AXI4Decoder`

Defined in [`axi/decoder.py`](amaranth_soc/axi/decoder.py). Routes AXI4 Full transactions from one master to N slaves based on address, with burst tracking.

```python
from amaranth_soc.axi import AXI4Decoder

decoder = AXI4Decoder(addr_width=32, data_width=32, id_width=4)
# Add subordinates with burst-aware routing
```

**Features:**
- Burst-aware address routing (tracks WLAST for write bursts)
- DECERR generation for unmapped addresses
- MemoryMap integration

#### `AXI4Arbiter`

Defined in [`axi/arbiter.py`](amaranth_soc/axi/arbiter.py). Round-robin arbitration for N AXI4 Full masters with ID remapping.

```python
from amaranth_soc.axi import AXI4Arbiter

arbiter = AXI4Arbiter(addr_width=32, data_width=32, id_width=4)
# Add masters — IDs are remapped to avoid conflicts
```

**Features:**
- Round-robin or priority arbitration
- ID remapping (prepends master index to ID)
- Burst locking (AW→W→B, AR→R sequences)

#### `AXI4Crossbar`

Defined in [`axi/crossbar.py`](amaranth_soc/axi/crossbar.py). Full N×M AXI4 crossbar interconnect.

```python
from amaranth_soc.axi import AXI4Crossbar

xbar = AXI4Crossbar(addr_width=32, data_width=32, id_width=4)
# Add masters and slaves for full N×M routing
```

**Features:**
- N×M routing with ID management
- Burst tracking and ordering rules
- Composes AXI4 decoders and arbiters

#### `AXI4SRAM`

Defined in [`axi/sram.py`](amaranth_soc/axi/sram.py). AXI4 Full SRAM controller with native burst support.

```python
from amaranth_soc.axi import AXI4SRAM

sram = AXI4SRAM(size=4096, data_width=32, id_width=4)
# Handles INCR, WRAP, FIXED bursts natively
```

**Features:**
- Native burst support (INCR, WRAP, FIXED) without AXI4→AXI4-Lite adapter
- Uses `Burst2Beat` for address generation
- Byte strobes

#### `AXI4Timeout`

Defined in [`axi/timeout.py`](amaranth_soc/axi/timeout.py). Burst-level timeout wrapper for AXI4 Full.

```python
from amaranth_soc.axi import AXI4Timeout

watchdog = AXI4Timeout(addr_width=32, data_width=32, id_width=4, timeout=1024)
```

**Features:**
- Burst-level timeouts (timeout on burst completion, not individual beats)
- SLVERR generation on timeout

#### `AXIBurst2Beat`

Defined in [`axi/burst.py`](amaranth_soc/axi/burst.py:13). Converts AXI4 burst parameters to per-beat addresses per IHI0022L §A3.4.1.

```python
from amaranth_soc.axi import AXIBurst2Beat

b2b = AXIBurst2Beat(addr_width=32, data_width=32)
# b2b.addr      — In(32): start address
# b2b.len       — In(8):  burst length - 1
# b2b.size      — In(3):  transfer size encoding
# b2b.burst     — In(2):  burst type (FIXED/INCR/WRAP)
# b2b.first     — In(1):  pulse to load new burst
# b2b.next      — In(1):  pulse to advance to next beat
# b2b.next_addr — Out(32): current beat address
# b2b.last      — Out(1):  high on final beat
```

**Constructor parameters:**
- `addr_width` (`int`) — Address width. Must be ≥ 1.
- `data_width` (`int`) — Data width. Must be a power of 2 and ≥ 8.

**Supports all three burst types:**
- **FIXED** — address stays the same for every beat.
- **INCR** — address increments by `1 << size` each beat.
- **WRAP** — address wraps within a boundary of `(len + 1) * (1 << size)` bytes.

#### `AXI4ToAXI4Lite`

Defined in [`axi/adapter.py`](amaranth_soc/axi/adapter.py:15). Decomposes AXI4 burst transactions into individual AXI4-Lite transactions.

```python
from amaranth_soc.axi import AXI4ToAXI4Lite

adapter = AXI4ToAXI4Lite(addr_width=32, data_width=32, id_width=4)
# adapter.axi4_bus     — In(AXI4Signature(...))     — AXI4 upstream slave port
# adapter.axi4lite_bus — Out(AXI4LiteSignature(...)) — AXI4-Lite downstream master port
```

**Constructor parameters:**
- `addr_width` (`int`) — Address width. Must be ≥ 1.
- `data_width` (`32` or `64`) — Data width.
- `id_width` (`int`, default `4`) — AXI4 ID width.

**Behavior:**
- Write path: accepts AW, then for each W beat issues an AXI4-Lite AW+W, collects B responses, sends single B upstream with worst response.
- Read path: accepts AR, then for each beat issues AXI4-Lite AR, collects R data, forwards upstream with correct `rlast`.
- Strips ID, cache, QoS, region, and user signals.

---

### Wishbone Bus Layer

#### Wishbone Crossbar

Defined in [`wishbone/bus.py`](amaranth_soc/wishbone/bus.py). Full N×M Wishbone crossbar interconnect.

```python
from amaranth_soc.wishbone import Crossbar

xbar = Crossbar(addr_width=16, data_width=32, granularity=8)
# Add masters and slaves similar to AXI4LiteCrossbar
```

#### Wishbone Burst Support

The Wishbone Decoder and Arbiter now support burst-aware routing:
- **Decoder:** Holds address decode for the duration of a burst (CTI != 0b111 end-of-burst).
- **Arbiter:** Does not re-arbitrate during a burst, maintaining lock until burst completes.

---

### Cross-Bus Bridges

#### `WishboneToAXI4Lite`

Defined in [`bridge/wb_to_axi.py`](amaranth_soc/bridge/wb_to_axi.py:15). Converts Wishbone Classic cycles to AXI4-Lite transactions.

```python
from amaranth_soc.bridge import WishboneToAXI4Lite

bridge = WishboneToAXI4Lite(addr_width=14, data_width=32, granularity=8)
# bridge.wb_bus  — In(WBSignature(...))          — Wishbone slave port
# bridge.axi_bus — Out(AXI4LiteSignature(...))   — AXI4-Lite master port
```

**Constructor parameters:**
- `addr_width` (`int`) — Wishbone word address width.
- `data_width` (`32` or `64`) — Data width.
- `granularity` (`8`, `16`, `32`, or `64`, default `8`) — Wishbone granularity.

**Address conversion:** AXI byte address = Wishbone word address << log2(data_width / granularity).

**FSM states:**

```
IDLE → WRITE_ADDR → WRITE_RESP → IDLE
     ↘ WRITE_DATA ↗
     ↘ WRITE_ADDR_PENDING ↗
IDLE → READ_ADDR → READ_DATA → IDLE
```

#### `AXI4LiteToWishbone`

Defined in [`bridge/axi_to_wb.py`](amaranth_soc/bridge/axi_to_wb.py:15). Converts AXI4-Lite transactions to Wishbone Classic cycles.

```python
from amaranth_soc.bridge import AXI4LiteToWishbone

bridge = AXI4LiteToWishbone(addr_width=16, data_width=32, granularity=8)
# bridge.axi_bus — In(AXI4LiteSignature(...))  — AXI4-Lite slave port
# bridge.wb_bus  — Out(WBSignature(...))        — Wishbone master port
```

**Constructor parameters:**
- `addr_width` (`int`) — AXI byte address width.
- `data_width` (`32` or `64`) — Data width.
- `granularity` (`8`, `16`, `32`, or `64`, default `8`) — Wishbone granularity.

**FSM states:**

```
IDLE → WR_DATA → WR_CYCLE → WR_RESP → IDLE
IDLE → RD_CYCLE → RD_RESP → IDLE
```

- Wishbone `err` maps to AXI `SLVERR`.
- Write takes priority over read when both AW and AR are valid.

#### `BusAdapter` (registry)

Defined in [`bridge/registry.py`](amaranth_soc/bridge/registry.py:11). Automatic bridge selection with direct and two-hop chains.

```python
from amaranth_soc import BusStandard
from amaranth_soc.bridge import BusAdapter

# Check if adaptation is possible
BusAdapter.can_adapt(BusStandard.WISHBONE, BusStandard.AXI4_LITE)  # True
BusAdapter.can_adapt(BusStandard.AXI4, BusStandard.WISHBONE)       # True (two-hop via AXI4-Lite)

# Get the bridge chain
chain = BusAdapter.get_bridge_chain(BusStandard.WISHBONE, BusStandard.AXI4_LITE)
# → [(WishboneToAXI4Lite, BusStandard.WISHBONE, BusStandard.AXI4_LITE)]

chain = BusAdapter.get_bridge_chain(BusStandard.AXI4, BusStandard.WISHBONE)
# → [(AXI4ToAXI4Lite, AXI4, AXI4_LITE), (AXI4LiteToWishbone, AXI4_LITE, WISHBONE)]

# Same standard → empty chain
BusAdapter.get_bridge_chain(BusStandard.AXI4_LITE, BusStandard.AXI4_LITE)  # []

# List all registered bridges
BusAdapter.list_bridges()
# {(WISHBONE, AXI4_LITE): WishboneToAXI4Lite,
#  (AXI4_LITE, WISHBONE): AXI4LiteToWishbone,
#  (AXI4, AXI4_LITE): AXI4ToAXI4Lite}
```

**Pre-registered bridges:**

| From | To | Bridge Class |
|------|----|-------------|
| `WISHBONE` | `AXI4_LITE` | `WishboneToAXI4Lite` |
| `AXI4_LITE` | `WISHBONE` | `AXI4LiteToWishbone` |
| `AXI4` | `AXI4_LITE` | `AXI4ToAXI4Lite` |

**Class methods:**
- `register(from_standard, to_standard, bridge_class)` — Register a new bridge.
- `can_adapt(from_standard, to_standard)` → `bool` — Check if adaptation is possible.
- `get_bridge_chain(from_standard, to_standard)` → `list[(class, from, to)]` — Get bridge chain.
- `adapt(interface, from_standard, to_standard, **kwargs)` — Create bridge instance(s).
- `list_bridges()` → `dict` — List all registered bridges.

---

### CSR Bridge

#### `AXI4LiteCSRBridge`

Defined in [`csr/axi_lite.py`](amaranth_soc/csr/axi_lite.py:15). Bridges AXI4-Lite to the amaranth-soc CSR bus.

```python
from amaranth_soc import csr
from amaranth_soc.memory import MemoryMap
from amaranth_soc.csr import AXI4LiteCSRBridge

# Create a CSR bus (e.g., from a Multiplexer or Decoder)
csr_bus = csr.Decoder(addr_width=10, data_width=8)
# ... add registers to csr_bus ...

# Bridge it to AXI4-Lite with 32-bit data width
bridge = AXI4LiteCSRBridge(csr_bus.bus, data_width=32, name="csr")
# bridge.axi_bus — In(AXI4LiteSignature(...)) — AXI4-Lite slave port
```

**Constructor parameters:**
- `csr_bus` — `csr.Interface` — The CSR bus to bridge.
- `data_width` (`int`, optional) — AXI4-Lite data width. Defaults to `csr_bus.data_width`.
- `name` (`str`, optional) — Window name in the memory map.

**Multi-beat access:**

When `data_width > csr_bus.data_width`, each AXI4-Lite transaction maps to multiple CSR beats. For example, with 32-bit AXI and 8-bit CSR:
- Each AXI write drives 4 consecutive CSR write beats (LSB first).
- Each AXI read performs 4 consecutive CSR read beats and assembles the result.
- Latency: `data_width // csr_data_width + 1` cycles.

---

### DMA Infrastructure

#### `DMAReader`

Defined in [`dma/reader.py`](amaranth_soc/dma/reader.py). DMA read engine with configurable FIFO depths.

```python
from amaranth_soc.dma import DMAReader

reader = DMAReader(addr_width=32, data_width=32)
```

#### `DMAWriter`

Defined in [`dma/writer.py`](amaranth_soc/dma/writer.py). DMA write engine.

```python
from amaranth_soc.dma import DMAWriter

writer = DMAWriter(addr_width=32, data_width=32)
```

#### `ScatterGatherDMA`

Defined in [`dma/scatter_gather.py`](amaranth_soc/dma/scatter_gather.py). Scatter-gather descriptor tables with loop/program modes.

```python
from amaranth_soc.dma import ScatterGatherDMA

sg_dma = ScatterGatherDMA(addr_width=32, data_width=32, max_descriptors=16)
```

---

### Peripherals

#### `TimerPeripheral`

Defined in [`periph/timer.py`](amaranth_soc/periph/timer.py:53). Countdown timer with CSR interface and IRQ output.

```python
from amaranth_soc.periph import TimerPeripheral

timer = TimerPeripheral(width=32, csr_data_width=8)
# timer.bus — In(CSRSignature(...)) — CSR bus interface
# timer.irq — Out(1)               — interrupt output
```

**Constructor parameters:**
- `width` (`int`) — Counter width in bits (1–32).
- `csr_data_width` (`int`, default `8`) — CSR bus data width.

**CSR Register Map:**

| Register | Access | Description |
|----------|--------|-------------|
| `reload` | RW | Reload value (counter resets to this on zero) |
| `enable` | RW | Timer enable (1 bit) |
| `counter` | R | Current counter value |
| `ev_status` | R | Raw zero event status |
| `ev_pending` | RW1C | Event pending (write 1 to clear) |
| `ev_enable` | RW | Event enable |

**Behavior:**
- When enabled, counter counts down from `reload` value.
- When counter reaches 0, `ev_pending` is set and counter reloads.
- `irq` output = `ev_pending & ev_enable`.

#### `InterruptController`

Defined in [`periph/intc.py`](amaranth_soc/periph/intc.py:29). Aggregates N IRQ sources into a single CPU interrupt with edge/level detection and priority encoding.

```python
from amaranth_soc.periph import InterruptController

intc = InterruptController(n_irqs=8, csr_data_width=8)
# intc.bus        — In(CSRSignature(...)) — CSR bus interface
# intc.irq_inputs — In(8)                — individual IRQ inputs
# intc.irq_out    — Out(1)               — aggregated interrupt output
```

**Constructor parameters:**
- `n_irqs` (`int`) — Number of IRQ inputs (1–32).
- `csr_data_width` (`int`, default `8`) — CSR bus data width.

**CSR Register Map:**

| Register | Access | Description |
|----------|--------|-------------|
| `pending` | RW1C | Pending IRQs (1 bit per IRQ, write-1-to-clear) |
| `enable` | RW | IRQ enable mask (1 bit per IRQ) |

**IRQ flow:**
1. Rising edge on `irq_inputs[n]` sets `pending[n]`.
2. Software reads `pending` to see which IRQs fired.
3. `irq_out` = `(pending & enable).any()` — asserted if any enabled IRQ is pending.
4. Software clears pending bits by writing 1 to them.

#### `MSIController`

Defined in [`periph/msi.py`](amaranth_soc/periph/msi.py). MSI/MSI-X interrupt controller with per-vector address/data/mask configuration.

```python
from amaranth_soc.periph import MSIController

msi = MSIController(n_vectors=8, csr_data_width=8)
```

**Features:**
- Per-vector address/data/mask tables (MSI-X style)
- Priority encoding for vector selection
- Stream output with valid/ready handshaking for MSI delivery
- Integration with the event system

---

### SoC Builder

#### `SoCBuilder`

Defined in [`soc/builder.py`](amaranth_soc/soc/builder.py:18). Bus-agnostic SoC configuration object.

```python
from amaranth_soc import BusStandard
from amaranth_soc.soc import SoCBuilder
from amaranth_soc.periph import TimerPeripheral

builder = SoCBuilder(
    bus_standard=BusStandard.AXI4_LITE,
    bus_addr_width=24,
    bus_data_width=32,
    csr_data_width=8,
    csr_addr_width=14,
    n_irqs=32,
)

# Add memory regions
builder.add_rom(name="rom", size=8192, addr=0x000000)
builder.add_ram(name="ram", size=16384, addr=0x100000)

# Add peripherals
timer = TimerPeripheral(width=32)
builder.add_peripheral(timer, name="timer", irq=0)

# Build the SoC
soc = builder.build()
```

**Constructor parameters:**
- `bus_standard` (`BusStandard`) — System bus standard. Supports `AXI4_LITE`, `AXI4`, and `WISHBONE`.
- `bus_addr_width` (`int`) — System bus address width.
- `bus_data_width` (`int`) — System bus data width.
- `csr_data_width` (`int`, default `8`) — CSR bus data width.
- `csr_addr_width` (`int`, default `14`) — CSR bus address width.
- `n_irqs` (`int`, default `32`) — Number of IRQ lines.

**Methods (all return `self` for chaining):**
- `add_rom(*, name="rom", size, init=None, addr=None)` — Add read-only SRAM.
- `add_ram(*, name="ram", size, addr=None)` — Add read-write SRAM.
- `add_peripheral(peripheral, *, name, addr=None, irq=None)` — Add a CSR peripheral.
- `build()` → `SoC` — Build and return the SoC component.

**Enhanced features:**
- Automatic bus bridge insertion when mixing Wishbone and AXI4 peripherals
- PCIe BAR mapping as a first-class concept
- DMA channel configuration
- Interrupt routing (MSI/MSI-X generation from event sources)

#### `SoC`

Defined in [`soc/builder.py`](amaranth_soc/soc/builder.py:164). The built SoC component (Amaranth `wiring.Component`).

**Members:**
- `bus` — `In(AXI4LiteSignature(...))` — system bus port (connect CPU here).
- `irq_out` — `Out(1)` — aggregated interrupt output.

**Internal structure (AXI4-Lite):**
- `AXI4LiteDecoder` as the main bus fabric.
- `AXI4LiteSRAM` instances for ROM and RAM.
- `csr.Decoder` + `AXI4LiteCSRBridge` for peripheral CSR access.
- `InterruptController` for IRQ aggregation.

---

### Software Export

#### `CHeaderGenerator`

Defined in [`export/c_header.py`](amaranth_soc/export/c_header.py:9). Generates C `#define` macros from memory maps.

```python
from amaranth_soc.export import CHeaderGenerator
from amaranth_soc.memory import MemoryMap

# From a memory map (e.g., from decoder.memory_map)
memory_map = ...  # MemoryMap with windows/resources
header = CHeaderGenerator.generate(memory_map, base_addr=0x80000000)
print(header)
```

**Static methods:**

##### `CHeaderGenerator.generate(memory_map, *, base_addr=0)`

Generates `#define` macros for memory regions.

**Parameters:**
- `memory_map` (`MemoryMap`) — The SoC memory map.
- `base_addr` (`int`, default `0`) — Base address offset.

**Returns:** `str` — C header content.

**Example output:**
```c
#ifndef __SOC_H
#define __SOC_H

/* Auto-generated by amaranth-soc */

#define ROM_BASE  0x80000000UL
#define ROM_SIZE  0x00002000UL
#define RAM_BASE  0x80100000UL
#define RAM_SIZE  0x00004000UL
#define ROM_MEM_BASE  0x80000000UL
#define ROM_MEM_SIZE  0x00002000UL

#endif /* __SOC_H */
```

##### `CHeaderGenerator.generate_irq_header(irq_map, *, guard="__SOC_IRQ_H")`

Generates `#define` macros for IRQ assignments.

**Parameters:**
- `irq_map` (`dict`) — Mapping of IRQ name to IRQ number.
- `guard` (`str`, default `"__SOC_IRQ_H"`) — Include guard macro name.

**Returns:** `str` — C header content.

```python
header = CHeaderGenerator.generate_irq_header({
    "timer": 0,
    "uart": 1,
    "spi": 2,
})
print(header)
```

**Output:**
```c
#ifndef __SOC_IRQ_H
#define __SOC_IRQ_H

/* Auto-generated IRQ assignments by amaranth-soc */

#define IRQ_TIMER  0
#define IRQ_UART  1
#define IRQ_SPI  2

#endif /* __SOC_IRQ_H */
```

#### `SVDGenerator`

Defined in [`export/svd.py`](amaranth_soc/export/svd.py). Generates CMSIS-SVD XML files for IDE debug tools.

#### `LinkerScriptGenerator`

Defined in [`export/linker.py`](amaranth_soc/export/linker.py). Generates linker scripts for firmware builds.

#### `DeviceTreeGenerator`

Defined in [`export/devicetree.py`](amaranth_soc/export/devicetree.py). Generates Linux device tree source files.

---

### Simulation Helpers

Defined in [`sim/axi.py`](amaranth_soc/sim/axi.py:1). Async testbench helpers for AXI4-Lite and AXI4 Full simulation.

#### `axi_lite_write(ctx, bus, addr, data, strb=None, expected_resp=AXIResp.OKAY)`

Perform an AXI4-Lite write transaction in an async testbench.

**Parameters:**
- `ctx` — `SimulatorContext` from an async testbench.
- `bus` — `AXI4LiteInterface` to drive.
- `addr` (`int`) — Write address.
- `data` (`int`) — Write data.
- `strb` (`int` or `None`) — Write strobe. If `None`, all bytes enabled.
- `expected_resp` (`AXIResp`, default `OKAY`) — Expected response (asserted).

**Returns:** `AXIResp` — The actual response code.

**Raises:** `TimeoutError` after 100 cycles, `AssertionError` if response doesn't match.

#### `axi_lite_read(ctx, bus, addr, expected_resp=AXIResp.OKAY)`

Perform an AXI4-Lite read transaction in an async testbench.

**Parameters:**
- `ctx` — `SimulatorContext` from an async testbench.
- `bus` — `AXI4LiteInterface` to drive.
- `addr` (`int`) — Read address.
- `expected_resp` (`AXIResp`, default `OKAY`) — Expected response (asserted).

**Returns:** `tuple(int, AXIResp)` — The read data and response code.

**Raises:** `TimeoutError` after 100 cycles, `AssertionError` if response doesn't match.

**Usage in async testbench:**

```python
from amaranth.sim import Simulator
from amaranth_soc.axi import AXI4LiteSRAM
from amaranth_soc.sim import axi_lite_write, axi_lite_read

sram = AXI4LiteSRAM(size=256, data_width=32)
sim = Simulator(sram)
sim.add_clock(1e-6)

async def testbench(ctx):
    await axi_lite_write(ctx, sram.bus, addr=0x10, data=0x12345678)
    data, resp = await axi_lite_read(ctx, sram.bus, addr=0x10)
    assert data == 0x12345678

sim.add_testbench(testbench)
with sim.write_vcd("test.vcd"):
    sim.run()
```

#### AXI4 Full Simulation Helpers

AXI4 Full simulation helpers with burst generation, ID tracking, and response checking are available in [`sim/axi.py`](amaranth_soc/sim/axi.py).

### Wishbone Simulation Helpers

Defined in [`sim/wishbone.py`](amaranth_soc/sim/wishbone.py:1). Async testbench helpers for Wishbone Classic and pipelined simulation.

#### `wb_write(ctx, bus, addr, data, sel=None)`

Perform a Wishbone Classic write cycle in an async testbench.

**Parameters:**
- `ctx` — `SimulatorContext` from an async testbench.
- `bus` — Wishbone `Interface` to drive.
- `addr` (`int`) — Write address (word-addressed).
- `data` (`int`) — Write data.
- `sel` (`int` or `None`) — Byte select. If `None`, all bytes enabled.

**Returns:** `bool` — `True` if acknowledged, `False` if error.

#### `wb_read(ctx, bus, addr)`

Perform a Wishbone Classic read cycle in an async testbench.

**Parameters:**
- `ctx` — `SimulatorContext` from an async testbench.
- `bus` — Wishbone `Interface` to drive.
- `addr` (`int`) — Read address (word-addressed).

**Returns:** `tuple(int, bool)` — The read data and ack status.

#### `wb_write_pipelined(ctx, bus, addr, data, sel=None)`

Perform a Wishbone pipelined write cycle (uses `stall` signal).

#### `wb_read_pipelined(ctx, bus, addr)`

Perform a Wishbone pipelined read cycle (uses `stall` signal).

**Usage:**

```python
from amaranth_soc.sim import wb_write, wb_read

# In an async testbench:
await wb_write(ctx, bus, addr=0x00, data=0xDEADBEEF)
data, ack = await wb_read(ctx, bus, addr=0x00)
```

---

### Bus Protocol Checkers

Defined in [`sim/protocol_checker.py`](amaranth_soc/sim/protocol_checker.py). Assertion-based checkers for bus protocol verification during simulation.

**Supported protocols:**
- **Wishbone:** `cyc` must be asserted with `stb`, `ack` must not assert without `stb`
- **AXI4-Lite:** No burst signals, single-beat only
- **AXI4 Full:** `WLAST` must match `AWLEN`, response ordering must match request ordering

---

### SoC Builder Handler Architecture

The SoC builder uses a handler-based architecture to support multiple bus standards. The monolithic builder has been decomposed into pluggable handlers:

| Handler | File | Description |
|---------|------|-------------|
| `BusHandler` (ABC) | [`soc/bus_handler.py`](amaranth_soc/soc/bus_handler.py:1) | Abstract base class for bus topology handlers |
| `AXI4LiteBusHandler` | [`soc/bus_handler.py`](amaranth_soc/soc/bus_handler.py) | AXI4-Lite bus topology (decoder, SRAM, CSR bridge) |
| `AXI4BusHandler` | [`soc/bus_handler.py`](amaranth_soc/soc/bus_handler.py) | AXI4 Full bus topology (decoder, SRAM, CSR bridge) |
| `WishboneBusHandler` | [`soc/bus_handler.py`](amaranth_soc/soc/bus_handler.py) | Wishbone bus topology (decoder, SRAM, CSR bridge) |
| `CSRHandler` | [`soc/csr_handler.py`](amaranth_soc/soc/csr_handler.py:1) | CSR map and multiplexer management |
| `IRQHandler` | [`soc/irq_handler.py`](amaranth_soc/soc/irq_handler.py:1) | IRQ routing and interrupt controller |

The `SoCBuilder` automatically selects the appropriate `BusHandler` based on the `bus_standard` parameter:

```python
from amaranth_soc import BusStandard
from amaranth_soc.soc import SoCBuilder

# AXI4-Lite SoC (uses AXI4LiteBusHandler internally)
builder = SoCBuilder(bus_standard=BusStandard.AXI4_LITE, bus_addr_width=24, bus_data_width=32)

# AXI4 Full SoC (uses AXI4BusHandler internally)
builder = SoCBuilder(bus_standard=BusStandard.AXI4, bus_addr_width=32, bus_data_width=32)

# Wishbone SoC (uses WishboneBusHandler internally)
builder = SoCBuilder(bus_standard=BusStandard.WISHBONE, bus_addr_width=24, bus_data_width=32)
```

---

## Examples

### Example 1: AXI4-Lite SRAM Read/Write Simulation

A complete, runnable simulation that writes data to SRAM and reads it back.

```python
from amaranth import *
from amaranth.sim import Simulator

from amaranth_soc.axi import AXI4LiteSRAM, AXIResp
from amaranth_soc.sim import axi_lite_write, axi_lite_read


def test_sram_read_write():
    """Write several values to SRAM and read them back."""
    sram = AXI4LiteSRAM(size=1024, data_width=32)

    sim = Simulator(sram)
    sim.add_clock(1e-6)

    async def testbench(ctx):
        # Write test pattern
        test_data = {
            0x000: 0xDEADBEEF,
            0x004: 0xCAFEBABE,
            0x008: 0x12345678,
            0x0FC: 0xFFFFFFFF,
        }

        for addr, data in test_data.items():
            await axi_lite_write(ctx, sram.bus, addr=addr, data=data)

        # Read back and verify
        for addr, expected in test_data.items():
            data, resp = await axi_lite_read(ctx, sram.bus, addr=addr)
            assert data == expected, f"@0x{addr:03X}: got 0x{data:08X}, expected 0x{expected:08X}"
            assert resp == AXIResp.OKAY

        # Test byte strobe: write only byte 1 (bits 15:8)
        await axi_lite_write(ctx, sram.bus, addr=0x000, data=0x00AA0000, strb=0b0010)
        data, _ = await axi_lite_read(ctx, sram.bus, addr=0x000)
        # Byte 0 = 0xEF (unchanged), byte 1 = 0xAA (written), bytes 2-3 = 0xDEAD (unchanged)
        # Result depends on SRAM implementation — byte 1 is overwritten
        print(f"After byte strobe write: 0x{data:08X}")

    sim.add_testbench(testbench)
    with sim.write_vcd("sram_test.vcd"):
        sim.run()
    print("SRAM test passed!")


if __name__ == "__main__":
    test_sram_read_write()
```

### Example 2: Building a Simple SoC

Configure and build a SoC with ROM, RAM, timer, and interrupt controller.

```python
from amaranth_soc import BusStandard
from amaranth_soc.soc import SoCBuilder
from amaranth_soc.periph import TimerPeripheral


def build_simple_soc():
    """Build a minimal SoC with ROM, RAM, and a timer."""
    # Configure the SoC
    builder = SoCBuilder(
        bus_standard=BusStandard.AXI4_LITE,
        bus_addr_width=24,
        bus_data_width=32,
        csr_data_width=8,
        n_irqs=4,
    )

    # Add memory: 8 KiB ROM at 0x000000, 16 KiB RAM at 0x100000
    builder.add_rom(name="rom", size=8192, addr=0x000000)
    builder.add_ram(name="ram", size=16384, addr=0x100000)

    # Add a 32-bit countdown timer on IRQ 0
    timer = TimerPeripheral(width=32, csr_data_width=8)
    builder.add_peripheral(timer, name="timer", irq=0)

    # Build the SoC
    soc = builder.build()

    print(f"SoC bus standard: {soc.bus_standard}")
    print(f"SoC bus port: addr_width={soc.bus.addr_width}, data_width={soc.bus.data_width}")
    return soc


if __name__ == "__main__":
    soc = build_simple_soc()
    print("SoC built successfully!")
```

### Example 3: Cross-Bus Bridge Usage

Connect a Wishbone master to an AXI4-Lite slave using the bridge.

```python
from amaranth_soc.bridge import WishboneToAXI4Lite, AXI4LiteToWishbone, BusAdapter
from amaranth_soc import BusStandard


def demo_bridges():
    """Demonstrate bridge construction and the BusAdapter registry."""

    # Direct bridge: Wishbone → AXI4-Lite
    wb_to_axi = WishboneToAXI4Lite(addr_width=14, data_width=32, granularity=8)
    print(f"WB→AXI bridge: wb_bus addr_width={wb_to_axi.addr_width}, "
          f"axi_bus addr_width={wb_to_axi.axi_bus.addr_width}")

    # Direct bridge: AXI4-Lite → Wishbone
    axi_to_wb = AXI4LiteToWishbone(addr_width=16, data_width=32, granularity=8)
    print(f"AXI→WB bridge: axi_bus addr_width={axi_to_wb.addr_width}, "
          f"wb_bus addr_width={axi_to_wb.wb_bus.addr_width}")

    # Use BusAdapter registry for automatic bridge selection
    print("\n--- BusAdapter Registry ---")
    print(f"WB → AXI4-Lite: {BusAdapter.can_adapt(BusStandard.WISHBONE, BusStandard.AXI4_LITE)}")
    print(f"AXI4 → WB (two-hop): {BusAdapter.can_adapt(BusStandard.AXI4, BusStandard.WISHBONE)}")
    print(f"AXI4-Lite → AXI4-Lite: {BusAdapter.can_adapt(BusStandard.AXI4_LITE, BusStandard.AXI4_LITE)}")

    # Get bridge chain for AXI4 → Wishbone (two-hop)
    chain = BusAdapter.get_bridge_chain(BusStandard.AXI4, BusStandard.WISHBONE)
    for bridge_cls, from_std, to_std in chain:
        print(f"  {bridge_cls.__name__}: {from_std.value} → {to_std.value}")


if __name__ == "__main__":
    demo_bridges()
```

### Example 4: Generating C Headers

Export memory map and IRQ assignments to C header files.

```python
from amaranth_soc.export import CHeaderGenerator


def demo_c_header():
    """Generate C headers for IRQ assignments."""

    # Generate IRQ header
    irq_map = {
        "timer": 0,
        "uart": 1,
        "spi": 2,
        "i2c": 3,
    }
    irq_header = CHeaderGenerator.generate_irq_header(irq_map)
    print("=== IRQ Header ===")
    print(irq_header)

    # For memory map header, you need a MemoryMap from a built SoC.
    # Here's how it works with a decoder:
    from amaranth_soc.axi import AXI4LiteDecoder, AXI4LiteSRAM

    decoder = AXI4LiteDecoder(addr_width=16, data_width=32)
    rom = AXI4LiteSRAM(size=4096, data_width=32, writable=False)
    ram = AXI4LiteSRAM(size=4096, data_width=32)
    decoder.add(rom.bus, name="rom", addr=0x0000)
    decoder.add(ram.bus, name="ram", addr=0x1000)

    header = CHeaderGenerator.generate(decoder.memory_map, base_addr=0x80000000)
    print("\n=== Memory Map Header ===")
    print(header)


if __name__ == "__main__":
    demo_c_header()
```

### Example 5: Custom Peripheral with CSR Registers

How to create a new peripheral following the CSR pattern used by `TimerPeripheral`.

```python
from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out, connect, flipped
from amaranth.utils import ceil_log2

from amaranth_soc import csr
from amaranth_soc.csr import action as csr_action
from amaranth_soc.csr.bus import Multiplexer, Signature as CSRSignature
from amaranth_soc.memory import MemoryMap


class _ControlReg(csr.Register, access="rw"):
    """Control register with enable and mode fields."""
    def __init__(self):
        super().__init__({
            "enable": csr.Field(csr_action.RW, 1),
            "mode":   csr.Field(csr_action.RW, 2),
        })


class _StatusReg(csr.Register, access="r"):
    """Read-only status register."""
    def __init__(self):
        super().__init__({
            "busy":  csr.Field(csr_action.R, 1),
            "error": csr.Field(csr_action.R, 1),
        })


class _DataReg(csr.Register, access="rw"):
    """Data register."""
    def __init__(self, width):
        super().__init__({"data": csr.Field(csr_action.RW, width)})


class MyPeripheral(wiring.Component):
    """Example custom peripheral with CSR interface.

    CSR Registers:
    - control (RW): enable (1 bit) + mode (2 bits)
    - status (R): busy (1 bit) + error (1 bit)
    - data (RW): 16-bit data register

    Parameters
    ----------
    csr_data_width : int
        CSR bus data width. Default 8.
    """
    def __init__(self, *, csr_data_width=8):
        # Step 1: Create CSR register instances
        self._control_reg = _ControlReg()
        self._status_reg = _StatusReg()
        self._data_reg = _DataReg(16)

        # Step 2: Build CSR memory map
        memory_map = MemoryMap(addr_width=4, data_width=csr_data_width)
        memory_map.add_resource(self._control_reg, size=1, name=("control",))
        memory_map.add_resource(self._status_reg, size=1, name=("status",))
        memory_map.add_resource(self._data_reg, size=2, name=("data",))

        # Step 3: Create Multiplexer for register access
        self._mux = Multiplexer(memory_map)

        # Step 4: Define component signature
        csr_sig = CSRSignature(
            addr_width=memory_map.addr_width,
            data_width=memory_map.data_width,
        )
        super().__init__({
            "bus": In(csr_sig),
            "irq": Out(1),
        })
        self.bus.memory_map = memory_map

    def elaborate(self, platform):
        m = Module()

        # Step 5: Add submodules
        m.submodules.mux = self._mux
        m.submodules.control = self._control_reg
        m.submodules.status = self._status_reg
        m.submodules.data = self._data_reg

        # Step 6: Connect CSR bus to multiplexer
        connect(m, flipped(self.bus), self._mux.bus)

        # Step 7: Implement peripheral logic
        enable = self._control_reg.f.enable.data
        mode = self._control_reg.f.mode.data
        data_val = self._data_reg.f.data.data

        # Example: busy when enabled and data is non-zero
        m.d.comb += self._status_reg.f.busy.r_data.eq(enable & (data_val != 0))
        m.d.comb += self._status_reg.f.error.r_data.eq(0)

        # IRQ: fire when enabled and data reaches a threshold
        m.d.comb += self.irq.eq(enable & (data_val > 0x8000))

        return m


# Instantiate and verify
periph = MyPeripheral(csr_data_width=8)
print(f"MyPeripheral CSR bus: addr_width={periph.bus.addr_width}, "
      f"data_width={periph.bus.data_width}")
print("Custom peripheral created successfully!")
```

### Example 6: AXI4-Lite Decoder with Multiple Slaves

Demonstrates address-based routing with the decoder.

```python
from amaranth_soc.axi import AXI4LiteDecoder, AXI4LiteSRAM


def demo_decoder():
    """Build a decoder with multiple SRAM regions."""
    decoder = AXI4LiteDecoder(addr_width=20, data_width=32)

    # Create memory regions
    boot_rom = AXI4LiteSRAM(size=4096, data_width=32, writable=False,
                             init=[0x00000013] * 1024)  # NOP instructions
    main_ram = AXI4LiteSRAM(size=65536, data_width=32)
    io_ram   = AXI4LiteSRAM(size=256, data_width=32)

    # Add to decoder with explicit addresses
    decoder.add(boot_rom.bus, name="boot_rom", addr=0x00000)
    decoder.add(main_ram.bus, name="main_ram", addr=0x10000)
    decoder.add(io_ram.bus,   name="io_ram",   addr=0x20000)

    # Inspect the memory map
    for window, name, (start, end, ratio) in decoder.memory_map.windows():
        name_str = ".".join(str(n) for n in name)
        print(f"  {name_str}: 0x{start:05X} - 0x{end:05X} (ratio={ratio})")

    return decoder


if __name__ == "__main__":
    dec = demo_decoder()
    print("Decoder configured successfully!")
```

### Example 7: AXI4 Burst Adapter

Convert AXI4 full burst transactions to AXI4-Lite.

```python
from amaranth_soc.axi import AXI4ToAXI4Lite, AXI4Signature, AXI4LiteSignature


def demo_burst_adapter():
    """Create an AXI4 → AXI4-Lite adapter."""
    adapter = AXI4ToAXI4Lite(addr_width=32, data_width=32, id_width=4)

    print(f"AXI4 upstream port:")
    print(f"  addr_width = {adapter.addr_width}")
    print(f"  data_width = {adapter.data_width}")
    print(f"  id_width   = {adapter.id_width}")
    print(f"AXI4-Lite downstream port:")
    print(f"  addr_width = {adapter.axi4lite_bus.addr_width}")
    print(f"  data_width = {adapter.axi4lite_bus.data_width}")

    return adapter


if __name__ == "__main__":
    demo_burst_adapter()
```

---

## Testing

Run the full test suite:

```bash
cd amaranth-soc && pdm run pytest tests/ -v
```

Run with coverage:

```bash
cd amaranth-soc && pdm run pytest tests/ -v --cov=amaranth_soc --cov-report=term-missing
```

Run a specific test file:

```bash
cd amaranth-soc && pdm run pytest tests/test_axi_sram.py -v
```

### Test Coverage Summary

**860 tests across 34 test files:**

| Test File | Tests | Coverage |
|-----------|------:|---------|
| `test_csr_reg.py` | 78 | CSR register infrastructure, element-based ownership |
| `test_memory.py` | 64 | Memory maps, BAR-relative addressing |
| `test_bridges.py` | 48 | WB↔AXI bridges, AXI4→AXI4-Lite adapter |
| `test_axi_bus.py` | 46 | AXI enums, signatures, interfaces, memory maps, relaxed data width |
| `test_axi_timeout.py` | 44 | AXI4-Lite + AXI4 Full timeout watchdog |
| `test_axi_crossbar.py` | 44 | AXI4-Lite + AXI4 Full NxM crossbar |
| `test_wishbone_bus.py` | 40 | Wishbone bus, decoder, arbiter, crossbar |
| `test_endianness.py` | 37 | Endianness support, byte-swap logic |
| `test_axi_decoder.py` | 34 | AXI4-Lite + AXI4 Full decoder with pipelining |
| `test_soc_handlers.py` | 31 | SoC builder handler unit tests |
| `test_csr_bus.py` | 31 | CSR bus, Multiplexer, Decoder |
| `test_csr_comprehensive.py` | 28 | Comprehensive CSR tests |
| `test_axi_arbiter.py` | 26 | AXI4-Lite + AXI4 Full arbiter |
| `test_axi_sram.py` | 25 | AXI4-Lite + AXI4 Full SRAM |
| `test_wb_crossbar.py` | 24 | Wishbone crossbar |
| `test_soc_builder_enhanced.py` | 24 | Enhanced SoC builder |
| `test_bar_memory.py` | 24 | BAR-relative memory map |
| `test_event.py` | 23 | Event handling |
| `test_dma.py` | 21 | DMA reader, writer, scatter-gather |
| `test_axi_burst.py` | 21 | Burst-to-beat address generator |
| `test_stubs.py` | 18 | All stub files have content |
| `test_bus_adapter.py` | 18 | Bridge registry |
| `test_sim_helpers.py` | 17 | Simulation helpers |
| `test_intc.py` | 17 | Interrupt controller, MSI |
| `test_protocol_checker.py` | 14 | Bus protocol checkers |
| `test_csr_action.py` | 14 | CSR field action types |
| `test_axi4_bus_handler.py` | 12 | AXI4 Full bus handler |
| `test_wishbone_sram.py` | 8 | Wishbone SRAM |
| `test_axi_csr_bridge.py` | 7 | AXI4-Lite to CSR bridge |
| `test_csr_event.py` | 6 | CSR event integration |
| `test_gpio.py` | 5 | GPIO peripheral |
| `test_wb_burst.py` | 4 | Wishbone burst support |
| `test_csr_wishbone.py` | 4 | Wishbone to CSR bridge |
| `test_wb_sim_integration.py` | 3 | Wishbone simulation integration |

---

## Project Status

See [`STATUS.md`](STATUS.md) for a detailed breakdown of all implemented files and [`TODO.md`](TODO.md) for the completed roadmap.

### All Features Implemented ✅

- ✅ CSR registers with element-based ownership model (fixes DuplicateElaboratable)
- ✅ Memory maps with BAR-relative addressing
- ✅ Event handling and interrupt aggregation
- ✅ Wishbone B4 bus with burst support and crossbar
- ✅ GPIO peripheral with CSR interface
- ✅ Full AXI4-Lite bus definitions with relaxed data width (128, 256-bit support)
- ✅ AXI4-Lite decoder (pipelined), arbiter, crossbar
- ✅ AXI4-Lite SRAM with byte strobes
- ✅ AXI4-Lite timeout watchdog
- ✅ Full AXI4 bus definitions with ID, burst, and user signals
- ✅ AXI4 Full decoder (burst-aware), arbiter (ID remapping), crossbar (N×M)
- ✅ AXI4 Full SRAM with native burst support
- ✅ AXI4 Full timeout wrapper (burst-level)
- ✅ AXI4 burst-to-beat converter and AXI4→AXI4-Lite adapter
- ✅ Wishbone ↔ AXI4-Lite bidirectional bridges
- ✅ AXI4-Lite → CSR and Wishbone → CSR bridges
- ✅ Automatic bridge selection registry (`BusAdapter`) with two-hop chains
- ✅ DMA infrastructure: reader, writer, scatter-gather
- ✅ Timer peripheral and enhanced interrupt controller with CSR interfaces
- ✅ MSI/MSI-X interrupt controller
- ✅ CPU wrappers (abstract, AXI, Wishbone, VexRiscv)
- ✅ Bus-agnostic SoC builder with AXI4-Lite, AXI4 Full, and Wishbone support
- ✅ Automatic bus bridge insertion, PCIe BAR mapping, DMA channel configuration
- ✅ Export: C headers, CMSIS-SVD, linker scripts, device tree
- ✅ Simulation helpers for AXI4-Lite, AXI4 Full, and Wishbone
- ✅ Bus protocol checkers for Wishbone, AXI4-Lite, and AXI4 Full
- ✅ Endianness support with automatic byte-swap in bridges
- ✅ All 13 previously-empty stub files now have implementations
- ✅ SoC platform integration

---

## License

BSD-2-Clause. See [`LICENSE.txt`](LICENSE.txt).
