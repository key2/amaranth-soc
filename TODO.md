# amaranth-soc Improvement Roadmap

*Based on analysis of amaranth-pcie, amaranth-stream, and real-world PCIe/DMA usage on Gowin GW5AST and Xilinx Series 7 FPGAs.*

> **🎉 All 18 TODO items have been implemented.** Last updated: 2026-03-27.

---

## Priority Legend

- 🔴 **P0 — Critical Bug/Blocker**: Prevents real-world usage
- 🟠 **P1 — Major Gap**: Forces users to bypass amaranth-soc entirely
- 🟡 **P2 — Important Enhancement**: Needed for AXI4 Full and advanced SoC features
- 🟢 **P3 — Nice to Have**: Quality-of-life and completeness

---

## 🔴 P0 — Critical Bugs / Blockers

### ✅ 1. CSR Register Ownership Model — DuplicateElaboratable — DONE

**Files:** [`csr/bus.py:505`](amaranth_soc/csr/bus.py:505) (Multiplexer), [`csr/reg.py:761`](amaranth_soc/csr/reg.py:761) (Bridge)

**Bug:** The CSR `Multiplexer` and `Bridge` require registers to be elaborated as their submodules. When a register is already owned by another component (e.g., a DMA engine's control registers), Amaranth raises `DuplicateElaboratable`. This prevents the most common use case: exposing peripheral registers to a host via CSR.

**Impact:** The amaranth-pcie tang_mega_138K_pro example was forced to create a custom [`WishboneCSRBank`](../amaranth-pcie/examples/tang_mega_138K_pro/gw_pcie_test/top.py:71) (75 lines) that bypasses the entire CSR infrastructure, manually mapping Wishbone addresses to `Register.element` interfaces.

**Root cause:** [`Bridge.__init__()`](amaranth_soc/csr/reg.py:761) calls `m.submodules[name] = reg` for each register. The `Multiplexer` directly accesses `reg.element.r_data`, `reg.element.w_data`, etc. at [`bus.py:562`](amaranth_soc/csr/bus.py:562).

**Fix implemented:** Element-based Multiplexer that accepts pre-created `Element` interfaces instead of `Register` objects. The Multiplexer drives `element.r_stb`/`element.w_stb`/`element.w_data` and reads `element.r_data` without needing to elaborate the register. See [`csr/reg.py`](amaranth_soc/csr/reg.py).

**Tests:** [`test_csr_reg.py`](tests/test_csr_reg.py), [`test_csr_comprehensive.py`](tests/test_csr_comprehensive.py)

---

## 🟠 P1 — Major Gaps

### ✅ 2. AXI4 Full Interconnect — Decoder — DONE

**File:** [`axi/decoder.py`](amaranth_soc/axi/decoder.py)

**Implemented:** `AXI4Decoder` that routes AW/W/B channels based on address decoding with burst support, tracks outstanding bursts per target to handle WLAST correctly, generates DECERR for unmapped addresses, and supports MemoryMap integration.

**Tests:** [`test_axi_decoder.py`](tests/test_axi_decoder.py)

---

### ✅ 3. AXI4 Full Interconnect — Arbiter — DONE

**File:** [`axi/arbiter.py`](amaranth_soc/axi/arbiter.py)

**Implemented:** `AXI4Arbiter` that arbitrates between multiple AXI4 Full masters (round-robin), handles ID remapping, locks during bursts (AW→W→B, AR→R sequences), and supports MemoryMap integration.

**Tests:** [`test_axi_arbiter.py`](tests/test_axi_arbiter.py)

---

### ✅ 4. AXI4 Full Interconnect — Crossbar — DONE

**File:** [`axi/crossbar.py`](amaranth_soc/axi/crossbar.py)

**Implemented:** `AXI4Crossbar` composing AXI4 decoders and arbiters for N×M routing with ID management, burst tracking, and ordering rules.

**Tests:** [`test_axi_crossbar.py`](tests/test_axi_crossbar.py)

---

### ✅ 5. AXI4-Lite Data Width Restriction — DONE

**File:** [`axi/bus.py`](amaranth_soc/axi/bus.py)

**Implemented:** Relaxed `AXI4LiteSignature` data width restriction to allow wider data widths (128-bit, 256-bit) for high-bandwidth SoCs, with a `strict=True` parameter for spec compliance.

**Tests:** [`test_axi_bus.py`](tests/test_axi_bus.py)

---

### ✅ 6. DMA Infrastructure — DONE

**Files:** [`dma/`](amaranth_soc/dma/)

**Implemented:**
- [`dma/common.py`](amaranth_soc/dma/common.py) — Common signatures and types
- [`dma/reader.py`](amaranth_soc/dma/reader.py) — DMA read engine with configurable FIFO depths
- [`dma/writer.py`](amaranth_soc/dma/writer.py) — DMA write engine
- [`dma/scatter_gather.py`](amaranth_soc/dma/scatter_gather.py) — Scatter-gather descriptor tables with loop/program modes

**Tests:** [`test_dma.py`](tests/test_dma.py)

---

### ✅ 7. Endianness Support in Bus Primitives — DONE

**File:** [`bus_common.py`](amaranth_soc/bus_common.py)

**Implemented:** Endianness parameter on bus signatures, automatic byte-swap logic in bus bridges when crossing endianness boundaries, and documentation of byte ordering conventions.

**Tests:** [`test_endianness.py`](tests/test_endianness.py)

---

### ✅ 8. Event System Enhancements for MSI — DONE

**Files:** [`periph/intc.py`](amaranth_soc/periph/intc.py), [`periph/msi.py`](amaranth_soc/periph/msi.py)

**Implemented:**
- Enhanced `InterruptController` with edge/level detection, enable mask, priority encoding, stream output
- `MSIController` for MSI support with per-vector address/data/mask tables
- Integration with the existing `event.Monitor` as a building block

**Tests:** [`test_intc.py`](tests/test_intc.py)

---

## 🟡 P2 — Important Enhancements

### ✅ 9. AXI4 Full SRAM — DONE

**File:** [`axi/sram.py`](amaranth_soc/axi/sram.py)

**Implemented:** `AXI4SRAM` that handles burst reads/writes natively (INCR, WRAP, FIXED) using `Burst2Beat` for address generation, without going through the AXI4→AXI4-Lite adapter.

**Tests:** [`test_axi_sram.py`](tests/test_axi_sram.py)

---

### ✅ 10. Wishbone Crossbar — DONE

**File:** [`wishbone/bus.py`](amaranth_soc/wishbone/bus.py)

**Implemented:** `WishboneCrossbar` that composes decoders and arbiters automatically, similar to `AXI4LiteCrossbar`.

**Tests:** [`test_wb_crossbar.py`](tests/test_wb_crossbar.py)

---

### ✅ 11. Memory Map — BAR-Relative Addressing — DONE

**File:** [`memory.py`](amaranth_soc/memory.py)

**Implemented:** `MemoryMap` mode for relative/offset addressing, integration between `MemoryMap` and PCIe BAR configuration, support for generating C headers / device tree entries from the PCIe register map.

**Tests:** [`test_bar_memory.py`](tests/test_bar_memory.py)

---

### ✅ 12. Wishbone Burst Support in Interconnect — DONE

**File:** [`wishbone/bus.py`](amaranth_soc/wishbone/bus.py)

**Implemented:** Burst-aware routing in Decoder (holds address decode for duration of burst when CTI != 0b111) and Arbiter (does not re-arbitrate during a burst).

**Tests:** [`test_wb_burst.py`](tests/test_wb_burst.py)

---

### ✅ 13. AXI4-Lite Decoder Pipelining — DONE

**File:** [`axi/decoder.py`](amaranth_soc/axi/decoder.py)

**Implemented:** Pipelined operation in the decoder that accepts new AW/AR while previous B/R is in flight, for high-throughput use cases.

**Tests:** [`test_axi_decoder.py`](tests/test_axi_decoder.py)

---

### ✅ 14. Stub Files Cleanup — DONE

All 13 previously empty files now have implementations:

| File | Status |
|------|--------|
| [`bridge/axi_to_csr.py`](amaranth_soc/bridge/axi_to_csr.py) | ✅ Implemented — AXI4-Lite to CSR bridge redirect |
| [`bridge/wb_to_csr.py`](amaranth_soc/bridge/wb_to_csr.py) | ✅ Implemented — Wishbone to CSR bridge redirect |
| [`cpu/axi_wrapper.py`](amaranth_soc/cpu/axi_wrapper.py) | ✅ Implemented — AXI CPU wrapper |
| [`cpu/vexriscv.py`](amaranth_soc/cpu/vexriscv.py) | ✅ Implemented — VexRiscv integration |
| [`cpu/wb_wrapper.py`](amaranth_soc/cpu/wb_wrapper.py) | ✅ Implemented — Wishbone CPU wrapper |
| [`cpu/wrapper.py`](amaranth_soc/cpu/wrapper.py) | ✅ Implemented — Generic CPU wrapper |
| [`export/devicetree.py`](amaranth_soc/export/devicetree.py) | ✅ Implemented — Device tree generation |
| [`export/linker.py`](amaranth_soc/export/linker.py) | ✅ Implemented — Linker script generation |
| [`export/svd.py`](amaranth_soc/export/svd.py) | ✅ Implemented — SVD file generation |
| [`periph/base.py`](amaranth_soc/periph/base.py) | ✅ Implemented — Base peripheral class |
| [`periph/gpio.py`](amaranth_soc/periph/gpio.py) | ✅ Implemented — GPIO peripheral |
| [`periph/uart.py`](amaranth_soc/periph/uart.py) | ✅ Implemented — UART peripheral |
| [`soc/platform.py`](amaranth_soc/soc/platform.py) | ✅ Implemented — SoC platform integration |

**Tests:** [`test_stubs.py`](tests/test_stubs.py)

---

## 🟢 P3 — Nice to Have

### ✅ 15. AXI4 Full Timeout Wrapper — DONE

**File:** [`axi/timeout.py`](amaranth_soc/axi/timeout.py)

**Implemented:** `AXI4Timeout` (full) that handles burst-level timeouts (timeout on burst completion, not individual beats), alongside the existing `AXI4LiteTimeout`.

**Tests:** [`test_axi_timeout.py`](tests/test_axi_timeout.py)

---

### ✅ 16. Simulation Helpers for AXI4 Full — DONE

**File:** [`sim/axi.py`](amaranth_soc/sim/axi.py)

**Implemented:** AXI4 Full simulation helpers with burst generation, ID tracking, and response checking.

**Tests:** [`test_sim_helpers.py`](tests/test_sim_helpers.py)

---

### ✅ 17. Bus Protocol Checker — DONE

**File:** [`sim/protocol_checker.py`](amaranth_soc/sim/protocol_checker.py)

**Implemented:** Assertion-based checkers for simulation:
- Wishbone: `cyc` must be asserted with `stb`, `ack` must not assert without `stb`
- AXI4: `WLAST` must match `AWLEN`, response ordering must match request ordering
- AXI4-Lite: No burst signals, single-beat only

**Tests:** [`test_protocol_checker.py`](tests/test_protocol_checker.py)

---

### ✅ 18. SoC Builder Integration — DONE

**File:** [`soc/builder.py`](amaranth_soc/soc/builder.py)

**Implemented:**
- Automatic bus bridge insertion when mixing Wishbone and AXI4 peripherals
- PCIe BAR mapping as a first-class concept
- DMA channel configuration
- Interrupt routing (MSI/MSI-X generation from event sources)
- AXI4 Full bus handler support

**Tests:** [`test_soc_builder_enhanced.py`](tests/test_soc_builder_enhanced.py), [`test_soc_handlers.py`](tests/test_soc_handlers.py), [`test_axi4_bus_handler.py`](tests/test_axi4_bus_handler.py)

---

## Implementation Phases — ALL COMPLETE ✅

```
Phase 1 — Unblock Real-World Usage (P0 + critical P1):     ✅ COMPLETE
  [✅]  Fix CSR register ownership (DuplicateElaboratable)
  [✅]  Add endianness support to bus primitives
  [✅]  Relax AXI4-Lite data width restriction
  [✅]  Clean up empty stub files

Phase 2 — AXI4 Full Foundation (P1):                        ✅ COMPLETE
  [✅]  AXI4 Full Decoder
  [✅]  AXI4 Full Arbiter
  [✅]  AXI4 Full SRAM
  [✅]  Wishbone burst support in interconnect

Phase 3 — Advanced SoC Features (P1 + P2):                  ✅ COMPLETE
  [✅]  DMA infrastructure
  [✅]  Enhanced interrupt controller (MSI support)
  [✅]  AXI4 Full Crossbar
  [✅]  Wishbone Crossbar
  [✅]  Memory Map BAR-relative addressing

Phase 4 — Polish and Completeness (P2 + P3):                ✅ COMPLETE
  [✅]  AXI4-Lite Decoder pipelining
  [✅]  AXI4 Full Timeout
  [✅]  AXI4 Full simulation helpers
  [✅]  Bus protocol checkers
  [✅]  SoC Builder enhancements
```

---

## Dependency Graph — ALL RESOLVED ✅

```
[✅] CSR Ownership Fix ──────────────────────────────────────→ Unblocks all CSR usage
[✅] Endianness Support ─────────────────────────────────────→ Unblocks correct PCIe bridges
[✅] AXI4-Lite Width ────────────────────────────────────────→ Unblocks wide AXI4-Lite usage

[✅] AXI4 Decoder ──┐
[✅] AXI4 Arbiter ──┼──→ [✅] AXI4 Crossbar ──→ Full AXI4 interconnect
[✅] AXI4 SRAM ─────┘

[✅] Interrupt Controller ──→ [✅] SoC Builder ──→ Complete SoC generation
[✅] DMA Infrastructure ───→ [✅] SoC Builder
[✅] BAR-Relative MemMap ──→ [✅] SoC Builder
```

---

*This roadmap was derived from the analysis in [`ANALYSIS.md`](../amaranth-pcie/ANALYSIS.md) and [`WISHBONE_VS_AXI4.md`](../amaranth-pcie/WISHBONE_VS_AXI4.md). All items have been implemented as of 2026-03-27.*
