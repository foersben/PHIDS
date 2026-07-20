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
## 2024-07-02 - Zensical Documentation and Mermaid
Learning: The Python test suite for `test_batch_runner.py` contains a test (`test_run_single_headless_breaks_when_termination_detected`) that is structurally broken in the repository's base state regarding the `_FakeLoop` constructor signature (missing `disable_replay` kwarg acceptance), which initially caused pytest failures.
Action: When modifying purely documentation files inside `docs/`, utilize targeted test running (`pytest tests/ <target_file>`) or explicitly note that existing integration test failures are disjoint from documentation updates. Do not attempt to fix unrelated tests in documentation PRs.

## 2024-05-18 - [Optimization of ECSWorld.query multi-component checks]
**Learning:** The previous ECS design used `min()` to find the smallest component set, then checked for intersection using `all(...)` across all components inside a list comprehension. This iteration and function call in python is slow. A better approach is to sort the component index sets by length and use Python's C-level `set.intersection_update()` down an initial copied set, which significantly outperforms purely iterating via list comprehensions with `all()` component checks.
**Action:** Changed the multi-component logic in `ECSWorld.query` to use `set.intersection_update()`. This significantly improves the execution speed of multi-component checks.

## 2026-07-17 - Optimize ECS Query Fast-Path
Learning: Iterating through an ECS component index and doing secondary lookup checks like `if eid in entities and ct in entities[eid]._components` is slow inside hot loops. Because the ECS is carefully managed, `_component_index` is strictly synchronized with `_entities`.
Action: Rely on invariant synchronization to safely drop defensive dictionary lookups in hot path queries. Fail-fast on desynchronization rather than silently masking it with `if in` checks.

## 2026-07-20 - Unnecessary Tuple Allocation in Read-Only Component Passes
**Learning:** During the `interaction` system, the engine was iterating over `tuple(world._component_index.get(SwarmComponent, set()))` for an initial read-only population accumulation pass. While wrapping the component index set in a tuple is strictly necessary when the loop modifies the ECS (to avoid "Set changed size during iteration" errors), doing this on a purely read-only pass introduces an unnecessary O(N) allocation per tick (where N is the number of swarms).
**Action:** Always identify whether an ECS loop mutates the world state. If it is purely read-only (e.g., just accumulating metrics or building read caches), iterate directly over the component index set without wrapping it in a `list` or `tuple` to save per-tick allocation overhead.
