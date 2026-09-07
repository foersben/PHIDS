# PHIDS Documentation Update Log

This document records the chronological history of structural, scientific, and architectural updates to the PHIDS documentation bundle, adhering to the Open Knowledge Format (OKF v0.2 §9) specification.

## 2026-09-07

* **Update**: Aligned the Flora Species workbench (`/ui/flora`) with the Decoupled Dual-Proxy Architecture ($E_{\text{current}}$ vs. $M_{\text{structural}}$), reproductive seed energetics, and wind anemochory aerodynamics.
* **Update**: Implemented the Tiered Progressive Disclosure UX pattern in `flora_config.html`, introducing collapsible species drawers and cross-view ecosystem shortcut navigation.
* **Update**: Documented the canonical domain separation matrix in `scenario_authoring.md` and UI architecture in `interfaces_and_ui.md`, explicitly separating botanical autotrophy from heterotrophic MVT foraging kinetics and constitutive/inducible defenses.
* **Update**: Extended API endpoints (`POST /api/config/flora`, `PUT /api/config/flora/{id}`) to validate and clamp structural mass, aerodynamics, and mycorrhizal tax parameters with dedicated integration tests.
* **Update**: Integrated the KaTeX client-side mathematical formula rendering engine into the web interface root (`base.html`), dynamically typesetting LaTeX formulations across all partial HTMX view swaps.
* **Update**: Conducted a repository-wide audit for DSE expansions, reconciling the guide header in `dse/container.html` to canonical **Design Space Exploration (DSE) & Pareto Optimization Guide**.
* **Refactor**: Decomposed `config_flora_update` in `flora.py` into specialized field-extraction helpers, satisfying local cognitive complexity quality gates (`just complexity-local`).

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
