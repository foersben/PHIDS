---
type: Agent Memory
title: Chisel
status: active
version: 0.1
description: Refactoring dashboard presenter monolithic logs and learnings
tags: [phids, ecs, numba]
generated: {by: process:okf-updater, at: "2026-07-21T16:01:38Z"}
name: chisel
sources:
- resource: dashboard.py
- resource: helpers.py
- resource: cell_details.py
- resource: payloads.py
- resource: mycorrhizal.py
- resource: substances.py
- resource: shared.py
- resource: interaction.py
- resource: draft/biotope.py
- resource: draft/species.py
- resource: __init__.py
---

## 2026-07-10 - Refactoring Dashboard Presenter Monolith

Learning: When extracting logic from a large presenter monolith (`dashboard.py`) into smaller cohesive modules (`helpers.py`, `cell_details.py`, `payloads.py`, `mycorrhizal.py`, `substances.py`), it is critical to ensure a 1:1 structural translation. If any payload dictionary keys are modified, missing, or renamed (e.g. `species_energy` vs `plant_energy`), or if state evaluation logic is inadvertently inverted (`active` vs `not active`), frontend and API tests will break. Refactoring must strictly maintain backwards compatibility with existing consumers.

Action: Run all tests after each structural extraction to ensure invariant behavior and schemas are fully preserved before moving to the next chunk of code.

## 2026-07-13 - Extracting shared pure functions

Learning: When extracting pure utility functions out of multiple domain modules into a single shared utility file (e.g. `shared.py` from `helpers.py`, `mycorrhizal.py`), you need to be very careful that the implementation extracted matches the tests that depend on it. In this case, `_describe_activation_condition` in `helpers.py` had small string formatting differences (`count ≥` vs `≥`, `is active` vs `active`, `concentration >` vs `concentration ≥`, `empty all_of` vs `unconditional`) from the tests, causing test failures. Always ensure the extracted implementation strictly matches the integration tests expectation.
Action: Run integration tests frequently and trace the specific formatting discrepancies before relying on simple file merges.

## 2026-07-15 - Extracting mathematical kernels from interaction monolith

Learning: When refactoring monolithic ECS engine modules (like interaction.py) into a package structure, extracting the core biological and mathematical logic (e.g., mitosis, feeding, metabolism) must be a strict 1:1 structural copy of the original functions. Abstracting or manually rewriting the logic often subtly breaks mathematical determinism and Pytest invariant checks (e.g., test_reproduction_population_is_monotone_in_initial_energy), even if the logic appears equivalent at a glance. Furthermore, moving `numba.njit` decorated functions across modules can lead to JIT recompilation errors (`TypeError: A jit decorator was called on an already jitted function`) if not careful about import structure or if the decorator is mistakenly applied twice during refactoring.

Action: Always copy-paste the exact function body when breaking up scientific model code, and run the invariant tests specifically after each functional block is moved. Verify Numba decorator placement carefully.

## 2026-07-19 - Extracting DraftService Monolith into Pure Functional Modules

Learning: When dismantling a state-mutation God Class (like `DraftService` manipulating `DraftState`), separating imperative mutations into pure functions across domain-specific modules (e.g., `draft/biotope.py`, `draft/species.py`) safely preserves API routing boundaries without mutating instance state, provided all static references to the class are replaced with function imports repository-wide.

Action: Future extractions of stateless manager classes must directly convert to free functions inside `__init__.py` or domain files to ensure the monolithic wrapper is deleted without leaving adapter classes behind.

## 2026-07-19 - Pydantic TypeAdapter for Polymorphic Trees

Learning: When parsing nested, discriminated UI configuration payloads (like `activation_condition` trees) in the PHIDS API, validating against the wrapper schema (`TriggerConditionSchema`) causes Pydantic to expect action metadata rather than just the condition leaf node itself, throwing "Extra inputs are not permitted [type=extra_forbidden]".
Action: Use `TypeAdapter(ConditionNode)` to correctly validate the root of the recursive discriminated condition tree when isolating builder validation logic.

## 2026-07-19 - Fast-API Monolith Extraction and `__future__` Imports

Learning: Extracting utility methods and Pydantic schemas out of a monolithic `phids.api.main` file cleans the module graph significantly but introduces severe import-ordering strictness under `ruff`. `from __future__ import annotations` must be the absolute first statement following the module docstring, overriding `typing.TYPE_CHECKING` blocks and standard library imports, otherwise `F404` and `E402` linting errors block PR validation.
Action: Ensure script-based refactors explicitly locate and insert `from __future__ import annotations` precisely at `docstring_end + 1` before rearranging any other dependencies.

## 2024-05-18 - Extraction of database compilation helpers from run_all.py

Learning: Extracting functional helpers requires careful handling of multiline functions and docstrings when replacing code. While it's tempting to use string replacement or regex tools directly in shell scripts, Python AST parsing or simply rewriting cleaner functions with proper imports and manual formatting verification is safer to preserve Google-style docstrings, especially across heavily typed DataFrame builders.
Action: Next time a monolith is identified, ensure that all extracted functions strictly inherit their full Google-style docstrings into the new modules to prevent CI or persona constraint failures for documentation debt.

## 2026-08-03 - Extracting Multiprocessing Runners

Learning: When extracting a `multiprocessing.spawn`-based runner function (like `_run_single_headless` or `_run_and_save`) from a monolith into a package submodule, the target functions must remain top-level module functions in their new locations to satisfy `pickle` serialization requirements. Wrapping them in classes or inner scopes will immediately break the `ProcessPoolExecutor` dispatcher.
Action: Retain module-level runner functions in isolation (e.g. `runner.py`) when dismantling batch execution engines.

## 2026-08-03 - Extracting Utility Methods from SimulationLoop

Learning: Extracting parameter lookup utilities out of large ECS orchestrator classes (like `SimulationLoop`) into dedicated pure functional modules (`herbivore_params.py`) prevents the God class from acting as a centralized dictionary wrapper. When extracting these, ensure they take `dict` instances rather than object references to decouple state effectively.

Action: When dismantling ECS God classes, extract lookup/calculation utilities that only access static or pre-computed data (`_herbivore_params`) into independent pure functional packages (`core/herbivore_params.py`) to reduce file length and increase testability.

## 2025-05-15 - Splitting the Cell Details Monolith

Learning: The `src/phids/api/presenters/dashboard/cell_details.py` file grew to over 700 lines, mixing both live simulation state extraction and draft/preview state extraction into a single monolith. This created a structural bottleneck in the UI layer. By splitting it into `cell_details/live.py` and `cell_details/preview.py`, we maintained strict domain segregation without breaking any tests, as long as `__init__.py` properly exported the expected functions. The `ruff` linting and formatting successfully cleaned up the unused imports automatically.

Action: When dealing with presentation layers that handle distinct application modes (e.g., live engine vs draft builder), extract them into isolated modules within a package, and rely on `__init__.py` to provide a unified public interface. This preserves backwards compatibility for importers while eliminating the monolith.

## 2026-10-27 - Trigger Re-arming State Coupling
**Learning:** The `SubstanceComponent` lacked sufficient state memory to distinguish between a newly triggered synthesis event and a continuing synthesis event waiting for its activation condition. Both states appeared identical (`active=False`, `synthesis_remaining=0`). This led to premature resetting of `synthesis_remaining` in `_apply_synthesize_action`. Furthermore, `_process_single_trigger` incorrectly bypassed activation condition checks for `SynthesizeSubstanceAction`.
**Action:** Introduced `triggered_last_tick` to `SubstanceComponent`, updated during `_phase_index_and_clean_substances`. This decouples the state and correctly identifies whether a synthesis trigger is a new event (where it should re-arm) versus an ongoing waiting phase. Never use zeroed countdowns (`synthesis_remaining <= 0`) as the sole proxy for state transitions in discrete simulation loops.
