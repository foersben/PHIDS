---
type: Agent Rule
title: Numba Constraints
status: stable
stale_after: "2027-01-01T00:00:00Z"
version: 1.1
description: Constraints for Numba JIT compilation in PHIDS.
tags: [numba, performance, simd]
generated: {by: process:okf-updater, at: "2026-08-14T00:30:00Z"}
verified: {by: process:okf-updater, at: "2026-08-14T16:00:00Z"}
trigger: always_on
rule_id: numba-constraints
severity: critical
---

# Mandates

- **No Python Objects:** Ban `dict`, `list`, or custom classes within `@njit` functions.
- **Array Layouts:** Require contiguous layouts and explicit dtypes (e.g., `np.float32`, `np.int32`) for JIT inputs. Avoid upcasting to `float64` unless PDE-required.
- **Pre-allocation:** Ban array allocation (`np.zeros`, `np.append`) inside JIT loops. Pre-allocate in write buffer and mutate in-place.
- **Float Masking:** State transitions must be represented as array-to-array transfers gated by float masks (`0.0` or `1.0`), prohibiting scalar enums or `if/else` state branching in JIT hot paths.
- **Absolute Value Avoidance:** Inside tight loops, avoid `abs(val) < threshold`. Replace with inline logic `val > -threshold and val < threshold` to reduce LLVM overhead and improve auto-vectorization.
- **Testing Fallbacks:** When accessing Python fallbacks of JIT-compiled functions in unit tests, always use `getattr(func, "py_func", func)` instead of direct `.py_func` access. This prevents `AttributeError` failures in CI pipelines where `NUMBA_DISABLE_JIT=1` is active.
