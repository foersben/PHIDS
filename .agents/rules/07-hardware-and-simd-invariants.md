---
type: Agent Rule
trigger: always_on
description: Hardware, cache alignment, branchless SIMD masking, and zero-allocation hot-path invariants.
---

# Hardware & SIMD Invariants

Mandates governing AVX2/AVX-512 vectorization, CPU cache line alignment, memory layout, and zero-allocation execution in PHIDS JIT kernels.

## 1. Branchless SIMD Float Masking

* **Float Mask Gating (Rule 05-B):** State transitions and conditional physics inside `@njit` kernels must execute branchlessly via float masks ($0.0$ or $1.0$ multipliers), e.g. `delta = rate * alive_mask * capacity_mask`.
* **Zero Scalar Branching:** Prohibit scalar `if/else` conditionals over individual entity state attributes inside inner loops. Branching inhibits LLVM auto-vectorization and degrades instruction pipelining.
* **Absolute Value Optimization:** Inside tight loops, avoid `abs(val) < threshold`. Replace with branchless inline interval checks `val > -threshold and val < threshold`.

## 2. Memory Contiguity & Cache Alignment

* **Contiguous C-Order:** All NumPy array buffers passed to JIT kernels must be contiguous C-order (`np.ascontiguousarray`) with explicit single-precision dtypes (`np.float32`, `np.int32`).
* **Cache Line Alignment (64 Bytes):** Structure-of-Arrays (SoA) component columns must be sized and aligned to 64-byte boundaries (16 `float32` lanes) to optimize SIMD vector registers and prevent false sharing.
* **Toroidal Wrapping:** Use power-of-two spatial grid dimensions (`width = 2^k`) so boundary wrapping compiles to bitwise AND instructions (`x & (width - 1)`) rather than costly integer modulo (`x % width`).

## 3. Zero-Allocation Hot Paths

* **Zero Dynamic Allocations:** Inside `@njit` kernels, ban dynamic instantiations (`np.zeros`, `np.empty`, `list`, `dict`, `set`, generator expressions, or closures).
* **Pre-Allocation in Write Buffer:** All intermediate scratch arrays must be pre-allocated once in the `_write` layer during system initialization and mutated in-place.
* **Gating Expressions:** Hot-path activation gates must use zero-allocation reductions like `arr.max() >= EPSILON` rather than allocating boolean masks via `np.any(arr >= EPSILON)`.
