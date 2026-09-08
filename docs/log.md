# PHIDS Documentation Update Log

This document records the chronological history of structural, scientific, and architectural updates to the PHIDS documentation bundle, adhering to the Open Knowledge Format (OKF v0.2 §9) specification.

## 2026-09-09

* **Refactor**: Decomposed all source and test modules exceeding 700 lines into modular packages and suites:
  * Decomposed `tests/unit/api/test_coverage_gaps.py` (1,104 lines) into 5 focused domain test suites (`test_signaling_coverage.py`, `test_interaction_coverage.py`, `test_zarr_coverage.py`, `test_flow_field_coverage.py`, `test_chartjs_coverage.py`).
  * Modularized `src/phids/mcp_server.py` into package `src/phids/mcp/` (`app.py`, `helpers.py`, `prompts.py`, `resources.py`, `tools_simulation.py`, `tools_telemetry.py`, `tools_validation.py`) with a backward-compatible facade.
  * Extracted Jacobi stencils, boundary propagators, and relaxation solvers from `src/phids/engine/core/flow_field.py` into package `src/phids/engine/core/flow/`.
  * Extracted initial entity placement from `src/phids/engine/loop.py` into `src/phids/engine/spawner.py`.
  * Extracted replay slices and no-op buffers from `src/phids/io/zarr_replay.py` into `src/phids/io/replay_types.py`.
  * Extracted Numba 2D advection and Gaussian convolution kernels from `src/phids/engine/core/biotope.py` into `src/phids/engine/core/diffusion.py`.
* **Refactor**: Centralized duplicated logic across the codebase (DRY):
  * Centralized scalar coercion in `src/phids/shared/coercion.py` (`coerce_int`, `coerce_float`) with explicit boolean rejection semantics in dashboard presenters.
  * Centralized allometric structural fragility and collapse risk calculations in `src/phids/api/presenters/dashboard/shared.py`.
  * Centralized plant entity instantiation in `PlantComponent.from_params`.
  * Reused phase-space axis boundary extraction in `src/phids/telemetry/export/core.py`.
* **Documentation**: Updated `docs/reference/api.md` and `docs/reference/module-map.md` with full coverage of the new modular packages, symbols, and utilities.
* **Audit**: Conducted a full 10-slice Epistemic Soundness Audit (`/epistemic-soundness-audit`) verifying theoretical rigor, continuous-discrete PDE stencils, branchless SIMD kernels, and OKF compliance.

## 2026-09-07

* **Update**: Aligned the Flora Species workbench (`/ui/flora`) with the Decoupled Dual-Proxy Architecture ($E_{\text{current}}$ vs. $M_{\text{structural}}$), reproductive seed energetics, and wind anemochory aerodynamics.
* **Update**: Implemented the Tiered Progressive Disclosure UX pattern in `flora_config.html`, introducing collapsible species drawers and cross-view ecosystem shortcut navigation.
* **Update**: Documented the canonical domain separation matrix in `scenario_authoring.md` and UI architecture in `interfaces_and_ui.md`, explicitly separating botanical autotrophy from heterotrophic MVT foraging kinetics and constitutive/inducible defenses.
* **Update**: Extended API endpoints (`POST /api/config/flora`, `PUT /api/config/flora/{id}`) to validate and clamp structural mass, aerodynamics, and mycorrhizal tax parameters with dedicated integration tests.
* **Update**: Integrated the KaTeX client-side mathematical formula rendering engine into the web interface root (`base.html`), dynamically typesetting LaTeX formulations across all partial HTMX view swaps.
* **Update**: Conducted a repository-wide audit for DSE expansions, reconciling the guide header in `dse/container.html` to canonical **Design Space Exploration (DSE) & Pareto Optimization Guide**.
* **Refactor**: Decomposed `config_flora_update` in `flora.py` into specialized field-extraction helpers, satisfying local cognitive complexity quality gates (`just complexity-local`).
* **Update**: Streamlined the dashboard canvas tooltip by removing the redundant top-level mycorrhizal card, consolidating root connection details and partner species identities cleanly into the plant entity card.
* **Refactor**: Purged shadowed legacy `batch.py` in favor of the modular `phids.engine.batch` package with public re-exports, elevating full repository test branch coverage to 81.6% and resolving all Zensical reference link warnings.
* **Update**: Reconstructed the coupled hybrid dynamical system Mermaid diagram in `scientific_model/index.md` into a closed-loop causal architecture connecting discrete ECS entities, continuous biotope diffusion PDEs, and sensory chemotactic flow fields.

## 2026-09-06

* **Update**: Realigned documentation architecture with Google's Open Knowledge Format (OKF v0.2).
* **Creation**: Upgraded `scripts/validate_okf.py` to enforce Option A index constraints, strict ISO 8601 UTC datetimes (`YYYY-MM-DDTHH:MM:SSZ`), actor validation, and source resource resolution.
* **Creation**: Formalized the 5 Data-Flow Matrices as first-class `Attested Computation` concepts under `docs/scientific_model/computations/`.
* **Creation**: Introduced interactive Cytoscape.js knowledge graph visualizer (`scripts/visualize_okf.py`).
* **Update**: Normalized all timestamp strings across 60+ concept documents to explicit UTC offset.

## 2026-09-04

* **Creation**: Implemented the OKF Continuous Agentic Change & Data-Flow Matrix Synchronization Protocol.
* **Creation**: Created `scripts/audit_matrix_coverage.py` and `scripts/verify_matrix_trace_parity.py` to enforce 1:1 table-to-trace parity.
* **Creation**: Added integration test suite `test_causal_data_flow_matrices.py` validating 5 core biological causal cascades.

## 2026-08-18

* **Update**: Completed the Decoupled Dual-Proxy Architecture (Plans 1, 2, 3, & 4) across ECS loops, HTMX dashboard views, and real-time Canvas inspectors.
* **Update**: Formalized Phase-Staggered Cohort Execution and Flush-to-Zero (FTZ) subnormal float elimination.

## 2026-07-26

* **Creation**: Initialized the Open Knowledge Format (OKF v0.1) metadata across all scientific model, technical architecture, and scenario guide chapters.
