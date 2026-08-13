---
type: rule
title: Numba Constraints
status: active
version: 1.1
description: Constraints for Numba JIT compilation in PHIDS.
tags:
- numba
- performance
- simd
timestamp: "2026-08-14T00:30:00Z"
resources: []
trigger: always_on
rule_id: numba-constraints
severity: critical
---

# Mandates

- **No Python Objects:** Ban `dict`, `list`, or custom classes within `@njit` functions.
- **Array Layouts:** Require contiguous layouts and explicit dtypes (e.g., `np.float32`, `np.int32`) for JIT inputs. Avoid upcasting to `float64` unless PDE-required.
- **Pre-allocation:** Ban array allocation (`np.zeros`, `np.append`) inside JIT loops. Pre-allocate in write buffer and mutate in-place.
- **Float Masking:** State transitions must be represented as array-to-array transfers gated by float masks (`0.0` or `1.0`), prohibiting scalar enums or `if/else` state branching in JIT hot paths.
