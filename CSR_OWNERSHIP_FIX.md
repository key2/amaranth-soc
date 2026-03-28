# CSR Register Ownership: The DuplicateElaboratable Problem and Its Solution

## The Problem

When a peripheral (e.g., a DMA engine) creates CSR registers and a separate CSR Bridge tries to expose them to a bus, Amaranth raises `DuplicateElaboratable` because the same `Register` object would be added as a submodule to two different parent modules.

### The Ownership Chain That Breaks

1. **DMA engine creates registers** in `__init__`:
   ```python
   self.enable_reg = csr.Register({"enable": csr.Field(csr_action.RW, 1)}, access="rw")
   ```

2. **DMA engine elaborates registers** as submodules in `elaborate()`:
   ```python
   m.submodules.enable = self.enable_reg  # DMA owns it
   ```

3. **A `Bridge` is created** to expose registers to the host via CSR bus. The Bridge's [`elaborate()`](amaranth_soc/csr/reg.py:814) with default `ownership="owned"` does:
   ```python
   m.submodules["enable"] = reg  # Bridge also tries to own it → 💥 DuplicateElaboratable
   ```

### Where It Happens in Code

- [`Bridge.__init__()`](amaranth_soc/csr/reg.py:789) creates a [`Multiplexer`](amaranth_soc/csr/bus.py:505) from the memory map
- [`Bridge.elaborate()`](amaranth_soc/csr/reg.py:814) at line 818-820 adds registers as submodules when `ownership="owned"`:
  ```python
  if self._ownership == "owned":
      for reg, reg_name, _ in self.bus.memory_map.resources():
          m.submodules["__".join(str(name) for name in reg_name)] = reg
  ```
- The [`Multiplexer.elaborate()`](amaranth_soc/csr/bus.py:530) directly accesses `reg.element` signals at lines 562-596 but does **not** add registers as submodules

### Real-World Impact

The amaranth-pcie tang_mega_138K_pro example was forced to create a custom [`WishboneCSRBank`](../amaranth-pcie/examples/tang_mega_138K_pro/gw_pcie_test/top.py:71) (75 lines of manual register mapping) that bypasses the entire amaranth-soc CSR infrastructure. This loses:
- Automatic address allocation
- Shadow register atomicity for wide registers
- Memory map for SVD/C-header export
- Standard bus bridge integration

---

## The Solution: `ownership="external"` Already Exists

### Discovery

The `Bridge` class already supports `ownership="external"` at [`reg.py:789`](amaranth_soc/csr/reg.py:789). When set, the Bridge's `elaborate()` **skips** the `m.submodules[...] = reg` line (line 818 condition is false), avoiding `DuplicateElaboratable`.

The `Multiplexer` works correctly with external ownership because it only accesses `reg.element` signals via `m.d.comb` and `m.d.sync` — it never adds registers as submodules.

### Why There Are No Driver Conflicts

The [`Element.Signature`](amaranth_soc/csr/bus.py:53) defines clear signal directions:

| Signal | Direction (from register's `In` perspective) | Driven by |
|--------|----------------------------------------------|-----------|
| `r_data` | Register → Bus | Register's `FieldAction` (via `elaborate()`) |
| `r_stb` | Bus → Register | Multiplexer |
| `w_data` | Bus → Register | Multiplexer |
| `w_stb` | Bus → Register | Multiplexer |

The register drives `r_data` (read data from fields). The Multiplexer drives `r_stb`, `w_data`, `w_stb` (bus access strobes and write data). These are **complementary directions** — no conflict.

### The Correct Pattern

```python
from amaranth_soc import csr
from amaranth_soc.csr.wishbone import WishboneCSRBridge

# 1. Peripheral creates and owns its registers
class MyDMA(wiring.Component):
    def __init__(self):
        self.enable_reg = csr.Register(
            {"enable": csr.Field(csr_action.RW, 1)},
            access="rw"
        )
        self.status_reg = csr.Register(
            {"busy": csr.Field(csr_action.R, 1)},
            access="r"
        )
        super().__init__({...})
    
    def elaborate(self, platform):
        m = Module()
        # DMA owns and elaborates its registers
        m.submodules.enable = self.enable_reg
        m.submodules.status = self.status_reg
        
        # DMA reads register fields for its logic
        with m.If(self.enable_reg.f.enable.data):
            ...  # DMA operation
        
        # DMA writes status back
        m.d.comb += self.status_reg.f.busy.r_data.eq(self.busy)
        return m

# 2. Build CSR memory map referencing the same registers
dma = MyDMA()

builder = csr.Builder(addr_width=10, data_width=8)
builder.add("enable", dma.enable_reg)
builder.add("status", dma.status_reg)

# 3. Create Bridge with ownership="external"
#    Bridge will NOT try to elaborate the registers
bridge = csr.Bridge(builder.as_memory_map(), ownership="external")

# 4. Create bus bridge (Wishbone or AXI4-Lite)
wb_csr = WishboneCSRBridge(bridge.bus, data_width=32)

# 5. In top-level elaborate():
def elaborate(self, platform):
    m = Module()
    m.submodules.dma = dma           # DMA elaborates its own registers
    m.submodules.csr_bridge = bridge  # Bridge elaborates Multiplexer only
    m.submodules.wb_csr = wb_csr     # Wishbone-to-CSR bridge
    
    # Connect Wishbone
    connect(m, pcie_wb_master.wb, wb_csr.wb_bus)
    return m
```

### What This Gives You

| Feature | Custom WishboneCSRBank | Bridge(ownership="external") |
|---------|----------------------|------------------------------|
| Automatic address allocation | ❌ Manual | ✅ Via Builder |
| Shadow register atomicity | ❌ Simplified | ✅ Full Multiplexer scheme |
| Memory map for export | ❌ None | ✅ SVD, C headers, device tree |
| Bus bridge integration | ❌ Manual Wishbone | ✅ WishboneCSRBridge or AXI4LiteCSRBridge |
| DuplicateElaboratable | ✅ Avoided | ✅ Avoided |
| Driver conflicts | ✅ None | ✅ None |

---

## How the InterruptController Already Uses This Pattern

The [`InterruptController`](amaranth_soc/periph/intc.py:56) demonstrates the pattern:

1. Creates registers internally (line 62-70)
2. Creates its own `Multiplexer` directly (line 76)
3. Elaborates both registers and multiplexer in its own `elaborate()` (lines 97-99)
4. Exposes the CSR bus interface for external connection

This works because the `InterruptController` is the **sole owner** of its registers. The same pattern applies when using `Bridge(ownership="external")` — the peripheral is the sole owner, and the Bridge just connects the bus to the element interfaces.

---

## Recommended Improvements to amaranth-soc

### 1. Documentation (Priority: High, Effort: Low)

Add documentation and examples for the `ownership="external"` pattern in:
- [`csr/reg.py`](amaranth_soc/csr/reg.py) Bridge class docstring
- README.md CSR section
- A dedicated "CSR Patterns" documentation page

### 2. Builder Validation (Priority: Medium, Effort: Low)

Add a warning in [`Builder.add()`](amaranth_soc/csr/reg.py:642) when the same register is added to multiple builders:

```python
def add(self, name, register):
    if hasattr(register, '_csr_builder_ref') and register._csr_builder_ref is not self:
        warnings.warn(f"Register {name} is already added to another Builder. "
                      f"Use ownership='external' in Bridge to avoid DuplicateElaboratable.")
    register._csr_builder_ref = self
    ...
```

### 3. Convenience Method (Priority: Low, Effort: Low)

Add a `Bridge.from_peripheral()` class method that automatically uses `ownership="external"`:

```python
@classmethod
def from_peripheral(cls, peripheral, registers, *, addr_width, data_width):
    """Create a Bridge for registers owned by an external peripheral.
    
    Automatically sets ownership="external".
    """
    builder = csr.Builder(addr_width=addr_width, data_width=data_width)
    for name, reg in registers.items():
        builder.add(name, reg)
    return cls(builder.as_memory_map(), ownership="external")
```

### 4. Test Coverage (Priority: Medium, Effort: Low)

Add a test in `test_csr_reg.py` that verifies the external ownership pattern:

```python
def test_bridge_external_ownership_no_duplicate():
    """Verify that Bridge(ownership='external') doesn't cause DuplicateElaboratable
    when registers are owned by another component."""
    # Create a peripheral that owns registers
    # Create a Bridge with ownership="external" referencing the same registers
    # Elaborate both — should not raise DuplicateElaboratable
```

---

## Migration Guide for amaranth-pcie

Replace the custom [`WishboneCSRBank`](../amaranth-pcie/examples/tang_mega_138K_pro/gw_pcie_test/top.py:71-174) and [`_build_register_map()`](../amaranth-pcie/examples/tang_mega_138K_pro/gw_pcie_test/top.py:177-241) with:

```python
# Before (75 lines of custom code):
csr_bank = WishboneCSRBank(registers=[...], data_width=32)
# Manual address mapping, manual element driving, no memory map

# After (10 lines using standard infrastructure):
builder = csr.Builder(addr_width=10, data_width=8)
builder.add("writer_enable", dma.writer.writer.enable_reg)
builder.add("writer_table_value", dma.writer.table.value)
# ... add all DMA registers

bridge = csr.Bridge(builder.as_memory_map(), ownership="external")
wb_csr = WishboneCSRBridge(bridge.bus, data_width=32)

# In elaborate():
m.submodules.dma = DomainRenamer("pcie")(dma)
m.submodules.csr_bridge = DomainRenamer("pcie")(bridge)
m.submodules.wb_csr = DomainRenamer("pcie")(wb_csr)
connect(m, wb_master.wb, wb_csr.wb_bus)
```

This eliminates 75 lines of custom CSR code and gains automatic address allocation, shadow register atomicity, and memory map export capability.

---

*This analysis is based on examination of [`csr/bus.py`](amaranth_soc/csr/bus.py), [`csr/reg.py`](amaranth_soc/csr/reg.py), and the amaranth-pcie workaround at [`top.py:71-241`](../amaranth-pcie/examples/tang_mega_138K_pro/gw_pcie_test/top.py:71).*
