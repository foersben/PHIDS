# 🌿 Plant-Herbivore Interaction & Defense Simulator (PHIDS)

<img src="docs/assets/logo.png" align="right" width="200" alt="PHIDS Logo">

PHIDS is a deterministic ecological simulation framework for analyzing how plant populations
accumulate energy, respond to herbivore pressure, activate chemically mediated defenses, and
propagate information across both airborne and mycorrhizal channels. The project integrates a
data-oriented engine core, strict state invariants, and reproducible telemetry surfaces so that
scenario outcomes can be interpreted as traceable computational experiments rather than opaque
animation artifacts.

Current release line: `v0.10.0` (active development branch preparing `v0.11.0`).

[![Python Version](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/downloads/)
[![Build Status](https://github.com/foersben/PHIDS/actions/workflows/ci.yml/badge.svg)](https://github.com/foersben/PHIDS/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/badge/docs-zensical-blue.svg)](https://foersben.github.io/PHIDS/)
[![Checked with mypy](https://img.shields.io/badge/mypy-strict-blue.svg)](https://mypy-lang.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Cognitive Complexity](https://img.shields.io/badge/cognitive%20complexity-%E2%89%A415-blue.svg)](https://github.com/astral-sh/complexipy)
[![Knowledge Format](https://img.shields.io/badge/knowledge-OKF%20v0.2-blue.svg)](docs/development_guide/okf_data_flow_matrices.md)
[![Dual License: EUPL-1.2 / Commercial](https://img.shields.io/badge/License-EUPL--1.2%20%7C%20Commercial-blue.svg)](#-licensing)

*Dual-licensed under EUPL-1.2 (Academic/Open Source) and a Commercial License.*

Live documentation: <https://foersben.github.io/PHIDS/>

---

## 🔬 Scientific scope and audience

PHIDS is an interdisciplinary simulation framework designed to abstract and compute complex system dynamics. It is engineered for five distinct target audiences and application domains:

* **Ecologists & Evolutionary Biologists** who require transparent rule systems and deterministic phase ordering to analyze spatially localized trophic interactions. The framework allows for the precise evaluation of discrete Lotka-Volterra population dynamics and the efficiency of chemically mediated defense strategies (constitutive, induced, and activated) across airborne and mycorrhizal channels.
* **Cybersecurity Researchers & WSN Architects** who utilize biological paradigms as blueprints for technical systems. The simulator functions as a conceptual modeling environment where plants represent sensor nodes and herbivores represent network threats. This enables the design and optimization of distributed, collaborative security schemes, in-network anomaly detection, and energy-efficient load balancing for large-scale static Wireless Sensor Networks (WSNs).
* **Applied Mathematicians & Complex Systems Theorists** who employ the simulator as a computational optimization game to study topological optimization. It provides a deterministic environment to evaluate graph partitioning schemes, spatial resource allocation, and the mathematical abstraction of biological complexity into solvable discrete-event models.
* **Constraint Engineers & System Architects** who focus on strict software architecture and structural perfection. The engine provides a blueprint for building high-performance, predictable systems operating under severe constraints, utilizing a strictly typed Entity-Component-System (ECS), O(1) spatial hashing, Numba JIT acceleration, and the "Rule of 16" to ensure deterministic execution and prevent dynamic memory allocation latency.
* **AI Orchestrators & MLOps Operators** who require headless, programmatic environments for autonomous agent interactions. The natively integrated Model Context Protocol (MCP) server allows external LLMs to read runtime snapshots, query logs, and execute self-evolving experiments, while the Zarr and Polars pipelines ensure memory-decoupled, high-density telemetry exports for batch analytics.

The core biological motifs currently represented include:

### Lotka-Volterra Population Dynamics (Spatially Constrained)

At its foundation, PHIDS models the classic herbivore-plant (predator-prey) relationship described by Lotka-Volterra dynamics, but translates these principles from theoretical, perfectly-mixed continuous populations into a discrete, spatially-aware environment. Herbivores must actively seek out plants to consume caloric energy for survival and reproduction. Plants, in turn, accumulate energy through photosynthesis. Population scaling is driven by this strict, spatially-dependent metabolic accounting, leading to localized booms, crashes, and persistent oscillation patterns.

### Reaction-Diffusion & Chemical Signaling

Rather than assuming instant global communication, PHIDS utilizes continuous reaction-diffusion fields (coupled with semi-Lagrangian advection for local wind effects) to model the spread of biochemical compounds. Plants can synthesize airborne Volatile Organic Compounds (VOCs) to warn neighboring flora of herbivore pressure, or transmit distress signals via underground mycorrhizal networks. The dispersion of these signals is bound by physical diffusion rates, decay coefficients, and environmental factors, ensuring that ecological communication remains localized and delayed.

### Chemotactic Foraging & Trophic Defenses

Herbivores in PHIDS do not possess omniscient knowledge of the map. They forage via chemotaxis - sensing and navigating localized chemical gradients to find caloric rewards while avoiding toxic compounds. Foraging behavior natively incorporates **Charnov's Marginal Value Theorem (MVT)** and **Softmax Stochastic Action Selection** (Stage 1B milestone complete). Swarms continuously re-evaluate local intake rates against landscape potential to make stochastic, biologically plausible decisions about when to abandon a depleting resource patch, controlled by a distinct temperature ($\tau$) parameter. Plants counter grazing pressure by deploying both baseline (constitutive) defenses and reactive (induced) defenses:

* **Morphological Defenses (Passive):** Features like spines (inflicting mechanical damage) or tough lignin (digestibility modifiers that cause caloric attenuation during feeding).
* **Chemical Defenses (Active):** When grazing pressure reaches a threshold, a plant might synthesize a targeted toxin or release an alarm signal, triggering compound chemical-defense cascades across the ecosystem. Or, under high stress, a plant might initiate *resource withdrawal* to mask its apparent nutritional value.

### Structured Scientific Model & Attested Computations

All biological mechanisms are formalized within a comprehensive 5-part Zensical scientific model:

* **[Part 1: Foundations](docs/scientific_model/part_1_foundations/mathematical_framework.md):** Continuous-discrete hybrid mathematical formulation, conservation invariants, and related academic literature.
* **[Part 2: Autotrophic Dynamics](docs/scientific_model/part_2_autotrophic_dynamics/flora_and_symbiosis.md):** Photosynthesis, structural lignification, symbiosis, and rate-limited phloem nutrient translocation.
* **[Part 3: Signaling & Transport](docs/scientific_model/part_3_signaling_and_transport/reaction_diffusion.md):** 2D Gaussian reaction-diffusion PDEs, semi-Lagrangian advection, and chemotactic gradient ascent.
* **[Part 4: Heterotrophic Kinematics](docs/scientific_model/part_4_heterotrophic_kinematics/herbivore_behavior.md):** Optimal foraging (MVT), Softmax temperature parameterization ($\tau$), metabolic starvation, and clonal mitosis bifurcation.
* **[Part 5: Ecosystem Synthesis](docs/scientific_model/part_5_ecosystem_synthesis/ecological_analytics.md):** Lotka-Volterra trophic equilibrium, multi-species stability criteria, and aggregate statistical analytics.
* **[Attested Computations Suite](docs/scientific_model/computations/index.md):** Self-contained, deterministic computational receipts executing canonical simulation traces with bit-exact machine verification.

### Dual-Audience Data-Flow Matrix Protocol

Every temporal state transition in PHIDS is documented as an Open Knowledge Format (OKF v0.2) **Data-Flow Matrix**. To eliminate cognitive barriers while maintaining scientific rigor, each matrix features:

1. **A Conceptual Guide for General Observers:** Uses an intuitive "slow-motion film strip" or "biological ledger" metaphor to explain what physical transitions occur step-by-step in nature.
2. **A Technical Scenario Narrative in Words:** Continuous floating prose detailing the exact biological triggers, multi-tick kinetics, conservation bounds, and branchless SIMD masking operations.
3. **Verified State Transition Table:** Columnar numerical transfer table validated point-by-point against live engine traces to prevent documentation drift.

---

## ⚙️ Runtime architecture & strictness improvements

Following recent massive architectural sweeps (Phases 1-4 & Tier 0 Optimizations), PHIDS is engineered for uncompromised performance, strict data integrity, and determinism.

**What does this mean for non-programmers?**
In complex ecological models, tiny calculation differences (like out-of-order events or microscopic rounding errors) can cause a "butterfly effect" where two identical starting scenarios produce completely different end results. To prevent this, PHIDS acts like a strict mathematical machine. It enforces rigid rules (who calculates what and when) and uses high-performance computing techniques to guarantee that every single simulation run is 100% predictable, reproducible, and extremely fast.

At its core, the system uses a deliberately layered runtime architecture centered on `src/phids/engine/loop.py` (`SimulationLoop`).

### Strict Data Boundaries (Pydantic V2)

The FastAPI ingress boundary is strictly guarded by **Pydantic V2** schemas (`_condition_adapter.validate_python`). Legacy `Any` types and defensive type-coercion shims have been completely eradicated from the codebase. All scenario configurations, species parameters, and recursive chemical-defense tree cascades are comprehensively validated mathematically before data ever reaches the simulation engine. This ensures a mathematically pure state runtime and prevents poisoned payloads from destabilizing long-running batch experiments.

### Engine: ECS, Numba JIT & Deterministic Double-Buffering

Primary state owners:

* `src/phids/engine/core/ecs.py` (`ECSWorld`) - discrete entities and $O(1)$ spatial hash queries.
* `src/phids/engine/core/biotope.py` (`GridEnvironment`) - vectorized field layers with read/write double-buffering.

To ensure exact determinism and reproducibility, the engine executes a strict phase sequence orchestrated by **Deterministic Multi-Scale Modulo-Gating**:

1. flow field (computed every tick)
2. lifecycle (modulo-gated stride: plant growth, stochastic raycasting dispersal for seed drops)
3. interaction (grazing, mitosis)
4. signaling (VOC synthesis)
5. termination assessment
6. double-buffer commit and telemetry flush

Grid updates rely on explicit read/write double-buffering (Phase 6 Buffer Swaps) to prevent race conditions during continuous diffusion processes. The engine employs high-throughput macro optimizations:

* **Toroidal Power-of-2 Bitwise Wrap:** Single-cycle bitwise AND coordinate wrapping (`x & (W-1)`) for power-of-two grids ($1024 \times 1024$) guarantees exact toroidal periodic boundary conditions and high L1/L2 cache-line locality during $5 \times 5$ spatial convolutions.
* **Massive Scale Parallelization (JIT & OpenMP):** Distributes heavy environmental processes (like signal diffusion and flow-field relaxation) across multi-threaded CPU workers, achieving massive throughput scaling on large grid simulations.
* **Processor Stall Prevention (Flush-to-Zero):** In-place truncation of decaying signal tails below `SIGNAL_EPSILON` ($10^{-4}$) prevents hardware-level microcode execution stalls caused by denormal/subnormal floating-point numbers.
* **Active Channel Gating:** Fast-path skipping of inactive chemical or diffusion channels via integer bitmasks ensures CPU cycles are only spent on active biological processes.
* **Constant-Time Dispersal & Trophic Anchoring:** Seed trajectories execute via $O(1)$ stochastic polar raycasting, while swarms co-located with active food patches leverage $O(1)$ trophic anchoring (`_is_swarm_anchored_jit`) to bypass redundant flow-field pathfinding evaluations during feeding.
* **Predictable Ecosystem Scaling (Rule of 16):** Maximum 16 species and substances are strictly pre-allocated at initialization, ensuring deterministic cache utilization and preventing memory latency spikes.

### UI & WebSockets: FastAPI, HTMX & TailwindCSS

The web-based control center is served by **FastAPI**, rendered via server-side templates with **HTMX**, and styled using **Tailwind CSS**. To allow the UI to render massive swarms and grids effortlessly without melting browser DOMs, the WebSocket telemetry streams (`/ws/ui/stream`) utilize strictly **columnar JSON payloads** with cache signatures. This prevents redundant encoding overhead on the server and ensures bounded in-place Chart.js updates on the client.

### Interactive Scenario Workbench & Tiered Flora Configuration

The control center provides dedicated, decoupled workbench views for configuring scenario drafts before compiling them into active Numba JIT simulation arrays:

* **🌿 Flora Species Workbench (`/ui/flora`):** Implements a **Tiered Progressive Disclosure Layout** providing complete access to botanical traits without interface clutter:
  * *Primary Table (Core Essentials):* Configures caloric baseline (`base_energy`), carrying capacity ceiling (`max_energy`), photosynthetic rate (`growth_rate`), senescence floor (`survival_threshold`), woodiness ceiling (`structural_mass_max`), seed drop interval (`reproduction_interval`), parental reproduction deduction (`seed_energy_cost`), maximum dispersal radius (`seed_max_dist`), and semiochemical masking (`camouflage`).
  * *Collapsible Species Drawer:* Expandable in-place drawer exposing granular **Structural Allometry** (`structural_growth_rate`), **Wind Anemochory Aerodynamics** (`seed_min_dist`, `seed_drop_height`, `seed_terminal_velocity`), **Symbiosis & Phloem Kinetics** (`mycorrhizal_tax_per_link`, `translocation_rate`, `camouflage_factor`), and direct cross-view navigation shortcuts.
  * *Decoupled Dual-Proxy Architecture ($E_{\text{current}}$ vs. $M_{\text{structural}}$):* Separates volatile caloric reserves from permanent lignified body mass. A heavily grazed plant loses caloric energy ($E$) but retains physical woodiness ($M$), eliminating the "trampled oak" paradox where mature trees revert to fragile saplings.
* **Canonical Ecosystem Separation of Concerns (Explicit vs. Implicit):**
  * *Marginal Value Theorem (MVT):* Governed on **🐛 Herbivores** (`consumption_rate`, `handling_time`, `energy_upkeep_per_individual`, `softmax_temperature`). Forager departure is an emergent kinetic of grazer appetite and upkeep relative to local caloric density and tissue digestibility.
  * *Collateral Herd Trampling:* Governed on **🐛 Herbivores** (`incidental_mortality_factor`, `incidental_mortality_mode`). Herd crushing interacts branchlessly with flora structural mass ratio ($1 - M_{\text{structural}} / M_{\text{max}}$).
  * *Trophic Edibility Network:* Configured in the bipartite **🍽️ Diet Matrix** ($16 \times 16$).
  * *Physical & Chemical Defenses:* Mechanical thorns ($m_{\text{bite}}$), digestibility discounts ($\mu_{\text{digest}}$), and active trigger rules reside in **🛡️ Morphology & Defense**.

### High-Performance Replay (Zarr & Polars)

Moving away from legacy `msgpack` serialization for high-density outputs, PHIDS now defaults to the **Zarr** storage backend (`src/phids/io/zarr_replay.py`) for replay data and telemetry exports. This enables high-performance, chunked, and memory-decoupled visual slicing of long-running Monte Carlo batch simulations. Analysts can effortlessly load enormous multidimensional datasets into **Polars** or Pandas DataFrames seamlessly without memory exhaustion.

### Agentic Integration: Model Context Protocol (MCP) Server & Diagnostic Observers

PHIDS is natively engineered for autonomous operation by AI agents. A specialized, stdio-based **Model Context Protocol (MCP)** server (`src/phids/mcp_server.py`) allows external LLMs and IDE assistants to inspect runtime state, validate biological invariants, evaluate OKF documentation compliance, and export multi-format artifacts:

* **11 Native MCP Tools:**
  * `runtime_snapshot()`: Reads global simulation metadata, grid dimensions, active species counts, and tick configuration.
  * `inspect_live_simulation()`: Directly inspects running ECS entity populations, energy distributions, and step metrics.
  * `validate_biological_invariants()`: Asserts conservation bounds, non-negative states, and valid coordinate placement.
  * `validate_simulation_config(config_json)`: Validates scenario structures against strict Pydantic V2 schemas prior to execution.
  * `validate_okf_compliance()`: Evaluates Open Knowledge Format (OKF v0.2) frontmatter, path resolution, and doc freshness.
  * `query_diagnostic_logs(limit)`: Retrieves structured diagnostic log events and observer warnings.
  * `query_batch_jobs()`: Queries the batch execution ledger and historical job statuses.
  * `read_batch_summary(job_id)`: Fetches aggregate metrics and survival statistics for a completed batch.
  * `query_telemetry_schema()`: Explores available scalar and tensor metrics in the live telemetry engine.
  * `inspect_telemetry_schema(zarr_store_path)`: Inspects array schemas and chunk layouts of on-disk Zarr replay buffers.
  * `export_telemetry_data(...)`: Headless generation of CSV tables, LaTeX tabular markup, TikZ vector graphics, or PNG charts.
* **3 Native Streamable Resources:**
  * `phids://config/draft.json` (`active_draft_resource`): Real-time server-side draft scenario configuration.
  * `phids://simulation/live.json` (`live_simulation_resource`): Live telemetry status of the active simulation loop.
  * `phids://analysis/drift-report.md` (`analyze_simulation_drift`): Evaluates parameter drift against canonical baselines.

Furthermore, PHIDS introduces an **Agentic Diagnostic Log Writer & Systemic Integrity Observer** (`dse-log-observer`). This lightweight observer tracks scaling drift, structural violations (e.g., spatial physics vs. MILP disconnects), and execution anomalies without acting as an uninterpretable black box. EEDSE optimization pathways are governed by strict **Human-in-the-Loop (HITL) vs. AI-in-the-Loop (AITL) Intervention Gates**, ensuring algorithmic decisions remain interpretable.

### 🧪 Empirical Trait Pipeline (`src/data_pipeline/`)

PHIDS features a dedicated, automated empirical data pipeline (`src/data_pipeline/`) that grounds simulation parameters in peer-reviewed biological datasets:

* **Global Dataset Ingestion:** Extracts botanical and zoological functional traits from LEDA (trait measurements), BIEN (botanical inventories), GIFT (island floras), TRY, and PanTHERIA databases.
* **Dual Licensing Architecture:**
  * *Core Empirical Pipeline (`just etl`):* Processes open-access datasets under CC0 and CC-BY licenses for unrestricted public redistribution.
  * *Extended Academic Pipeline (`just etl-extended`):* Opt-in processing of non-commercial datasets under CC-BY-NC-SA 4.0 terms, strictly guarded by pre-commit import barriers (`NC License Guard`).
* **Archetype Extraction & DuckDB Compilation:** Vectorizes continuous physiological measurements into discrete plant and herbivore archetype vectors stored in DuckDB (`bio_database.duckdb`), directly feeding the parameter calibration framework (`parameter_calibration_strategy.md`).

### 🧬 Evolutionary Encapsulated Multi-Stage Design Space Exploration (EEDSE) & Empirical Database

> [!WARNING]
> **Status: Work In Progress (WIP) / Under Construction**
> The Empirical Bio-Database pipeline and Evolutionary Design Space Exploration (EEDSE) modules are currently under active development and construction. The APIs, database integration pipelines, and optimization UI interfaces described below are in experimental preview status.

To discover stable Lotka-Volterra configurations in complex ecosystems, PHIDS implements the **Evolutionary Encapsulated Multi-Stage Design Space Exploration (EEDSE)** subsystem (`src/phids/analytics/dse_optimizer.py`).

* **Macro Delimitation (Phase 1):** Restricts the infinite search volume to an empirically anchored, requirement-bounded hyper-cube ($\mathcal{X}_{init}$) before optimization begins.
* **Genetic Algorithm Optimization:** Uses the **pymoo** library to execute vectorized multi-objective NSGA-III optimization (with **evosax** available for GPU scaling), evaluating populations on longevity, stability, and spatial dispersion.
* **Analytical Pre-Pruning:** Filters out structurally infeasible genomes (e.g., total caloric deficits, extreme reproduction costs) via `dse_pruning.py` before running simulations, saving CPU cycles.
* **Biotope Database Tuning:** Integrates a curated species database (`bio_database.py`) supporting Mode A (nearest-species matching via Euclidean distance) and Mode B (clamped parameter bounds mutation).
* **Asynchronous WebSocket Telemetry:** Runs evaluations in background worker threads, dispatching Pareto front updates real-time to HTMX UI clients over `/ws/dse/stream` using thread-safe event loop scheduling.

---

## 📊 Batch orchestration and aggregate analytics

The `/api/batch` routes expose an async job runner that orchestrates `SimulationLoop`
instances outside the main thread, targeted at statistical analysis rather than
live-grid rendering. The operational flow is:

1. run `N` seeded trajectories from a validated draft;
2. persist aggregate outputs to `data/batches/{job_id}_summary.json`;
3. inspect completed jobs in a chart/data-grid detail view;
4. export decimated, publication-oriented aggregate artifacts.

The batch detail pane exposes:

* `Charts` tab with mean±sigma trajectory overlays and survival-probability curve;
* `Data Grid` tab with column projection and tick-stride decimation controls;
* explicit `Apply Chart Settings` and `Apply Table Settings` actions for deterministic UI state transitions;
* chart presets (`Balanced overview`, `Collapse risk focus`, `Herbivore pressure focus`, `Survival probability only`) for rapid comparative evaluation;
* export controls for `CSV`, `LaTeX table`, and `TikZ` with metadata overrides (including survival-focused TikZ export when the survival preset is active).

Telemetry retention is intentionally bounded (`MAX_TELEMETRY_TICKS = 10000`) and table previews
show a decimated recent-tail window to keep both backend memory and browser DOM usage stable under
long-running observations.

Previously computed batches can be rehydrated into the in-memory ledger using the
`Load Persisted Batches` button (backed by `POST /api/batch/load-persisted`).

Reference chapter:
[`docs/scientific_model/part_5_ecosystem_synthesis/ecological_analytics.md`](docs/scientific_model/part_5_ecosystem_synthesis/ecological_analytics.md).

---

## 🧪 Scenario model and curated examples

Scenarios encode bounded experimental setups: grid dimensions, species parameterization,
trigger-rule matrices, initial placements, wind conditions, and termination constraints.

Curated examples are provided under `examples/`, including:

* `examples/ecosystem_equilibrium_benchmark_200x200.json` (High-density, multi-species Lotka-Volterra trophic equilibrium)
* `examples/dry_shrubland_cycles.json`
* `examples/meadow_defense.json`
* `examples/mixed_forest_understory.json`
* `examples/root_network_alarm_chain.json`
* `examples/wind_tunnel_orchard.json`

Authoring references:

* [`docs/scenario_guide/index.md`](docs/scenario_guide/index.md)
* [`docs/scenario_guide/curated_examples.md`](docs/scenario_guide/curated_examples.md)
* [`docs/scenario_guide/scenario_authoring.md`](docs/scenario_guide/scenario_authoring.md)

---

## 🚀 Quick start

### 1) Environment setup (Python 3.13+)

Dependency management and environment isolation are strictly handled by Astral's `uv`, and task execution is automated via `just`.

```bash
uv sync --all-groups
# or one-step full bootstrap:
just setup
```

### 2) Start the application

```bash
just run
```

Or via direct `uv` launch:

```bash
uv run phids --reload
```

Equivalent direct ASGI launch remains available when needed:

```bash
uv run uvicorn phids.api.main:app --reload --app-dir src
```

Open:

* UI: `http://127.0.0.1:8000/`
* OpenAPI docs: `http://127.0.0.1:8000/docs`

### 3) Load an example scenario and run

1. Open the UI at `http://127.0.0.1:8000/`.
2. In the control panel, locate the **Import JSON** button in the bottom left corner.
3. Import one of the curated examples (e.g., `examples/dry_shrubland_cycles.json`) to populate the draft state.
4. Click **Start** to begin the ecological simulation.

---

## ✅ Development, Testing & CI behavior

Strict quality gates are enforced across the repository to guarantee physical conservation invariants, branch coverage, numerical parity, and zero runtime memory faults.

For comprehensive documentation of the testing hierarchy, directory structure, custom pytest markers, and Google-style docstring requirements, see [`tests/README.md`](tests/README.md).

### Two-Pass Numba Testing Strategy

The ECS engine relies heavily on Numba JIT compilation. To ensure both logical correctness and memory-safe machine code generation, the testing pipeline employs a strict **Two-Pass Testing Strategy**:

1. **Pass 1: Logic & Branch Coverage (`NUMBA_DISABLE_JIT=1`):** Tests run with JIT compilation disabled. Because compiled machine code bypasses Python VM tracing hooks, disabling JIT exposes all inner branches, boundary clamps, and edge conditions directly to `coverage.py`, enforcing a strict branch coverage floor ($\ge 80\%$, currently **84.65%** overall and **89.0%** diff coverage).
2. **Pass 2: JIT Parity & Latency Verification:** Tests re-run with JIT enabled (`just test-parity` and `just benchmark`). This verifies that compiled LLVM kernels produce bit-exact numerical parity against pure-Python reference implementations within floating-point tolerance ($\text{atol} \le 1\times 10^{-12}$) with zero memory leaks or OpenMP race conditions.

### Scientific Invariant & Physical Proof Suites

Computational simulation logic must mirror physical laws and biological equations to exact floating-point precision. PHIDS maintains specialized test suites for mathematical conservation:

* **Thermodynamic Energy Balance (`just test-scientific`):** Enforces First Law of Thermodynamics compliance ($\Delta E_{\text{herbivore}} + E_{\text{digestive\_loss}} = \Delta E_{\text{plant\_consumed}}$, $\text{rel\_tol} \le 1\times 10^{-6}$), Holling Type II asymptotic saturation bounds ($I(N) \le 1/T_h$), and monotone Hill defense induction curves.
* **PDE Advection Conservation (`just test-scientific`):** Verifies semi-Lagrangian chemical mass conservation across toroidal boundaries ($\nabla \cdot \vec{v} = 0$, $\text{rtol} \le 1\times 10^{-5}$) and asserts chemical concentration non-negativity ($c \ge 0.0$) with tail-zeroing below `SIGNAL_EPSILON` ($1\times 10^{-4}$).
* **Bit-Exact Replay Playback (`just test-replay`):** Asserts that evaluation outcomes serialized tick-by-tick into compressed Zarr matrices can be played back with zero numerical divergence, completely bypassing engine simulation logic.
* **Mutation Testing (`just mutate`):** Validates test-suite fault-detection power via Mutmut by injecting mutations into core movement and interaction kernels.
* **Property-Based Testing (Hypothesis):** Aggressively stress-tests mathematical invariants, half-life degradation rates, and toroidal coordinate wrapping ($x \ \& \ (W - 1) \equiv x \pmod{W}$) across thousands of pseudo-random parameter combinations.

### Causal Data-Flow Matrix Parity Testing (Rule 05)

Every multi-tick behavioral cascade (foraging, signaling, phloem translocation, starvation mortality) is formally governed by an Open Knowledge Format (OKF v0.2) Data-Flow Matrix specification. The test suite (`tests/integration/scientific_invariants/test_causal_data_flow_matrices.py`) and pre-commit verification script (`scripts/verify_matrix_trace_parity.py --all`) assert exact 1:1 point-by-point numerical parity between documented Markdown matrix tables and runtime simulation traces.

### Cognitive Complexity Budget ($\le 15$)

All production and test functions are bound by a strict cognitive complexity budget ($\le 15$) enforced via Complexipy (`just complexity`). Deeply nested branching logic must be refactored into atomic, single-responsibility helper functions or branchless SIMD array masks.

### Automation Tooling & `Justfile` Recipes

PHIDS provides a comprehensive task runner configured in `Justfile`, backed by 15 automation and validation scripts detailed in [`scripts/README.md`](scripts/README.md).

#### Setup & Environment

* `just setup` (or `just install`): Bootstrap dependencies (`uv sync --all-groups`), install git hooks, register recommended VS Code extensions, and execute initial empirical DuckDB ETL.
* `just install-extensions`: Install recommended editor extensions declared in `.vscode/extensions.json`.

#### Quality & Static Analysis

* `just lint`: Run Ruff linter (`--fix`), Ruff formatter, and strict Mypy type validation across `src/phids/`.
* `just format`: Format all Python codebases using Ruff.
* `just check`: Execute pre-commit quality gates across all staged and repository files.
* `just complexity` (or `just complexity-local`): Run repository-wide cognitive complexity audits with Complexipy.

#### Test Execution

* `just test`: Run the standard Pytest suite across all test packages with benchmarks enabled.
* `just test-scientific`: Run biological and physical invariant tests (`-m scientific_invariant`) with `--no-cov`.
* `just test-parity`: Run Numba JIT vs. pure-Python numerical equivalence tests (`-m jit_parity`).
* `just test-replay`: Run bit-exact Zarr replay round-trip tests (`tests/e2e/replay_and_io/`).
* `just mutate`: Run mutation testing with Mutmut across core simulation kernels.
* `just ci-test`: Execute local CI test orchestration script (`./scripts/local_ci.sh tests`).

#### Causal Data-Flow Matrices & OKF Governance

* `just test-matrix`: Execute the causal Data-Flow Matrix integration test suite.
* `just audit-matrix`: Audit OKF Data-Flow Matrix coverage and bilateral resource links across `docs/scientific_model/`.
* `just verify-matrix`: Assert 1:1 table-to-trace parity against live simulation runs (`scripts/verify_matrix_trace_parity.py --all`).
* `just validate-okf`: Validate OKF v0.2 frontmatter schemas, relative path links, and timestamp freshness.
* `just visualize-okf`: Generate the interactive Cytoscape.js knowledge graph (`docs/viz.html`).

#### Simulation Runtime & Documentation

* `just run`: Launch the PHIDS FastAPI simulation server with auto-reload (`uv run phids --reload`).
* `just docs`: Strictly build static Zensical documentation (`uv run zensical build`).
* `just serve`: Build and serve live interactive Zensical documentation on `localhost:9000`.

#### Benchmarking & Performance

* `just benchmark`: Execute latency micro-benchmarks with Numba JIT enabled (`pytest-benchmark`).
* `just bench-compare <ref1> <ref2> <scenario>`: Compare simulation performance between two git branches or scenario blueprints.
* `just bench-compare-jit <ref1> <ref2> <scenario>`: Run comparative benchmarks isolated to compiled JIT execution phases.

#### Empirical Trait Data Pipeline

* `just etl`: Run the core open-access empirical trait pipeline (LEDA, BIEN, GIFT).
* `just etl-refresh`: Force re-download and rebuild core DuckDB trait database.
* `just etl-extended`: Run the extended academic pipeline incorporating TRY and PanTHERIA (requires NC agreement).
* `just etl-extended-refresh`: Force re-download and rebuild extended academic datasets.
* `just etl-publish-core`: Publish core CC0/CC-BY trait artifacts to Hugging Face.
* `just etl-publish-extended`: Publish extended CC-BY-NC-SA trait artifacts to Hugging Face.

#### Local CI & Containerized GitHub Actions (`act`)

* `just act-ci`: Execute the full GitHub Actions `quality-gate` workflow locally via `nektos/act`.
* `just act-docker`: Test container build workflow locally via `act`.
* `just act-release`: Simulate multi-arch release builds locally using act event payloads.
* `just act-profiling`: Run architectural profiling workflow locally via `act`.
* `just act-complexity`: Run CI cognitive complexity gate workflow locally via `act`.

#### Maintenance & Hygiene

* `just clean`: Remove all build artifacts, cache directories (`__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`), and coverage data.
* `just clean-act`: Prune dangling Docker containers and networks labeled by `nektos/act`.
* `just docker-clean`: Remove local PHIDS container images and prune system caches.

#### Fast Local CI Script & Hook-Only Verification

```bash
# Full local CI pass covering linting, two-pass tests, and strict docs build
./scripts/local_ci.sh all

# Hook-only verification across all repository files
uv run pre-commit run --all-files
uv run pre-commit run --all-files --hook-stage pre-push
```

GitHub Actions policy summary:

* CI quality gates (`.github/workflows/ci.yml`) run automatically on pushes and PRs targeting `main` and `develop`.
* Documentation site deployment to GitHub Pages triggers automatically on pushes to `main`.
* Container images, DuckDB bio-databases, and desktop binary releases publish automatically on semantic tag boundaries (`v*`).

References:

* [`tests/README.md`](tests/README.md)
* [`scripts/README.md`](scripts/README.md)
* [`docs/development_guide/contribution_workflow.md`](docs/development_guide/contribution_workflow.md)

---

## 🐳 Containerized execution

For local containerized development:

```bash
docker compose up --build
```

The compose workflow mounts `src/` for iterative development. Optional cleanup:

```bash
docker rm -f phids-local
docker rmi -f phids:test phids:local
docker image prune -f
```

Release and packaging policy:
[`docs/development_guide/contribution_workflow.md`](docs/development_guide/contribution_workflow.md)

---

## 📦 Release and distribution surfaces

The repository includes automated GitHub Actions workflows:

* `Dockerfile` and `docker-compose.yml` for local container workflows
* `.github/workflows/ci.yml` for quality gates, two-pass Numba testing, and GitHub Pages deployment
* `.github/workflows/docker-publish.yml` for multi-arch GHCR image publication
* `.github/workflows/etl-publish.yml` for empirical DuckDB bio-database release artifact publication
* `.github/workflows/release-binaries.yml` for bundled standalone Linux/Windows/macOS PyInstaller desktop artifacts

### Release runbook (main + tag)

The canonical automated release flow is:

1. merge `develop` into `main` through a reviewed PR,
2. push a semantic tag from `main` (for example `v0.4.0`),
3. allow GitHub Actions to publish all release artifacts.

Expected automation outcomes:

* `Docs Pages` workflow publishes updated documentation to GitHub Pages,
* `Build and Publish Release Binaries` workflow attaches OS-specific bundles to the GitHub release,
* `Build and Publish Docker Image` workflow publishes multi-arch GHCR images for the release tag.

---

## 📚 Documentation map

The documentation is organized into clear domain areas with Open Knowledge Format (OKF) frontmatter headers. You can read the raw Markdown source in the repository or explore the live, rendered site hosted via GitHub Pages:

* **Published Zensical Site**: <https://foersben.github.io/PHIDS/>
* **Local Interactive Server**: Run `uv run zensical serve` (or `just docs`)

| Domain | Local Repository File | Live Hosted Page | Description |
| --- | --- | --- | --- |
| 🏠 **Docs Home** | [`docs/index.md`](docs/index.md) | [Home](https://foersben.github.io/PHIDS/) | High-level abstract, biological introduction, and core engineering principles. |
| 🔬 **Scientific Model** | [`docs/scientific_model/index.md`](docs/scientific_model/index.md) | [Scientific Model](https://foersben.github.io/PHIDS/scientific_model/) | 5-part mathematical foundations, autotrophic dynamics, reaction-diffusion PDEs, chemotaxis, and ecosystem synthesis. |
| 🔢 **Attested Computations** | [`docs/scientific_model/computations/index.md`](docs/scientific_model/computations/index.md) | [Computations](https://foersben.github.io/PHIDS/scientific_model/computations/) | Empirical computational models, SIMD matrix traces, and runtime verification contracts. |
| ⚙️ **Technical Architecture** | [`docs/technical_architecture/index.md`](docs/technical_architecture/index.md) | [Technical Architecture](https://foersben.github.io/PHIDS/technical_architecture/) | ECS data structures, Numba JIT double-buffering, FastAPI/HTMX UI, and Zarr telemetry. |
| 🧪 **Scenario Guide** | [`docs/scenario_guide/index.md`](docs/scenario_guide/index.md) | [Scenario Guide](https://foersben.github.io/PHIDS/scenario_guide/) | Pydantic V2 scenario schemas, curated blueprints, and WIP DSE optimization workflows. |
| 🛠️ **Development Guide** | [`docs/development_guide/index.md`](docs/development_guide/index.md) | [Development Guide](https://foersben.github.io/PHIDS/development_guide/) | Strategic roadmap, agent ecosystem, contribution workflows, and release runbook. |
| 📐 **Data-Flow Matrices** | [`docs/development_guide/okf_data_flow_matrices.md`](docs/development_guide/okf_data_flow_matrices.md) | [Data-Flow Matrix](https://foersben.github.io/PHIDS/development_guide/okf_data_flow_matrix_architecture/) | OKF Data-Flow Matrix architecture, SIMD transfer tables, and trace testing verification. |
| 🧪 **Test Architecture** | [`tests/README.md`](tests/README.md) | [Tests](https://github.com/foersben/PHIDS/blob/develop/tests/README.md) | Two-pass Numba testing, physical invariant proofs, mutation testing, and coverage governance. |
| ⚙️ **Automation Tooling** | [`scripts/README.md`](scripts/README.md) | [Scripts](https://github.com/foersben/PHIDS/blob/develop/scripts/README.md) | Dossiers for all 15 validation, audit, parity, ETL, and benchmarking scripts. |
| 🌐 **Knowledge Graph** | [`docs/viz.html`](docs/viz.html) | [Knowledge Graph](https://foersben.github.io/PHIDS/viz.html) | Interactive Cytoscape.js visual graph of the OKF documentation and agent ecosystem. |
| 📖 **Reference & API** | [`docs/reference/index.md`](docs/reference/index.md) | [Reference](https://foersben.github.io/PHIDS/reference/) | Module ownership map, glossary/concept index, requirements traceability, and Python API. |

### 🔮 Future Prospects & Strategic Enhancements

* 🌿 **[Biological Abstractions & Grid Mechanics](docs/scientific_model/future_prospects/biological_abstractions.md)** ([Live](https://foersben.github.io/PHIDS/scientific_model/future_prospects/biological_abstractions_and_grid_mechanics/)): Decoupled dual-proxy metabolic framework, structural mass accumulation, and incidental seedling mortality.
* 🧮 **[Parameter Calibration Strategy](docs/scientific_model/future_prospects/parameter_calibration_strategy.md)** ([Live](https://foersben.github.io/PHIDS/scientific_model/future_prospects/parameter_calibration_strategy/)): Non-dimensionalization, Buckingham $\Pi$-groups, log-normal hyper-cubes, and Kleiber-Arrhenius thermodynamic scaling.
* 🌐 **[Spatiotemporal Scaling Architecture](docs/scientific_model/future_prospects/spatiotemporal_scaling.md)** ([Live](https://foersben.github.io/PHIDS/scientific_model/future_prospects/spatiotemporal_scaling_architecture/)): Dimensional anchoring ($\Delta L = 1\text{m}$, $\Delta \tau = 1\text{hr}$), multi-scale temporal loop decimation (fast, medium, slow), and forest-scale biome scaling.
* ⚡ **[GPU CUDA Acceleration Engine](docs/technical_architecture/future_prospects/gpu_cuda_acceleration.md)** ([Live](https://foersben.github.io/PHIDS/technical_architecture/future_prospects/gpu_cuda_acceleration/)): Architecture for offloading 2D/3D reaction-diffusion PDE stencil solvers and VOC advection to PyTorch and CUDA C++ GPU kernels.
* 🤖 **[AI Coevolution & Distributed DSE](docs/scenario_guide/future_prospects/ai_coevolution_dse.md)** ([Live](https://foersben.github.io/PHIDS/scenario_guide/future_prospects/ai_coevolution_dse/)): Ray/Tune distributed multi-objective Pareto optimization, AITL vs HITL intervention governance, and reinforcement learning swarm coevolution under EEDSE.
* 📝 **[Agentic Diagnostic Log Writer](docs/scenario_guide/future_prospects/agentic_log_writer.md)** ([Live](https://foersben.github.io/PHIDS/scenario_guide/future_prospects/agentic_log_writer/)): The diagnostic observer agent monitoring systemic integrity and execution anomalies.

---

## 🛠 Technology stack

* simulation/math: `numpy`, `scipy`, `numba`, `pymoo`, `pyscipopt`
* API/runtime: `fastapi`, `uvicorn`, `websockets`
* UI/frontend: `HTMX`, `Tailwind CSS`, `Jinja2`, `Chart.js`
* CLI: `typer`
* validation/modeling boundary: `pydantic` (V2)
* telemetry/data processing: `polars`, `zarr`
* serialization: `zarr` (high-density), `json` (columnar UI streams)
* documentation: `zensical`

---

## 🗂 Repository shape at a glance

```text
src/
├── phids/              canonical runtime simulation package
│   ├── api/            FastAPI routes, Pydantic V2 schemas, HTMX templates, WebSockets
│   ├── engine/         Core determinism domain (ECS + Numba JIT double-buffered grid fields)
│   ├── analytics/      Evolutionary Design Space Exploration (DSE) & empirical database tuning
│   ├── io/             High-performance Zarr replay serialization & scenario ingestion
│   ├── telemetry/      Tick analytics, batch export routines, and Polars handlers
│   ├── shared/         Common constants, rule-of-16 limits, and logging configurations
│   ├── mcp_server.py   Model Context Protocol (MCP) stdio entrypoint for AI agents
│   └── __main__.py     Command-line interface (Typer CLI) entry point
└── data_pipeline/      Empirical trait extraction & normalization pipeline (BIEN, LEDA, GIFT, TRY, PanTHERIA)
.agents/                AI agent ecosystem (OKF AGENTS.md, role definitions, skills & workflows)
data/                   Empirical DuckDB trait database (TRY/PanTHERIA) & batch export ledgers
docs/                   Zensical documentation corpus with OKF frontmatter & Future Prospects
examples/               Curated scenario blueprint JSON files
packaging/              PyInstaller desktop binary packaging configuration
scripts/                Automation & validation scripts (15 scripts, pre-commit & CI gates; see scripts/README.md)
tests/                  Hypothesis invariant tests, two-pass Numba tests, and API integration (see tests/README.md)
```

---

## 📄 Where to go next

* Want to understand phase semantics & Numba JIT rules? Start at [`docs/technical_architecture/engine_execution.md`](docs/technical_architecture/engine_execution.md).
* Want to build or edit scenarios? Start at [`docs/scenario_guide/index.md`](docs/scenario_guide/index.md).
* Want route and WebSocket details? Start at [`docs/technical_architecture/interfaces_and_ui.md`](docs/technical_architecture/interfaces_and_ui.md).
* Want to model behavioral cascades via branchless SIMD transfer tables? Start at [`docs/development_guide/okf_data_flow_matrices.md`](docs/development_guide/okf_data_flow_matrices.md).
* Want to calibrate traits to empirical scales? Start at [`docs/scientific_model/future_prospects/parameter_calibration_strategy.md`](docs/scientific_model/future_prospects/parameter_calibration_strategy.md).
* Want to explore high-density replays & Polars exports? Start at [`docs/technical_architecture/telemetry.md`](docs/technical_architecture/telemetry.md).
* Want to run evolutionary EEDSE searches? Start at [`docs/scenario_guide/work_in_progress/design_space_exploration.md`](docs/scenario_guide/work_in_progress/design_space_exploration.md).
* Want to understand AI integration boundaries? Start at [`docs/scenario_guide/future_prospects/agentic_log_writer.md`](docs/scenario_guide/future_prospects/agentic_log_writer.md).
* Want contributor workflow and CI policy? Start at [`docs/development_guide/contribution_workflow.md`](docs/development_guide/contribution_workflow.md).
* Want to inspect the testing taxonomy, JIT two-pass strategy, and invariant proofs? Start at [`tests/README.md`](tests/README.md).
* Want to inspect all automation scripts and pre-commit gates? Start at [`scripts/README.md`](scripts/README.md).
* Want to explore the interactive knowledge graph? Open [`docs/viz.html`](docs/viz.html) or run `just visualize-okf`.

---

## 📄 Licensing

This project is dual-licensed under the following terms:

* **Open-Source Tier:** Available for academic, scientific, and non-commercial validation under the copyleft terms of the [EUPL-1.2](./LICENSE).
* **Commercial Tier:** For integration into proprietary closed-source systems, SaaS distribution, or monetization outside the scope of the EUPL-1.2, a proprietary commercial license is required.

  Please contact [Benjamin Förster](https://github.com/foersben) to request a commercial license template and pricing.
