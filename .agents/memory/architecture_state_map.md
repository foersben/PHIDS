---
type: Agent Memory
title: Current Architecture State (November 2026)
status: stable
stale_after: "2027-06-01T00:00:00Z"
version: 1.2
description: Active architecture state detailing implemented stages, test gates, agentic OS tooling, and pre-v1.0 horizons.
tags: [architecture, status, memory, okf, zarr, toolchain, skills]
generated: {by: "process:agent-os-refactor", at: "2026-10-30T00:00:00Z"}
verified: {by: "human:benjamin-foerster", at: "2026-11-26T02:35:00Z"}
---

## Current Architecture State (November 2026)

* **Python Runtime & Toolchain:** Python 3.13 strictly managed via Astral `uv` and anchored in `.agents/toolchain.yaml`. Strict `mypy` typing across `src/phids` and `scripts/`, `ruff` linting/formatting, soft-wrapped Google-style docstrings with selective `Why:`/`How:` rationales on core subsystems, and cognitive complexity ceilings ($\le 15$) enforced.
* **Agentic OS & Native Skills:** 14 unified skills operational in `.agents/skills/` (`epistemic-soundness-audit`, `matrix-tdd-refactor`, `validate-full-stack`, `verify-matrix-trace-parity`, `auto-reconcile-matrix-drift`, `analyze-zarr`, `run-benchmarks`, `validate-okf`, `visualize-okf`, `delegation-protocol`, `doc-synchronization-pipeline`, `ecs-refactor-pipeline`, `implement-scientific-model`, `vertical-slice-development`), with legacy `.agents/workflows/` and deprecated Jules triage retired.
* **Governance & Experiment Script Architecture:** Domain-partitioned layout in `scripts/` (`governance/`, `simulation/`, `experiments/`, `ci/`, `maintenance/`) with OKF v0.2 Option A/B validation, forwarder compatibility shims, and integrated SIMPAT manuscript workflows (`just paper-*`).
* **Headless CLI & FastMCP Diagnostic Server:** Typer CLI supports `batch` / `batch-inspect` Monte Carlo workflows alongside the modular FastMCP server (`src/phids/mcp/`).
* **Modernized Technical Documentation & Dual Interactive Hub:** Modernized Zensical documentation (`docs/interactive_hub.md`) embedding both the 26-node interactive system architecture visualizer (`docs/architecture_visualizer.html`) and the verified OKF v0.2 knowledge graph (`docs/viz.html`), alongside Mermaid.js viewport controls.
* **Documentation Architecture:** Fully partitioned Zensical documentation structure (`docs/scientific_model/part_1_*` through `part_5_*`, `computations/`, `future_prospects/`).
* **OKF Metadata Compliance:** 100% compliance across all docs with Open Knowledge Format (OKF v0.2) frontmatter, graph integrity, and bilateral resource linking.
* **Scientific Simulation Core (Stage 1):** Complete and formally attested with 11/11 Data-Flow Matrices matching live Pytest traces (`test_causal_data_flow_matrices.py`).
* **Empirical Trait Database (Stage 2A):** Operational embedded DuckDB (`bio_database.duckdb`) and JSON catalog with Mode A matching and Mode B trait bounding.
* **Design Space Exploration (Stage 2B/2C):** Active prototype implementing MINLP genotypes (`dse_genotype.py`), analytical pruners (`dse_pruning.py`), and headless simulation evaluation (`dse_optimizer.py`).
* **Forest-Scale Scaling (Stage 4):** Power-of-2 bitwise toroidal coordinate wrapping (`x & (W-1)`) and $O(1)$ trophic anchoring (`anchoring.py`) implemented and tested. Multi-scale temporal decimation active in `SimulationLoop`.
* **Pre-v1.0 Open Milestones (Stage 3):** Soil Seed Bank (3A), Soil Detritus Recycling (3B), and Weather Profiles (3C) are fully specified in `docs/development_guide/roadmap.md` awaiting implementation prior to formal v1.0.
* **Verification Gates:** 9-gate continuous attestation seal (`.agents/verifiers/attest_seal.py`), automated pre-commit hooks, and continuous 1:1 table-to-trace parity verification.
