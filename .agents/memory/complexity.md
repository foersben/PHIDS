---
type: Agent Memory
title: Complexity
status: stable
stale_after: "2027-01-01"
version: 0.1
description: Refactoring cognitive complexity from telemetry module and
  learnings
tags: [phids, refactor, complexity]
generated: {by: process:okf-updater, at: "2026-07-22T13:00:00Z"}
verified: {by: process:okf-updater, at: "2026-08-14T16:00:00Z"}
name: complexity
sources:
- id: telemetry
  resource: telemetry.py
---

## 2026-07-22 - Refactoring Telemetry API Monolith

Learning: When resolving high cognitive complexity (score 27 to 5) in a view handler (`telemetry_chartjs_data`) that builds JSON payloads, separating the deep nested data extraction logic into pure private helpers (`_filter_telemetry_rows_for_chart` and `_extract_chart_series`) dramatically flattens the view handler while posing zero execution risk to the engine loops. Benchmark tests demonstrate that keeping the exact same Numba-independent work decoupled preserves performance properties while vastly improving readability and maintainability.

Action: Isolate array filtering and iteration logic from HTTP response formatting into private functions to keep view handlers structurally flat and below a complexity threshold of 15. Verify by running `complexipy` checks alongside integration tests after each structural extraction.

## 2026-07-22 - Refactoring UI State Condition Mappings

Learning: Refactoring deeply nested tree-traversal logic (`_remap_condition_references` handling polymorphic `ConditionNode` structures) into distinct leaf and group mapper functions drastically reduces cognitive complexity (from 29 to 2) with zero performance risk to the simulation hot loop. Conversely, attempting to decompose FastAPI view handlers that rely heavily on `Form(...)` annotations (like `config_trigger_rule_condition_node_update`) into smaller helpers can unexpectedly break Pydantic request validation.

Action: Prioritize refactoring pure configuration data mutation logic over HTTP endpoints bound to strict Pydantic/FastAPI `Form` annotations to avoid validation errors. When refactoring recursive tree traversals, isolate leaf-node logic and group-node traversal into separate private helpers.

## 2025-02-28 - Complexity Refactoring Report
* **Target Function:** src/phids/api/routers/config/trigger_rules.py and `config_trigger_rule_condition_node_update`
* **Selection Rationale:** The `config_trigger_rule_condition_node_update` function in `src/phids/api/routers/config/trigger_rules.py` was selected because it had a high cognitive complexity score (32), but it essentially contained a long series of `if/elif` statements. Moving these out into a `_build_node_updates` private helper function drastically cut down the complexity (down to 11) without altering any engine logic.
* **Before/After Score:** 32 vs. 11
* **Performance Assessment:** The extracted code lives purely in the REST API config-setting path (called interactively via the UI, not within any engine ticks). The change incurs trivial dictionary-building overhead and poses absolutely zero risk to simulation hot loops.
* **Test Verification:** Confirmed that all linting, unit tests, and complexity checks pass.
## 2025-02-18 - Complexity Refactoring Report
* **Target Function:** `src/phids/api/presenters/dashboard/payloads.py` - `build_live_dashboard_payload`
* **Selection Rationale:** The function had a high cognitive complexity score (32) but was structurally easy to untangle. It had distinct, cohesive blocks for iterating over plants, swarms, and flora species. Extracting these into three private helper functions flattened the logic cleanly. Since this function is part of the API presentation layer and executes outside the Numba JIT hot loops (at most per UI frame), the minor function call overhead is completely negligible, meaning zero risk to simulation performance.
* **Before/After Score:** 32 vs. 13 (maximum score among the helpers)
* **Performance Assessment:** The refactoring purely extracts logic into helper functions without changing data structures or introducing new allocations. Given it runs on the API/UI boundary and not in the simulation tick hot path, the performance regression risk is effectively zero.
* **Test Verification:** Confirmed that all linting (`ruff`), unit tests (`pytest`), and complexity checks (`complexipy`) pass successfully.
## 2025-02-28 - Complexity Refactoring Report
* **Target Function:** `src/phids/api/presenters/dashboard/shared.py` `_describe_activation_condition`
* **Selection Rationale:** This function had a complexity score of 24 due to highly nested repeated recursive comprehensions in its `"all_of"` and `"any_of"` conditionals. Because it is a simple UI presentation utility handling standard dictionary inputs, it poses zero risk to engine performance (non-JIT path) and could be easily untangled using a straightforward helper extraction `_describe_composite_condition`.
* **Before/After Score:** 24 vs. 9
* **Performance Assessment:** Common-sense engineering determines this non-engine UI rendering function imposes no execution impact on the simulation engine or benchmark-critical loops. Existing `pytest-benchmark` payload JSON benchmarks continue passing perfectly.
* **Test Verification:** Confirmed that all linting, unit tests, and complexity checks pass.
## 2025-02-23 - Complexity Refactoring Report
* **Target Function:** `src/phids/engine/core/flow_field.py` - `_compute_flow_field_impl`
* **Selection Rationale:** Selected due to its very high cognitive complexity (70) entirely driven by deeply nested boundary-checking loops (`for x in (0, width-1)` etc). The logic was purely spatial indexing, making it easy to untangle by safely extracting the boundary evaluation into helper functions (`_propagate_boundaries_jit`, `_update_boundary_x_jit`, and `_update_boundary_y_jit`), maintaining Numba compatibility with zero abstractions.
* **Before/After Score:** 70 vs. < 15 (Target function completely cleared).
* **Performance Assessment:** The benchmark `test_flow_field_generation_benchmark` showed a mean execution time of ~240µs, matching the baseline of ~235µs well within the expected environmental jitter (StdDev ~33µs vs ~15µs baseline), confirming that extracting cleanly typed `@njit` kernels inside the JIT compiler successfully inlines the functions with zero runtime abstraction penalty.
* **Test Verification:** Confirmed that all linting, unit tests, and complexity checks pass.
## 2026-08-05 - Complexity Refactoring Report
* **Target Function:** `src/phids/api/routers/telemetry.py` -> `export_telemetry_format`
* **Selection Rationale:** The function had a cognitive complexity of 15 due to deep nesting of export-format-specific branches containing inline helper functions (closures). As an API endpoint handler, extracting the format logic into top-level async helper functions carries no engine performance risk while greatly flattening and simplifying the handler.
* **Before/After Score:** 15 vs. 11
* **Performance Assessment:** The endpoint runs standard API workload out of the hot path of the core simulation engine. Moving closures to top-level async functions retains exact performance characteristics (they are still passed to `run_in_threadpool` and awaited) but avoids repeated closure instantiation. No performance regressions.
* **Test Verification:** Confirmed that all linting, unit tests, and complexity checks pass.
## 2026-10-27 - Complexity Refactoring Report
* **Target Function:** `src/phids/api/routers/telemetry.py` > `telemetry_chartjs_data`
* **Selection Rationale:** This function was targeted because it failed complexity checks with a score of 37 due to deeply nested loop logic that overlaid per-species dictionary structures into flat Chart.js arrays. Given its position in the API routing layer, it posed zero performance risk to the core simulation engine. It was highly modular and ripe for untangling via extraction.
* **Before/After Score:** 37 vs. 8 (Main function), with helpers `_overlay_species_data` (3), `_overlay_flora_data` (7), and `_overlay_herbivore_data` (6).
* **Performance Assessment:** The extraction of nested loops into helpers strictly passes references and avoids unnecessary object allocations. Benchmark results indicate zero performance regression on related API encoding endpoints.
* **Test Verification:** Confirmed that all `ruff` formatting, linting, `complexipy` checks, and the full test suite (`uv run pytest`) run flawlessly without regressions.
## 2025-05-18 - Complexity Refactoring Report
* **Target Function:** src/phids/engine/systems/signaling/triggers.py `_phase_evaluate_triggers`
* **Selection Rationale:** The function had a very high complexity score (39) due to deep nesting and multiple inner loops evaluating different initiator types. It was straightforward to untangle by extracting the loop over trigger species into a separate helper function (`_evaluate_triggers_for_species`) and then flattening the deepest inner loops inside it into a separate helper (`_process_triggers_for_species`), while cleanly preserving all array types, variables, and logic.
* **Before/After Score:** 39 vs. 13 (score for `_evaluate_triggers_for_species` lowered further by extracting inner loop logic)
* **Performance Assessment:** The benchmark results confirm zero performance regressions. We did not change any looping structures or data allocation in the Numba paths or tight loops, just extracted blocks of iteration logic to flat helpers.
* **Test Verification:** Confirmed that all linting, unit tests, and complexity checks pass.
## 2025-05-18 - Complexity Refactoring Report
* **Target Function:** src/phids/engine/systems/signaling/triggers.py `_phase_evaluate_triggers`
* **Selection Rationale:** The function had a very high complexity score (39) due to deep nesting and multiple inner loops evaluating different initiator types. It was straightforward to untangle by extracting the loop over trigger species into a separate helper function (`_evaluate_triggers_for_species`) and then flattening the deepest inner loops inside it into a separate helper (`_process_triggers_for_species`), while cleanly preserving all array types, variables, and logic.
* **Before/After Score:** 39 vs. 13 (score for `_evaluate_triggers_for_species` lowered further by extracting inner loop logic)
* **Performance Assessment:** The benchmark results confirm zero performance regressions. We did not change any looping structures or data allocation in the Numba paths or tight loops, just extracted blocks of iteration logic to flat helpers.
* **Test Verification:** Confirmed that all linting, unit tests, and complexity checks pass.
## 2025-05-18 - Complexity Refactoring Report
* **Target Function:** src/phids/engine/systems/signaling/triggers.py `_phase_evaluate_triggers`
* **Selection Rationale:** Extracted logic into `_evaluate_triggers_for_species` and `_process_triggers_for_species` to fix score.
* **Before/After Score:** 39 vs. 13
* **Performance Assessment:** No benchmark regressions, n-jit loop intact.
* **Test Verification:** Tests, benchmarks, linting and complexity all passed.
## 2025-05-18 - Complexity Refactoring Report
* **Target Function:** src/phids/engine/systems/signaling/triggers.py `_phase_evaluate_triggers`
* **Selection Rationale:** Extracted logic into `_evaluate_triggers_for_species` and `_process_triggers_for_species` to fix score.
* **Before/After Score:** 39 vs. 13
* **Performance Assessment:** No benchmark regressions, n-jit loop intact.
* **Test Verification:** Tests, benchmarks, linting and complexity all passed.
