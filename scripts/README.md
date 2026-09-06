# PHIDS Automation & Tooling Scripts (`scripts/`)

This directory houses the automation, validation, diagnostic, and benchmarking scripts supporting the PHIDS (Plant-Herbivore Integrated Dynamical Simulator) repository.

These scripts maintain the operational invariants of the simulation engine, protect intellectual property and open-source licensing boundaries, enforce Google's **Open Knowledge Format (OKF v0.2)** across all scientific and architectural documentation, and verify mathematical trace parity against runtime kernels.

---

## 1. Directory Overview & Design Philosophy

The scripts in this directory are governed by strict operational principles:

1. **Deterministic Execution:** Validation and parity scripts are fully deterministic. Given the same repository state, they produce identical results across local developer workstations and remote CI runners.
2. **Layer Separation:** Automation scripts interact with simulation schemas (`src/phids/api/schemas/`), input/output serializers (`src/phids/io/`), and trace generators (`tests/integration/scientific_invariants/`), but never introduce runtime dependencies or side effects into the high-performance Numba JIT engine core (`src/phids/engine/`).
3. **Execution Gating:** Scripts are categorized into **Pre-Commit Gates**, **Continuous Integration (CI) Pipelines**, and **Developer Diagnostics / On-Demand Tooling**. Only deterministic, sub-second scripts with zero external dependencies are allowed in the pre-commit hook.
4. **Python Modernization & Typing:** All Python scripts run under `uv run python`, enforce strict Python 3.13+ typing, and adhere to `ruff check` and `ruff format` mandates.

---

## 2. Script Taxonomy & Execution Matrix

| Script | Category | Execution Stage | Runtime | Governing Invariant / Policy |
| :--- | :--- | :--- | :--- | :--- |
| [`validate_okf.py`](#1-validate_okfpy) | Knowledge & Documentation | **Pre-Commit & CI** | < 0.2s | OKF v0.2 Specification (§4-§11) |
| [`audit_matrix_coverage.py`](#2-audit_matrix_coveragepy) | Causal Invariants & Matrices | **Pre-Commit & CI** | < 0.1s | Rule 05-A, Rule 05-C, Rule 05-D |
| [`verify_matrix_trace_parity.py`](#3-verify_matrix_trace_paritypy) | Causal Invariants & Matrices | **Pre-Commit & CI** | ~ 0.5s | Rule 05-A, Rule 05-D (Table-to-Trace Parity) |
| [`check_no_extended_imports.py`](#4-check_no_extended_importspy) | IP & Licensing Security | **Pre-Commit & CI** | < 0.1s | Non-Commercial (NC) License Guard |
| [`visualize_okf.py`](#5-visualize_okfpy) | Knowledge & Visualization | **CI (`deploy-docs`) & On-Demand** | ~ 0.3s | OKF v0.2 Graph Visualization (`docs/viz.html`) |
| [`run_sim_benchmark.py`](#6-run_sim_benchmarkpy) | Performance Benchmarking | **CI & On-Demand** (`just benchmark`) | 10s - 5m | Performance Degradation Guard |
| [`inspect_zarr.py`](#7-inspect_zarrpy) | Telemetry & Storage | **On-Demand** (`.agents/skills/analyze-zarr`) | < 0.2s | Rule 01 (Stochastic Replay Buffers) |
| [`bootstrap.py`](#8-bootstrappy) | Developer Environment | **On-Demand** (`just setup`) | < 0.1s | Local CI / `act` Configuration |
| [`phids_request_trace.py`](#9-phids_request_tracepy) | API Diagnostics | **On-Demand & Smoke Testing** | ~ 0.5s | FastAPI / HTMX Lifecycle Validation |
| [`clean_branches.py`](#10-clean_branchespy) | Git Housekeeping | **On-Demand** | Interactive | Git Repository Hygiene |
| [`find_large_tests.sh`](#11-find_large_testssh) | Code Quality | **On-Demand & Audit** | < 0.1s | Test Modularity (Threshold: 750 LOC) |
| [`local_ci.sh`](#12-local_cish) | Local Orchestration | **On-Demand** | 30s - 2m | Fast Local CI Simulation |
| [`run_ci_with_act.sh`](#13-run_ci_with_actsh) | Local Orchestration | **On-Demand** (`just act-*`) | 1m - 5m | Containerized Local GitHub Actions Rehearsal |
| [`target_cov.sh`](#14-target_covsh) | Code Quality & TDD | **On-Demand** | 1s - 5s | Subsystem Isolated Coverage Verification |

---

## 3. Detailed Script Dossiers

### 1. `validate_okf.py`
* **Purpose:** Validates the entire PHIDS knowledge bundle (`docs/` and `.agents/`) against Google's Open Knowledge Format (OKF v0.2).
* **Key Checks:**
  - Mandatory `type` declaration in YAML frontmatter for all concept documents (§4.1).
  - Lifecycle `status` enumeration (`draft`, `stable`, `deprecated`) (§5.4).
  - Strict ISO 8601 UTC timestamp format (`YYYY-MM-DDTHH:MM:SSZ`) on `stale_after`, `generated.at`, and `verified.at` (§5.5).
  - Actor string conventions (`human:<id>`, `process:<id>`, `<producer>/<version>`) (§5.2).
  - Source resource path existence resolution against document parent, workspace root, or `docs/` (§5.1).
  - Cross-document Markdown link validity and traversal containment (§6.1).
  - **Option A Index Document Rules:** Subdirectory `index.md` files must contain **no YAML frontmatter**, retaining rich narrative text, section headings, and navigation directly in the Markdown body. Bundle root `docs/index.md` allows `okf_version: "0.2"` (§8).
  - **Update Log Document Rules:** Chronological ordering in `log.md` with newest `## YYYY-MM-DD` entries first (§9).
  - **Attested Computation Requirements:** Mandates explicit `runtime` declarations for computational concepts (§10).
  - Audit statistics output: Computes Trust Tiers (Human-Reviewed, Machine-Confirmed, Unverified) and Freshness.
* **CLI Syntax:**
  ```bash
  # Validate all markdown files in docs/ and .agents/
  uv run python scripts/validate_okf.py

  # Validate specific files
  uv run python scripts/validate_okf.py docs/scientific_model/reaction_diffusion.md

  # Automatically migrate date-only strings (YYYY-MM-DD) to ISO 8601 UTC
  uv run python scripts/validate_okf.py --fix
  ```
* **Exit Codes:** `0` = Pristine; `1` = Non-compliance detected.

---

### 2. `audit_matrix_coverage.py`
* **Purpose:** Audits the scientific documentation to enforce that every temporal state-shift and causal cascade described in `docs/scientific_model/` has an associated Data-Flow Matrix specification.
* **Key Checks:**
  - Presence of a `## Data-Flow Matrix Specifications` section.
  - Columnar Markdown table declaring tick-by-tick state vectors ($t_0, t_1, \dots$).
  - **Rule 05-C Bilateral Resource Mapping:** YAML frontmatter `sources:` or `resources:` must explicitly link to both:
    1. The underlying engine implementation in `src/phids/engine/` or API schema in `src/phids/api/`.
    2. The corresponding trace test in `tests/integration/scientific_invariants/test_causal_data_flow_matrices.py`.
* **CLI Syntax:**
  ```bash
  # Audit primary behavioral cascades (morphological defenses, reaction-diffusion, herbivore behavior, flora/symbiosis, population dynamics, biological abstractions)
  uv run python scripts/audit_matrix_coverage.py

  # Strict audit across all markdown files in target directory
  uv run python scripts/audit_matrix_coverage.py --strict --dir docs/scientific_model
  ```
* **Exit Codes:** `0` = 100% coverage; `1` = Missing matrix or missing bilateral resource mapping.

---

### 3. `verify_matrix_trace_parity.py`
* **Purpose:** Enforces Rule 05-A and Rule 05-D by parsing documented Markdown Data-Flow Matrix tables and asserting exact 1:1 point-by-point numerical parity against runtime simulation traces generated by `tests/integration/scientific_invariants/test_causal_data_flow_matrices.py`.
* **Verified Cascades (11 Total):**
  - Primary Scientific Concepts: `morphological_defenses.md`, `reaction_diffusion.md`, `herbivore_behavior.md`, `flora_and_symbiosis.md`, `population_dynamics.md`, `okf_data_flow_matrices.md`.
  - Attested Computations: `defense_signaling_cascade.md`, `phloem_translocation.md`, `herbivore_starvation.md`, `mycorrhizal_propagation.md`, `clonal_mitosis.md`.
* **CLI Syntax:**
  ```bash
  # Verify all 11 registered Data-Flow Matrix specifications
  uv run python scripts/verify_matrix_trace_parity.py --all

  # Verify a single document
  uv run python scripts/verify_matrix_trace_parity.py --doc docs/scientific_model/reaction_diffusion.md
  ```
* **Exit Codes:** `0` = Exact numerical parity (within $10^{-4}$ tolerance); `1` = Divergence detected.

---

### 4. `check_no_extended_imports.py`
* **Purpose:** Protects the commercial licensing integrity of the PHIDS core simulation pipeline.
* **Mechanism:** Scans trusted core pipeline files (`run_all.py`, `export.py`, `writer.py`, `query.py`, `transform.py`, `archetype_extractor.py`) for any imports of Non-Commercial (NC) or ShareAlike (SA) third-party data clients (e.g. BIEN, LEDA, GIFT).
* **CLI Syntax:**
  ```bash
  uv run python scripts/check_no_extended_imports.py
  ```
* **Exit Codes:** `0` = Clean trusted zone; `1` = Contamination detected (blocks git commit).

---

### 5. `visualize_okf.py`
* **Purpose:** Generates a standalone, zero-dependency interactive HTML knowledge graph visualization ([`docs/viz.html`](file:///home/benni/Documents/antigravity_workspace/PHIDS/docs/viz.html)) powered by Cytoscape.js and Marked.js.
* **Features:**
  - Extracts all concepts, documents, and cross-references across `docs/` and `.agents/`.
  - Displays color-coded nodes by document type (Concept, Architecture, Reference, Skill, Role, Rule, Workflow, Attested Computation).
  - Provides real-time text search, type filters, and interactive inspection side-panels rendering Markdown descriptions and links.
  - Automatically embedded into static documentation builds during CI deployment.
* **CLI Syntax:**
  ```bash
  # Generate docs/viz.html
  uv run python scripts/visualize_okf.py

  # Custom output path or root directory
  uv run python scripts/visualize_okf.py --output site/graph.html --root .
  ```
* **Recipe:** `just visualize-okf`

---

### 6. `run_sim_benchmark.py`
* **Purpose:** High-precision performance comparison harness for the simulation loop.
* **Capabilities:**
  - Benchmarks wall-clock ticks per second across JIT modes (`NUMBA_DISABLE_JIT=0` vs. `NUMBA_DISABLE_JIT=1`).
  - Evaluates cross-git branch or cross-commit performance parity by spinning up headless virtual worktrees under `.cache/` without touching the active workspace working branch.
  - Reports min, max, mean, standard deviation, and speedup multipliers.
* **CLI Syntax:**
  ```bash
  # Benchmark a single scenario for 500 ticks
  uv run python scripts/run_sim_benchmark.py scenarios/basic.json 500

  # Compare performance between two git revisions
  uv run python scripts/run_sim_benchmark.py scenarios/basic.json 200 --compare main feature/opt
  ```
* **Recipes:** `just benchmark`, `just bench-compare`, `just bench-compare-jit`

---

### 7. `inspect_zarr.py`
* **Purpose:** Interactive developer and diagnostic tool to inspect serialized Zarr replay stores generated by `src/phids/io/zarr_replay.py`.
* **Capabilities:**
  - Verifies root Zarr group structure and decodes consolidated JSON metadata (`_metadata`).
  - Summarizes recorded frame count, frame index bounds, and chronological timestamps.
  - Inspects array dimensions, data types (`float32`), and chunk layouts for all physical and semiochemical layers.
* **CLI Syntax:**
  ```bash
  uv run python scripts/inspect_zarr.py data/replays/sim_run_01.zarr
  ```

---

### 8. `bootstrap.py`
* **Purpose:** Developer environment initial setup.
* **Capabilities:**
  - Sets up `.github/workflows/secrets.env` from `.github/workflows/secrets.env.example` if absent (enabling local `act` workflow testing).
  - Ensures `.cache/act-artifacts/` and its `.gitkeep` anchor exist.
* **CLI Syntax:**
  ```bash
  uv run python scripts/bootstrap.py
  ```
* **Recipe:** `just setup`

---

### 9. `phids_request_trace.py`
* **Purpose:** Diagnostic utility to trace full HTTP/HTMX API request lifecycles without requiring an interactive web browser or frontend test runner.
* **Capabilities:**
  - Uses `httpx.AsyncClient` with `ASGITransport` to mount `phids.api.main:app` in-process.
  - Exercises root status, scenario JSON loading, simulation initiation, and streaming telemetry endpoints.
* **CLI Syntax:**
  ```bash
  uv run python scripts/phids_request_trace.py
  ```

---

### 10. `clean_branches.py`
* **Purpose:** Interactive Git housekeeping tool to prune stale local branches whose remote upstreams have been deleted on GitHub.
* **Capabilities:**
  - Runs `git fetch --prune`.
  - Excludes protected branches (`main`, `develop`) and the currently checked-out branch.
  - Interactively confirms deletion and handles unmerged branches safely (`-d` vs. `-D`).
* **CLI Syntax:**
  ```bash
  uv run python scripts/clean_branches.py
  ```

---

### 11. `find_large_tests.sh`
* **Purpose:** Scans `tests/` to detect individual test modules or test directories that exceed the designated Line of Code (LOC) threshold (default: 750 LOC).
* **CLI Syntax:**
  ```bash
  ./scripts/find_large_tests.sh
  THRESHOLD=500 ./scripts/find_large_tests.sh
  ```

---

### 12. `local_ci.sh`
* **Purpose:** Local continuous integration simulation script running the quality gates, test passes, and documentation build on the host machine.
* **Capabilities:**
  - `quality`: Runs `ruff check` and `ruff format --check`.
  - `tests`: Runs Pass 1 (Logic & Coverage with `NUMBA_DISABLE_JIT=1`) and Pass 2 (Numba JIT compilation).
  - `docs`: Builds documentation site with `zensical build`.
  - `all`: Runs all three passes in sequence.
* **CLI Syntax:**
  ```bash
  ./scripts/local_ci.sh all
  ./scripts/local_ci.sh quality
  ./scripts/local_ci.sh tests
  ```

---

### 13. `run_ci_with_act.sh`
* **Purpose:** Local runner for GitHub Actions workflows using `nektos/act`.
* **Capabilities:**
  - Automatically configures rootless Podman or Docker daemon sockets.
  - Supports `--dryrun`, specific event triggers (`--event push`), or specific jobs (`--job quality-gate`).
* **CLI Syntax:**
  ```bash
  ./scripts/run_ci_with_act.sh --dryrun
  ./scripts/run_ci_with_act.sh --job quality-gate
  ```
* **Recipes:** `just act-ci`, `just act-profiling`, `just act-complexity`

---

### 14. `target_cov.sh`
* **Purpose:** Fast-feedback developer utility to run targeted pytest executions for a single test file against a specific module, requiring 80% coverage on that module.
* **CLI Syntax:**
  ```bash
  ./scripts/target_cov.sh tests/integration/api/test_api_simulation_and_scenario_routes.py phids.api.routers.simulation
  ```

---

## 4. Pre-Commit vs. CI Workflow Allocation Strategy

The decision to place a script into the local Git pre-commit hook vs. the remote CI pipeline is guided by strict criteria:

### Pre-Commit Gate Mandates
A script is placed in `.pre-commit-config.yaml` if and only if:
1. **Sub-Second Execution:** It executes in less than 1.0 second on modern hardware, preventing developer friction during `git commit`.
2. **Deterministic & Isolated:** It operates purely on files within the workspace without starting daemons, network requests, or container runtimes.
3. **Prevention of Upstream Drift:** A failure indicates a direct invariant violation that must never be allowed into git history (e.g. broken OKF frontmatter, unmapped Data-Flow matrices, numerical table-to-trace drift, or license contamination).

Current Pre-Commit Script Hooks:
- `validate-okf`: `uv run python scripts/validate_okf.py`
- `audit-matrix-coverage`: `uv run python scripts/audit_matrix_coverage.py`
- `verify-matrix-parity`: `uv run python scripts/verify_matrix_trace_parity.py --all`
- `nc-license-guard`: `uv run python scripts/check_no_extended_imports.py`

### CI Workflow Mandates
A script is placed in `.github/workflows/ci.yml` if:
1. **Heavy Computational Burden:** Test execution with full coverage, Numba JIT compilation verification, or benchmarking sweeps take several seconds to minutes.
2. **Deployment Artifact Generation:** Artifact generation tied to release or publication triggers (e.g. running `visualize_okf.py` prior to `zensical build` during GitHub Pages deployment).
3. **Audit & Reporting:** SARIF metric uploads (Complexipy, CodeQL) or architectural profiling (`scc`).

---

## 5. Adding New Automation Scripts

When contributing a new script to `scripts/`:

1. **Include Standard SPDX Headers:**
   ```python
   #!/usr/bin/env python3
   # SPDX-FileCopyrightText: 2026 Benjamin Förster
   # SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial
   ```
2. **Type Everything:** Use `from __future__ import annotations` and annotate all function parameters and returns.
3. **Provide Informative CLI Help:** Implement `argparse` with descriptive summaries and argument help strings.
4. **Document in this README:** Add the script to the taxonomy table and provide a dedicated dossier section detailing its purpose, invariants, usage, and exit codes.
5. **Add Unit Tests:** If the script contains validation logic or parsing algorithms, add corresponding unit tests under `tests/unit/`.
