# amaranth-soc — Project Status

> **Last updated:** 2026-03-19  
> **Version:** 0.1.0  
> **Tests:** 219 passed (+ 10 subtests), 0 failed

---

## Overview

`amaranth-soc` is the unified SoC toolkit for Amaranth HDL. It combines the original
upstream amaranth-soc foundations (CSR registers, memory maps, event handling, Wishbone
bus, GPIO peripheral) with a full AXI4/AXI4-Lite bus infrastructure, cross-bus bridges,
CSR integration, peripherals, and a bus-agnostic SoC builder.

---

## ✅ Core Components (from upstream amaranth-soc)

These components are stable and come from the original amaranth-soc project.

| Component | File(s) | Description |
|-----------|---------|-------------|
| **CSR registers** | `amaranth_soc/csr/` | `csr.Register`, `csr.Field`, `csr.Multiplexer`, `csr.Decoder` — control/status register infrastructure with field-level access control |
| **Memory maps** | `amaranth_soc/memory.py` | `MemoryMap` — hierarchical address space management with windows and resources |
| **Event handling** | `amaranth_soc/event.py` | `event.Source`, `event.EventMap`, `event.Monitor` — interrupt event aggregation |
| **Wishbone bus** | `amaranth_soc/wishbone/` | `wishbone.Signature`, `wishbone.Interface`, `wishbone.Decoder`, `wishbone.Arbiter` — Wishbone B4 pipelined bus |
| **GPIO peripheral** | `amaranth_soc/gpio.py` | `gpio.Peripheral` — general-purpose I/O with CSR interface |

---

## ✅ Implemented Files (with content)

### Package Root

| File | Bytes | Description |
|------|------:|-------------|
| `amaranth_soc/__init__.py` | 1,641 | Package root: `BusStandard` enum, `detect_bus_standard()` helper |

### AXI Bus Infrastructure (`axi/`)

| File | Bytes | Description |
|------|------:|-------------|
| `axi/__init__.py` | 375 | Re-exports all AXI components |
| `axi/bus.py` | 14,811 | `AXIResp`, `AXIBurst`, `AXISize` enums; `AXI4LiteSignature`, `AXI4LiteInterface`, `AXI4Signature`, `AXI4Interface` — full bus definitions with MemoryMap support |
| `axi/decoder.py` | 10,937 | `AXI4LiteDecoder` — address-based subordinate routing (1-to-N) |
| `axi/arbiter.py` | 6,798 | `AXI4LiteArbiter` — round-robin multi-master arbitration (N-to-1) |
| `axi/sram.py` | 4,820 | `AXI4LiteSRAM` — AXI4-Lite SRAM controller with byte strobes |
| `axi/burst.py` | 5,134 | `AXIBurst2Beat` — AXI burst-to-beat address generator per IHI0022L §A3.4.1 |
| `axi/adapter.py` | 9,593 | `AXI4ToAXI4Lite` — AXI4 (full) to AXI4-Lite adapter with burst decomposition |
| `axi/crossbar.py` | 10,159 | `AXI4LiteCrossbar` — NxM crossbar interconnect (N decoders × M arbiters) |
| `axi/timeout.py` | 7,921 | `AXI4Timeout` — bus timeout watchdog with error response generation |

### Bus Bridges (`bridge/`)

| File | Bytes | Description |
|------|------:|-------------|
| `bridge/__init__.py` | 158 | Re-exports bridge components |
| `bridge/axi_to_wb.py` | 6,793 | `AXI4LiteToWishbone` — AXI4-Lite to Wishbone Classic bridge |
| `bridge/wb_to_axi.py` | 6,707 | `WishboneToAXI4Lite` — Wishbone Classic to AXI4-Lite bridge |
| `bridge/wb_to_csr.py` | 152 | `WishboneCSRBridge` — re-export from `amaranth-soc` |
| `bridge/registry.py` | 5,589 | `BusAdapter` — automatic bridge selection registry with direct + two-hop chains |

### CSR Infrastructure (`csr/`)

| File | Bytes | Description |
|------|------:|-------------|
| `csr/__init__.py` | 120 | Re-exports CSR types + `AXI4LiteCSRBridge` |
| `csr/axi_lite.py` | 7,577 | `AXI4LiteCSRBridge` — AXI4-Lite to CSR bus bridge |

### Peripherals (`periph/`)

| File | Bytes | Description |
|------|------:|-------------|
| `periph/__init__.py` | 182 | Re-exports `TimerPeripheral`, `InterruptController` |
| `periph/timer.py` | 6,036 | `TimerPeripheral` — countdown timer with CSR interface (load, reload, enable, irq) |
| `periph/intc.py` | 4,015 | `InterruptController` — simple priority-based interrupt controller with CSR interface |

### SoC Builder (`soc/`)

| File | Bytes | Description |
|------|------:|-------------|
| `soc/__init__.py` | 358 | Re-exports `SoCBuilder`, `SoC`, handler classes |
| `soc/builder.py` | 9,585 | `SoCBuilder` / `SoC` — refactored bus-agnostic SoC builder using handler architecture |
| `soc/bus_handler.py` | 7,479 | `BusHandler` ABC, `AXI4LiteBusHandler`, `WishboneBusHandler` — bus topology handlers |
| `soc/csr_handler.py` | 3,356 | `CSRHandler` — CSR map and bridge handler |
| `soc/irq_handler.py` | 2,488 | `IRQHandler` — IRQ routing and interrupt controller handler |

### Simulation Helpers (`sim/`)

| File | Bytes | Description |
|------|------:|-------------|
| `sim/__init__.py` | 126 | Re-exports `axi_lite_write`, `axi_lite_read`, `wb_write`, `wb_read`, `wb_write_pipelined`, `wb_read_pipelined` |
| `sim/axi.py` | 3,624 | `axi_lite_write()`, `axi_lite_read()` — async AXI4-Lite simulation transaction helpers |
| `sim/wishbone.py` | 7,679 | `wb_write()`, `wb_read()`, `wb_write_pipelined()`, `wb_read_pipelined()` — async Wishbone simulation transaction helpers |

### Export Utilities (`export/`)

| File | Bytes | Description |
|------|------:|-------------|
| `export/__init__.py` | 116 | Re-exports `CHeaderGenerator` |
| `export/c_header.py` | 2,809 | `CHeaderGenerator` — generates C `#define` macros for memory regions and IRQ assignments |

### Reexport Wrappers

| File | Bytes | Description |
|------|------:|-------------|
| `wishbone/__init__.py` | 19 | Re-exports Wishbone bus types (`Signature`, `Interface`, `Decoder`, `Arbiter`, `WishboneSRAM`) |
| `event/__init__.py` | 196 | Re-exports event types (`Source`, `EventMap`, `Monitor`) |

---

## ❌ Empty / Placeholder Files (0 bytes)

### CPU Wrappers (`cpu/`) — **Intentionally placeholder**

These require actual Verilog CPU cores (e.g., VexRiscv `.v` files) to wrap.
They cannot be implemented without the RTL cores themselves.

| File | Bytes | Status |
|------|------:|--------|
| `cpu/__init__.py` | 0 | Empty — no CPU wrappers to export yet |
| `cpu/wrapper.py` | 0 | Empty — abstract CPU wrapper base class |
| `cpu/vexriscv.py` | 0 | Empty — VexRiscv CPU wrapper (needs Verilog core) |
| `cpu/axi_wrapper.py` | 0 | Empty — AXI bus CPU wrapper |
| `cpu/wb_wrapper.py` | 0 | Empty — Wishbone bus CPU wrapper |

### Peripherals (`periph/`) — **Intentionally NOT implemented (separate project phase)**

UART, I2C, SPI, and GPIO peripherals are planned for a different part of the project.
They are not in scope for the bus infrastructure phase.

| File | Bytes | Status |
|------|------:|--------|
| `periph/base.py` | 0 | Empty — abstract peripheral base class |
| `periph/gpio.py` | 0 | Empty — GPIO peripheral (separate phase) |
| `periph/uart.py` | 0 | Empty — UART peripheral (separate phase) |

### Export Modules (`export/`) — **Placeholder (only C header is done)**

| File | Bytes | Status |
|------|------:|--------|
| `export/svd.py` | 0 | Empty — CMSIS-SVD XML generator |
| `export/linker.py` | 0 | Empty — linker script generator |
| `export/devicetree.py` | 0 | Empty — Linux device tree generator |

### Bus Bridges (`bridge/`)

| File | Bytes | Status |
|------|------:|--------|
| `bridge/axi_to_csr.py` | 0 | Empty — direct AXI4-Lite to CSR bridge (the path via Wishbone works: AXI→WB→CSR) |

### SoC Builder (`soc/`)

| File | Bytes | Status |
|------|------:|--------|
| `soc/platform.py` | 0 | Empty — platform integration |

---

## 🧪 Test Coverage

**Total: 219 tests passed, 0 failed** (+ 10 subtests)

| Test File | Tests | What It Covers |
|-----------|------:|----------------|
| `tests/test_bridges.py` | 45 | WB↔AXI4-Lite bridges, AXI4→AXI4-Lite adapter |
| `tests/test_axi_bus.py` | 41 | AXI enums, AXI4-Lite/AXI4 signatures & interfaces, MemoryMap |
| `tests/test_axi_crossbar.py` | 24 | NxM crossbar construction, configuration, elaboration |
| `tests/test_axi_timeout.py` | 23 | Timeout watchdog construction, properties, elaboration |
| `tests/test_axi_burst.py` | 21 | Burst-to-beat address generator |
| `tests/test_bus_adapter.py` | 18 | Bus adapter registry, same-standard passthrough, direct + two-hop chains |
| `tests/test_axi_sram.py` | 15 | SRAM construction + **simulation tests** (write/read, byte strobes, init data) |
| `tests/test_axi_arbiter.py` | 11 | Arbiter construction, master management, elaboration |
| `tests/test_axi_decoder.py` | 10 | Decoder construction, subordinate management, elaboration |
| `tests/test_axi_csr_bridge.py` | 7 | AXI4-Lite to CSR bridge |
| `tests/test_sim_helpers.py` | 4 | Simulation helper imports and function signatures |
| `tests/test_wb_sim_integration.py` | — | Wishbone simulation helper integration tests |
| `tests/test_soc_handlers.py` | — | SoC builder handler unit tests (BusHandler, CSRHandler, IRQHandler) |

### Running Tests

```bash
cd amaranth-soc && pdm run pytest tests/ -v
```

With coverage:
```bash
cd amaranth-soc && pdm run pytest tests/ -v --cov=amaranth_soc --cov-report=term-missing
```

---

## 📊 Summary

| Category | Implemented | Empty/Placeholder | Total |
|----------|:-----------:|:-----------------:|:-----:|
| Core (CSR, memory, event, WB, GPIO) | stable | 0 | — |
| AXI bus (`axi/`) | 9 | 0 | 9 |
| Bridges (`bridge/`) | 5 | 1 | 6 |
| CSR (`csr/`) | 2 | 0 | 2 |
| Peripherals (`periph/`) | 3 | 3 | 6 |
| SoC builder (`soc/`) | 5 | 1 | 6 |
| CPU wrappers (`cpu/`) | 0 | 5 | 5 |
| Export (`export/`) | 2 | 3 | 5 |
| Simulation (`sim/`) | 3 | 0 | 3 |
| Reexport wrappers | 2 | 0 | 2 |
| Package root | 1 | 0 | 1 |
| **Total** | **32** | **13** | **45** |

---

## 🗺️ What's Done vs What's Not

### ✅ Done — Core SoC Infrastructure (from upstream amaranth-soc)
- CSR registers with field-level access control (`csr.Register`, `csr.Field`, `csr.Multiplexer`, `csr.Decoder`)
- Hierarchical memory maps (`MemoryMap`)
- Event handling and interrupt aggregation (`event.Source`, `event.EventMap`, `event.Monitor`)
- Wishbone B4 pipelined bus (`wishbone.Signature`, `wishbone.Interface`, `wishbone.Decoder`, `wishbone.Arbiter`)
- GPIO peripheral with CSR interface (`gpio.Peripheral`)

### ✅ Done — AXI4/AXI4-Lite Bus Infrastructure (core focus)
- Full AXI4-Lite and AXI4 bus definitions with Amaranth `wiring.Signature`
- Address decoder (1-to-N routing)
- Round-robin arbiter (N-to-1)
- NxM crossbar interconnect
- SRAM controller with byte strobes
- Burst-to-beat converter (AXI4 → AXI4-Lite)
- AXI4 → AXI4-Lite protocol adapter
- Bus timeout watchdog
- AXI4-Lite simulation helpers (`axi_lite_write`, `axi_lite_read`)
- Wishbone simulation helpers (`wb_write`, `wb_read`, `wb_write_pipelined`, `wb_read_pipelined`)

### ✅ Done — Bus Bridges
- Wishbone ↔ AXI4-Lite (bidirectional)
- Wishbone → CSR (re-export from amaranth-soc)
- AXI4-Lite → CSR bridge
- Automatic bridge selection registry (`BusAdapter`)

### ✅ Done — Peripherals (bus infrastructure peripherals only)
- Timer peripheral with CSR interface
- Interrupt controller with CSR interface

### ✅ Done — SoC Builder
- `SoCBuilder` / `SoC` — bus-agnostic builder with CPU, memory, peripheral, IRQ management
- Handler architecture: `BusHandler` ABC with `AXI4LiteBusHandler` and `WishboneBusHandler`, `CSRHandler`, `IRQHandler`
- Builder refactored to delegate bus topology, CSR mapping, and IRQ routing to handler classes

### ✅ Done — Export
- C header generator (`#define` macros for memory map + IRQs)

### ⏳ Intentionally NOT Done — CPU Wrappers
- `cpu/vexriscv.py` — needs actual VexRiscv Verilog core
- `cpu/wrapper.py`, `cpu/axi_wrapper.py`, `cpu/wb_wrapper.py` — need RTL cores to wrap
- **These are blocked on obtaining/generating the Verilog CPU cores**

### ⏳ Intentionally NOT Done — Communication Peripherals (separate project phase)
- `periph/uart.py` — UART peripheral
- `periph/gpio.py` — GPIO peripheral
- I2C, SPI — not even stubbed yet
- **These belong to a different development phase focused on peripheral IP**

### ⏳ Intentionally NOT Done — Export Formats
- `export/svd.py` — CMSIS-SVD XML (for IDE debug tools)
- `export/linker.py` — linker script generation
- `export/devicetree.py` — Linux device tree
- **Only C header export is needed for initial bring-up**

### ⏳ Not Yet Implemented — SoC Platform Integration
- `soc/platform.py` — platform-specific integration (FPGA target configuration)
