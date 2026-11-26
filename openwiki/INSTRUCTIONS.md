# OpenWiki Generation & Update Instructions

These instructions govern automated OpenWiki maintenance across the PHIDS (Plant-Herbivore Interaction & Defence Simulator) repository.

When executing `openwiki code --update`, prioritise the following architectural layers, physical conservation laws, and epistemic invariants:

* Data-Oriented ECS Kernel & Numba PDE Solvers (`src/phids/engine/core/`, `src/phids/engine/loop.py`):
  * Entity-Component-System (`ECSWorld`) storing contiguous C-order Structure-of-Arrays (`float32` / `int32`) buffers with $O(1)$ spatial hashing; object-oriented entities in the hot path are forbidden.
  * Double-buffered `Biotope` layers enforcing read/write immutability across each tick and bitwise-AND toroidal wrapping ($x \;\&\; (W - 1)$) on power-of-two grids.
  * Jacobi chemotactic potential solver (`src/phids/engine/core/flow/solvers.py`) and operator-split semi-Lagrangian wind advection plus $5\times 5$ Gaussian stencil diffusion (`src/phids/engine/core/diffusion.py`) with subnormal Flush-to-Zero truncation ($\varepsilon < 10^{-4}$).
  * Rule of 16 compile-time capacity caps (`src/phids/shared/constants.py`) guaranteeing zero dynamic allocations inside `@njit` kernels.

* Ecological Dynamics & Multi-Scale Coupling (`src/phids/engine/systems/`, `src/phids/engine/spawner.py`):
  * Decoupled dual-proxy plant energy vs structural biomass, phloem source-sink translocation, cardinal-adjacent mycorrhizal root graphs, and anemochorous seed dispersal (`systems/lifecycle/`).
  * Charnov Marginal Value Theorem (MVT) Softmax Boltzmann foraging, saturating Holling Type II grazing, mechanical defense wear, starvation attrition, and clonal mitosis (`systems/interaction/`).
  * Dose-dependent Hill receptor priming ($S(c) = c^n / (K_H^n + c^n)$), damage-triggered VOC emission, systemic toxin synthesis, and olfactory camouflage (`systems/signaling/`).
  * Phase-staggered cohort execution ($S \in \{1, 24, 168\}$) and per-region partitioned `numpy.random.Generator` (PCG64) streams for thread-count-invariant deterministic trajectories.

* Telemetry, Zarr Replay, Batch Execution & EEDSE (`src/phids/io/`, `src/phids/telemetry/`, `src/phids/engine/batch/`, `src/phids/analytics/`, `src/data_pipeline/`):
  * Chunked Zstandard Zarr replay serialization and zero-copy `ReplaySlice` playback (`src/phids/io/zarr_replay.py`) strictly bypassing engine simulation logic (Rule 01).
  * Lazy Polars longitudinal aggregation (`src/phids/telemetry/analytics.py`), death-attribution `TickMetrics`, termination predicates `Z1-Z7`, and TikZ/LaTeX/PNG/CSV exporters (`src/phids/telemetry/export/`).
  * Spawn-pool `BatchOrchestrator` ensembles, DuckDB empirical trait ETL (`TRY`, `PanTHERIA`, `BIEN`, `GIFT`, `LEDA`) with strict non-commercial import isolation (`check_no_extended_imports.py`), and Optuna/NSGA-II EEDSE optimization.

* Async Web Service, UI & FastMCP Surface (`src/phids/api/`, `src/phids/mcp/`):
  * FastAPI ASGI server, modular `APIRouter` composition, mutable `DraftState` vs immutable engine contract conversion (`ui_state/`), HTMX presenters, WebSocket delta streaming, and non-blocking `asyncio.to_thread` offloading.
  * Modular FastMCP server (`src/phids/mcp/`) exposing read-only scenario resources, config validation, and headless telemetry export tools.

* Governance, OKF v0.2 & Quality Invariants (`.agents/`, `scripts/governance/`, `tests/`):
  * Strict `uv run` / `just` toolchain discipline, cryptographic SSH/GPG commit signing (Rule 03), REUSE 3.3 dual-licensing boundaries (`EUPL-1.2 OR LicenseRef-PHIDS-Commercial`), and two-pass Numba branch coverage + JIT parity verification.
  * Data-Flow Matrix table-to-trace parity (Rule 05) audited via `validate_okf.py`, `audit_matrix_coverage.py`, and `verify_matrix_trace_parity.py --all`.
