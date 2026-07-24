---
type: rule
trigger: always_on
rule_id: numba-constraints
severity: critical
---
# Mandates
- **No Python Objects:** Ban `dict`, `list`, or custom classes within `@njit` functions.
- **Array Layouts:** Require contiguous layouts and explicit dtypes (e.g., `np.float32`, `np.int32`) for JIT inputs. Avoid upcasting to `float64` unless PDE-required.
- **Pre-allocation:** Ban array allocation (`np.zeros`, `np.append`) inside JIT loops. Pre-allocate in write buffer and mutate in-place.
