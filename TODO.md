# amaranth-soc Improvement Roadmap

*Based on analysis of amaranth-pcie, amaranth-stream, and real-world PCIe/DMA usage on Gowin GW5AST and Xilinx Series 7 FPGAs.*

---

## Priority Legend

- 🔴 **P0 — Critical Bug/Blocker**: Prevents real-world usage
- 🟠 **P1 — Major Gap**: Forces users to bypass amaranth-soc entirely
- 🟡 **P2 — Important Enhancement**: Needed for AXI4 Full and advanced SoC features
- 🟢 **P3 — Nice to Have**: Quality-of-life and completeness

---

## 🔴 P0 — Critical Bugs / Blockers

### 1. CSR Register Ownership Model — DuplicateElaboratable

**Files:** [`csr/bus.py:505`](amaranth_soc/csr/bus.py:505) (Multiplexer), [`csr/reg.py:761`](amaranth_soc/csr/reg.py:761) (Bridge)

**Bug:** The CSR `Multiplexer` and `Bridge` require registers to be elaborated as their submodules. When a register is already owned by another component (e.g., a DMA engine's control registers), Amaranth raises `DuplicateElaboratable`. This prevents the most common use case: exposing peripheral registers to a host via CSR.

**Impact:** The amaranth-pcie tang_mega_138K_pro example was forced to create a custom [`WishboneCSRBank`](../amaranth-pcie/examples/tang_mega_138K_pro/gw_pcie_test/top.py:71) (75 lines) that bypasses the entire CSR infrastructure, manually mapping Wishbone addresses to `Register.element` interfaces.

**Root cause:** [`Bridge.__init__()`](amaranth_soc/csr/reg.py:761) calls `m.submodules[name] = reg` for each register. The `Multiplexer` directly accesses `reg.element.r_data`, `reg.element.w_data`, etc. at [`bus.py:562`](amaranth_soc/csr/bus.py:562).

**Fix options:**
1. **Element-based Multiplexer**: Accept pre-created `Element` interfaces instead of `Register` objects. The Multiplexer would drive `element.r_stb`/`element.w_stb`/`element.w_data` and read `element.r_data` without needing to elaborate the register.
2. **Proxy pattern**: Create a `RegisterProxy` that wraps an `Element` interface without owning the register. The Bridge would use proxies instead of direct register references.
3. **Deferred elaboration**: Allow registers to declare their elaboration context separately from their CSR mapping.

**Test needed:** `test_multiplexer_external_register` — register owned by a DMA module, exposed via CSR Multiplexer without DuplicateElaboratable.

**Workaround in amaranth-pcie:** Custom [`WishboneCSRBank`](../amaranth-pcie/examples/tang_mega_138K_pro/gw_pcie_test/top.py:71) at [`top.py:71-174`](../amaranth-pcie/examples/tang_mega_138K_pro/gw_pcie_test/top.py:71).

---

## 🟠 P1 — Major Gaps

### 2. AXI4 Full Interconnect — Decoder

**Current state:** [`AXI4Signature`](amaranth_soc/axi/bus.py:197) exists but has **no decoder**. The only path from AXI4 Full to targets is through [`AXI4ToAXI4Lite`](amaranth_soc/axi/adapter.py:15) which serializes bursts.

**What's needed:** An `AXI4Decoder` that:
- Routes AW/W/B channels based on address decoding (like [`AXI4LiteDecoder`](amaranth_soc/axi/decoder.py:13) but with burst support)
- Tracks outstanding bursts per target to handle WLAST correctly
- Generates DECERR for unmapped addresses
- Supports MemoryMap integration

**Complexity:** High — must handle burst tracking, write interleaving (or prohibit it), and ID passthrough.

**Reference:** The existing [`AXI4LiteDecoder`](amaranth_soc/axi/decoder.py:87) can serve as a starting point. The [`Burst2Beat`](amaranth_soc/axi/burst.py:13) component already handles address generation for FIXED/INCR/WRAP.

**Test needed:** `test_axi4_decoder_incr_burst` — INCR burst routed to correct target, WLAST tracked.

---

### 3. AXI4 Full Interconnect — Arbiter

**Current state:** No AXI4 Full arbiter exists.

**What's needed:** An `AXI4Arbiter` that:
- Arbitrates between multiple AXI4 Full masters (round-robin or priority)
- Handles ID remapping (prepend master index to ID to avoid conflicts)
- Locks during bursts (AW→W→B, AR→R sequences)
- Supports MemoryMap integration

**Reference:** [`AXI4LiteArbiter`](amaranth_soc/axi/arbiter.py:13) for the basic pattern.

**Test needed:** `test_axi4_arbiter_two_masters_concurrent_bursts`.

---

### 4. AXI4 Full Interconnect — Crossbar

**Current state:** No AXI4 Full crossbar exists.

**What's needed:** An `AXI4Crossbar` composing AXI4 decoders and arbiters (like [`AXI4LiteCrossbar`](amaranth_soc/axi/crossbar.py:21) but for AXI4 Full).

**Complexity:** Very high — N×M routing with ID management, burst tracking, and ordering rules.

**Recommendation:** Implement as Phase 3 (long-term). For now, point-to-point AXI4 Full connections + AXI4→AXI4-Lite adapter cover most use cases.

---

### 5. AXI4-Lite Data Width Restriction

**File:** [`axi/bus.py:72`](amaranth_soc/axi/bus.py:72)

**Bug:** `AXI4LiteSignature` restricts `data_width` to 32 or 64 only. While this matches the AXI4-Lite spec, it prevents using AXI4-Lite for wider internal buses (128-bit, 256-bit) that are common in high-bandwidth SoCs.

**Fix:** Add an `AXI4LiteWideSignature` variant that allows wider data widths, or relax the restriction with a `strict=True` parameter.

**Impact:** PCIe DMA uses 256-bit data paths. The [`PCIeAXISlave`](../amaranth-pcie/amaranth_pcie/frontend/axi.py:57) defines AXI4 signals manually partly because AXI4-Lite can't handle 256-bit.

---

### 6. No DMA Infrastructure

**Current state:** amaranth-soc has zero DMA support. amaranth-pcie imports DMA from an external `amaranth_lib.dma` library.

**What's needed:**
- **DMA Reader/Writer engines** with configurable FIFO depths
- **Scatter-gather descriptor tables** with loop/program modes
- **Descriptor splitters** for breaking large transfers into max-payload-sized chunks
- **DMA synchronizers and buffering** for clock domain crossing
- **IRQ generation** on transfer completion

**Reference:** amaranth-pcie's [`PCIeDMA`](../amaranth-pcie/amaranth_pcie/frontend/dma.py:413) and the external `amaranth_lib.dma` module.

**Proposed location:** `amaranth_soc/dma/` with:
- `amaranth_soc/dma/reader.py` — DMA read engine
- `amaranth_soc/dma/writer.py` — DMA write engine
- `amaranth_soc/dma/scatter_gather.py` — Descriptor management
- `amaranth_soc/dma/common.py` — Common signatures and types

---

### 7. Endianness Support in Bus Primitives

**Current state:** Neither Wishbone nor AXI4 in amaranth-soc has any endianness concept.

**Impact:** Every PCIe frontend implements its own byte-swap logic:
- [`PCIeWishboneMaster._byte_swap_32()`](../amaranth-pcie/amaranth_pcie/frontend/wishbone.py:110)
- [`dword_endianness_swap()`](../amaranth-pcie/amaranth_pcie/tlp/common.py:379)

**What's needed:**
- An `endianness` parameter on `WishboneSignature` and `AXI4Signature`
- Automatic byte-swap logic in bus bridges when crossing endianness boundaries
- Documentation of byte ordering conventions

**Proposed API:**
```python
wb_sig = WishboneSignature(addr_width=16, data_width=32, endianness="little")
axi_sig = AXI4LiteSignature(addr_width=16, data_width=32, endianness="big")
# Bridge automatically inserts byte swap
bridge = AXI4LiteToWishbone(axi_sig, wb_sig)  # auto byte-swap
```

---

### 8. Event System Enhancements for MSI

**File:** [`event.py:180`](amaranth_soc/event.py:180)

**Gap:** The `event.Monitor` outputs a single aggregated `Source.i` bit. PCIe MSI needs:
- **Stream output** with valid/ready handshaking to pace MSI delivery
- **Priority encoding** to select which IRQ number to report
- **Clear strobe** (not persistent mask) for CSR-driven clear operations
- **Multi-vector support** with per-vector address/data/mask tables (MSI-X)

**Impact:** amaranth-pcie implements three custom MSI controllers:
- [`PCIeMSI`](../amaranth-pcie/amaranth_pcie/core/msi.py:32) — basic edge-triggered
- [`PCIeMSIMultiVector`](../amaranth-pcie/amaranth_pcie/core/msi.py:119) — priority-encoded
- [`PCIeMSIX`](../amaranth-pcie/amaranth_pcie/core/msi.py:184) — table-based

**What's needed in amaranth-soc:**
- `InterruptController` with edge/level detection, enable mask, priority encoding, stream output
- `InterruptTable` for MSI-X-style per-vector configuration
- Integration with the existing `event.Monitor` as a building block

**Proposed location:** Enhance [`periph/intc.py`](amaranth_soc/periph/intc.py) (currently only 4KB).

---

## 🟡 P2 — Important Enhancements

### 9. AXI4 Full SRAM

**Current state:** Only [`AXI4LiteSRAM`](amaranth_soc/axi/sram.py:15) exists.

**What's needed:** An `AXI4SRAM` that handles burst reads/writes natively (INCR, WRAP, FIXED) without going through the AXI4→AXI4-Lite adapter.

**Reference:** Use [`Burst2Beat`](amaranth_soc/axi/burst.py:13) for address generation.

---

### 10. Wishbone Crossbar

**Current state:** Wishbone has Decoder and Arbiter but no Crossbar. Users must compose them manually.

**What's needed:** A `WishboneCrossbar` (like [`AXI4LiteCrossbar`](amaranth_soc/axi/crossbar.py:21)) that composes decoders and arbiters automatically.

---

### 11. Memory Map — BAR-Relative Addressing

**File:** [`memory.py`](amaranth_soc/memory.py:1)

**Gap:** `MemoryMap` assumes addresses are defined at design time. PCIe BAR addresses are assigned by the host BIOS/OS during enumeration — the FPGA only sees offsets within a BAR.

**What's needed:**
- A `MemoryMap` mode for relative/offset addressing
- Integration between `MemoryMap` and PCIe BAR configuration
- Support for generating C headers / device tree entries from the PCIe register map (the [`export/c_header.py`](amaranth_soc/export/c_header.py) exists but requires a `MemoryMap`)

---

### 12. Wishbone Burst Support in Interconnect

**Current state:** Wishbone CTI/BTE signals exist as optional features ([`bus.py:132-134`](amaranth_soc/wishbone/bus.py:132)) but the Decoder and Arbiter just pass them through — no burst-aware routing.

**What's needed:** The Decoder should hold the address decode for the duration of a burst (CTI != 0b111). The Arbiter should not re-arbitrate during a burst.

---

### 13. AXI4-Lite Decoder Pipelining

**File:** [`axi/decoder.py:87`](amaranth_soc/axi/decoder.py:87)

**Issue:** The decoder uses FSMs that serialize transactions. For high-throughput use cases, the decoder should support pipelined operation (accept new AW/AR while previous B/R is in flight).

---

### 14. Stub Files Cleanup

**Issue:** 13 files in amaranth-soc are empty (0 bytes):

| File | Expected Content |
|------|-----------------|
| [`bridge/axi_to_csr.py`](amaranth_soc/bridge/axi_to_csr.py) | AXI4-Lite to CSR bridge (direct, bypassing Wishbone) |
| [`bridge/wb_to_csr.py`](amaranth_soc/bridge/wb_to_csr.py) | Wishbone to CSR bridge (redirect to `csr/wishbone.py`) |
| [`cpu/axi_wrapper.py`](amaranth_soc/cpu/axi_wrapper.py) | AXI CPU wrapper |
| [`cpu/vexriscv.py`](amaranth_soc/cpu/vexriscv.py) | VexRiscv integration |
| [`cpu/wb_wrapper.py`](amaranth_soc/cpu/wb_wrapper.py) | Wishbone CPU wrapper |
| [`cpu/wrapper.py`](amaranth_soc/cpu/wrapper.py) | Generic CPU wrapper |
| [`export/devicetree.py`](amaranth_soc/export/devicetree.py) | Device tree generation |
| [`export/linker.py`](amaranth_soc/export/linker.py) | Linker script generation |
| [`export/svd.py`](amaranth_soc/export/svd.py) | SVD file generation |
| [`periph/base.py`](amaranth_soc/periph/base.py) | Base peripheral class |
| [`periph/gpio.py`](amaranth_soc/periph/gpio.py) | GPIO peripheral (separate from `gpio.py` at root) |
| [`periph/uart.py`](amaranth_soc/periph/uart.py) | UART peripheral |
| [`soc/platform.py`](amaranth_soc/soc/platform.py) | SoC platform integration |

**Fix:** Either implement these or remove them and track as future work. Empty files create false expectations.

---

## 🟢 P3 — Nice to Have

### 15. AXI4 Full Timeout Wrapper

**Current state:** [`AXI4LiteTimeout`](amaranth_soc/axi/timeout.py:17) exists for AXI4-Lite only.

**What's needed:** An `AXI4Timeout` that handles burst-level timeouts (timeout on burst completion, not individual beats).

---

### 16. Simulation Helpers for AXI4 Full

**Current state:** [`sim/axi.py`](amaranth_soc/sim/axi.py:1) has basic AXI4-Lite simulation helpers.

**What's needed:** AXI4 Full simulation helpers with burst generation, ID tracking, and response checking.

---

### 17. Bus Protocol Checker

**Gap:** No runtime protocol checking for Wishbone or AXI4 bus violations.

**What's needed:** Assertion-based checkers that can be enabled during simulation:
- Wishbone: `cyc` must be asserted with `stb`, `ack` must not assert without `stb`
- AXI4: `WLAST` must match `AWLEN`, response ordering must match request ordering
- AXI4-Lite: No burst signals, single-beat only

---

### 18. SoC Builder Integration

**File:** [`soc/builder.py`](amaranth_soc/soc/builder.py:1)

**Enhancement:** The SoC builder should support:
- Automatic bus bridge insertion when mixing Wishbone and AXI4 peripherals
- PCIe BAR mapping as a first-class concept
- DMA channel configuration
- Interrupt routing (MSI/MSI-X generation from event sources)

---

## Implementation Phases

```
Phase 1 — Unblock Real-World Usage (P0 + critical P1):
  [1]  Fix CSR register ownership (DuplicateElaboratable)
  [7]  Add endianness support to bus primitives
  [5]  Relax AXI4-Lite data width restriction
  [14] Clean up empty stub files

Phase 2 — AXI4 Full Foundation (P1):
  [2]  AXI4 Full Decoder
  [3]  AXI4 Full Arbiter
  [9]  AXI4 Full SRAM
  [12] Wishbone burst support in interconnect

Phase 3 — Advanced SoC Features (P1 + P2):
  [6]  DMA infrastructure
  [8]  Enhanced interrupt controller (MSI support)
  [4]  AXI4 Full Crossbar
  [10] Wishbone Crossbar
  [11] Memory Map BAR-relative addressing

Phase 4 — Polish and Completeness (P2 + P3):
  [13] AXI4-Lite Decoder pipelining
  [15] AXI4 Full Timeout
  [16] AXI4 Full simulation helpers
  [17] Bus protocol checkers
  [18] SoC Builder enhancements
```

---

## Dependency Graph

```
[1] CSR Ownership Fix ──────────────────────────────────────→ Unblocks all CSR usage
[7] Endianness Support ─────────────────────────────────────→ Unblocks correct PCIe bridges
[5] AXI4-Lite Width ────────────────────────────────────────→ Unblocks wide AXI4-Lite usage

[2] AXI4 Decoder ──┐
[3] AXI4 Arbiter ──┼──→ [4] AXI4 Crossbar ──→ Full AXI4 interconnect
[9] AXI4 SRAM ─────┘

[8] Interrupt Controller ──→ [18] SoC Builder ──→ Complete SoC generation
[6] DMA Infrastructure ───→ [18] SoC Builder
[11] BAR-Relative MemMap ──→ [18] SoC Builder
```

---

*This roadmap is derived from the analysis in [`ANALYSIS.md`](../amaranth-pcie/ANALYSIS.md) and [`WISHBONE_VS_AXI4.md`](../amaranth-pcie/WISHBONE_VS_AXI4.md).*
