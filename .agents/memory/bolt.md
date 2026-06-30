---
type: memory
---

# Bolt's Performance Journal

## 2024-05-18 - [Optimization of ECSWorld.query]
**Learning:** The previous ECS design relied on an `Iterator[Entity]` for `query(...)`, forcing callers in hot paths to wrap it in a materialized `list()` to prevent "Set changed size during iteration" errors since components could be mutated or updated concurrently in game loops. CPython actually evaluates list comprehensions with inline `[]` significantly faster than wrapping a generator in `list()`.
**Action:** Changed `world.query` to return a materialized `list[Entity]` directly using fast-path list comprehensions. This successfully removed the `list()` wrappers at call sites, making queries noticeably faster and removing boilerplate while implicitly preserving thread and mutation safety.

## 2025-02-25 - ECS Single-Component Query Fast-Path Optimization
**Learning:** The ECS engine heavily queries entities by single component types (e.g., `world.query(SwarmComponent)`) in the simulation hot loop across lifecycle, interaction, and signaling phases. The original implementation used a generalized multi-component check involving `min()`, `all()`, and set building, creating significant overhead for single-component queries.
**Action:** Added an early-exit fast path in `ECSWorld.query` for `len(component_types) == 1`, allowing direct iteration over `_component_index`, yielding a 6-7x speedup for the majority of queries without affecting multi-component functionality. Copied the set into a list before iterating to avoid runtime mutation errors since components may be added or removed during loops.

## 2025-02-26 - Python Flat List vs Dict & NumPy for spatial indexing
**Learning:** During profiling of the O(1) crowding lookups (`tile_populations`) in the interaction phase, I found that using a flat Python list (`[0] * (env.width * env.height)`) accessed via `list[y * width + x]` is ~2-3x faster than the original `dict` keyed by `(x, y)` tuples due to avoiding tuple creation and hashing overhead. Interestingly, it also marginally outperformed using a 2D NumPy array (`np.zeros((width, height), dtype=np.int32)`) for this specific workload, because modifying NumPy elements iteratively from pure Python incurs slight C-API overhead unless the operation is vectorized or fully JIT-compiled.
**Action:** When tracking dense, integer-based scalar state that must be updated iteratively within pure Python logic without Numba or vectorization (like spatial population accumulation), pre-allocating a flat Python list often provides the fastest mutable caching structure.

## 2025-02-27 - [Flow-Field Propagation - Push toxin layer summing to Numba JIT loop]
**Learning:** Python-level NumPy operations like `toxin_layers.sum(axis=0)` inside hot loops create a new array object, which results in unnecessary dynamic memory allocations per simulation tick.
**Action:** Replaced `toxin_layers.sum(axis=0)` array aggregation outside of the Numba wrapper with an inline `for t in range(num_toxins): t_sum += toxin_layers[t, x, y]` iteration directly within the `@njit` kernel in `_compute_flow_field_impl`. Numba can handle this inline summing extremely efficiently, eliminating object allocations inside the hot propagation kernel and measurably improving operations per second and median latencies.
