# 🌿 Plant-Herbivore Interaction & Defense Simulator (PHIDS)

<img src="docs/assets/logo.png" align="right" width="200" alt="PHIDS Logo">

PHIDS is a deterministic ecological simulation framework for analyzing how plant populations
accumulate energy, respond to herbivore pressure, activate chemically mediated defenses, and
propagate information across both airborne and mycorrhizal channels. The project integrates a
data-oriented engine core, strict state invariants, and reproducible telemetry surfaces so that
scenario outcomes can be interpreted as traceable computational experiments rather than opaque
animation artifacts.

Current release line: `v0.7.0`.

[![Python Version](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/downloads/)
[![Build Status](https://github.com/foersben/PHIDS/actions/workflows/ci.yml/badge.svg)](https://github.com/foersben/PHIDS/actions)
[![Coverage Status](https://coveralls.io/repos/github/foersben/PHIDS/badge.svg)](https://coveralls.io/github/foersben/PHIDS)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

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

Herbivores in PHIDS do not possess omniscient knowledge of the map. They forage via chemotaxis–sensing and navigating localized chemical gradients to find caloric rewards while avoiding toxic compounds. Plants can counter this by deploying both baseline (constitutive) defenses and reactive (induced) defenses:

* **Morphological Defenses (Passive):** Features like spines (inflicting mechanical damage) or tough lignin (digestibility modifiers that cause caloric attenuation during feeding).
* **Chemical Defenses (Active):** When grazing pressure reaches a threshold, a plant might synthesize a targeted toxin or release an alarm signal, triggering compound chemical-defense cascades across the ecosystem. Or, under high stress, a plant might initiate *resource withdrawal* to mask its apparent nutritional value.

---

## ⚙️ Runtime architecture & strictness improvements (Phase 4)

Following recent massive architectural sweeps (Phases 1-4), PHIDS is engineered for uncompromised performance, strict data integrity, and determinism. It uses a deliberately layered runtime architecture centered on `src/phids/engine/loop.py` (`SimulationLoop`).

### Strict Data Boundaries (Pydantic V2)

The FastAPI ingress boundary is strictly guarded by **Pydantic V2** schemas (`_condition_adapter.validate_python`). Legacy `Any` types and defensive type-coercion shims have been completely eradicated from the codebase. All scenario configurations, species parameters, and recursive chemical-defense tree cascades are comprehensively validated mathematically before data ever reaches the simulation engine. This ensures a mathematically pure state runtime and prevents poisoned payloads from destabilizing long-running batch experiments.

### Engine: ECS, Numba JIT & Deterministic Double-Buffering

Primary state owners:

* `src/phids/engine/core/ecs.py` (`ECSWorld`) – discrete entities and $O(1)$ spatial hash queries.
* `src/phids/engine/core/biotope.py` (`GridEnvironment`) – vectorized field layers with read/write double-buffering.

To ensure exact determinism and reproducibility, the engine executes a strict phase sequence:

1. flow field
2. lifecycle
3. interaction
4. signaling
5. termination assessment
6. double-buffer commit and telemetry flush

Grid updates rely on explicit read/write double-buffering (Phase 6 Buffer Swaps) to prevent race conditions during continuous diffusion processes. Furthermore, the engine employs $O(1)$ fast-path optimizations, such as the **"Anchoring Heuristic"**, which bypasses costly flow-field pathfinding for swarms currently positioned directly on food sources, drastically reducing CPU overhead during grazing events. Finally, the spatial `GridEnvironment` enforces the **Rule of 16** (maximum 16 species/substances) to ensure predictable $L1/L2$ cache utilization and invariant execution times.

### UI & WebSockets: FastAPI, HTMX & TailwindCSS

The web-based control center is served by **FastAPI**, rendered via server-side templates with **HTMX**, and styled using **Tailwind CSS**. To allow the UI to render massive swarms and grids effortlessly without melting browser DOMs, the WebSocket telemetry streams (`/ws/ui/stream`) utilize strictly **columnar JSON payloads** with cache signatures. This prevents redundant encoding overhead on the server and ensures bounded in-place Chart.js updates on the client.

### High-Performance Replay (Zarr & Polars)

Moving away from legacy `msgpack` serialization for high-density outputs, PHIDS now defaults to the **Zarr** storage backend (`src/phids/io/zarr_replay.py`) for replay data and telemetry exports. This enables high-performance, chunked, and memory-decoupled visual slicing of long-running Monte Carlo batch simulations. Analysts can effortlessly load enormous multidimensional datasets into **Polars** or Pandas DataFrames seamlessly without memory exhaustion.

### Agentic Integration: MCP Server Support

PHIDS is natively designed to be operated by AI agents. A specialized, stdio-based **Model Context Protocol (MCP)** server (`src/phids/mcp_server.py`) is included. It allows external LLMs and agents to hook directly into the simulator to safely read the `runtime_snapshot()` (retrieving scenario metadata, grid dimensions, species counts, and tick configuration) and query `recent_logs()`. This enables autonomous scenario tuning, diagnostic debugging, and AI-driven experiment generation without disturbing the HTTP API launcher or breaking the engine's single-writer discipline.

### 🧬 Evolutionary Design Space Exploration (DSE)

To discover stable Lotka-Volterra configurations in complex ecosystems, PHIDS implements an evolutionary **Design Space Exploration (DSE)** subsystem (`src/phids/analytics/dse_optimizer.py`).

* **Genetic Algorithm Optimization:** Uses the **DEAP** library to execute multi-objective NSGA-II optimization, evaluating populations on longevity, stability, and spatial dispersion.
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
[`docs/scientific_model/ecological_analytics.md`](docs/scientific_model/ecological_analytics.md).

---

## 🧪 Scenario model and curated examples

Scenarios encode bounded experimental setups: grid dimensions, species parameterization,
trigger-rule matrices, initial placements, wind conditions, and termination constraints.

Curated examples are provided under `examples/`, including:

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
uv sync --all-extras --dev
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

---

## ✅ Development, Testing & CI behavior

We enforce strict quality gates to guarantee arithmetic invariants, memory safety, and simulation stability.

### Two-Pass Numba Testing Strategy

The ECS engine relies heavily on Numba JIT compilation. To ensure both logical correctness and memory-safe machine code generation, our CI pipeline (`scripts/local_ci.sh`) employs a strict **Two-Pass Testing Strategy**:

1. **Pass 1: Logic & Coverage (`NUMBA_DISABLE_JIT=1`):** Tests are run with JIT explicitly disabled to enforce pure-Python line coverage and validate branch logic without compilation overhead masking interpreter coverage.
2. **Pass 2: Compilation Verification:** Tests are re-run with JIT enabled to verify safe machine-code compilation, confirming parametric invariants and ensuring zero runtime segfaults during fast-math execution.

### Property Hypothesis Testing

To guarantee invariant ecosystem rules (e.g., mass conservation, correct condition tree algebraic evaluation), PHIDS utilizes property-based testing (via the `hypothesis` library). These pilot tests aggressively explore edge cases in the biological mechanics and trophic interaction rules.

### Scripted local CI & `just` commands

Scripted local CI covering linting, the two-pass tests, and docs build:

```bash
./scripts/local_ci.sh all
```

Useful `just` Commands:

* `just test`: Run the full test suite via pytest.
* `just lint`: Automatically fix formatting and run static analysis (Ruff & Mypy).
* `just check`: Run all pre-commit hooks across the codebase.
* `just docs`: Build and serve the Zensical documentation strictly.
* `just clean`: Remove all build artifacts, cache directories, and test coverage files.

Hook-only verification:

```bash
uv run pre-commit run --all-files
uv run pre-commit run --all-files --hook-stage pre-push
```

GitHub Actions policy summary:

* CI runs on pushes to `main`, PRs targeting `main`, and manual dispatch.
* `develop` is intentionally not configured as an automatic CI trigger.
* Container publishing is release-focused (main/tag boundaries).

References:

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

The repository includes:

* `Dockerfile` and `docker-compose.yml` for container workflows
* `.github/workflows/docker-publish.yml` for GHCR publication policy
* `.github/workflows/release-binaries.yml` for bundled Linux/Windows/macOS artifacts

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

Start here for full subsystem detail:

* docs home: [`docs/index.md`](docs/index.md)
* scientific model: [`docs/scientific_model/index.md`](docs/scientific_model/index.md)
* technical architecture: [`docs/technical_architecture/system_architecture.md`](docs/technical_architecture/system_architecture.md)
* scenario guide: [`docs/scenario_guide/index.md`](docs/scenario_guide/index.md)
* development guide: [`docs/development_guide/contribution_workflow.md`](docs/development_guide/contribution_workflow.md)
* reference: [`docs/reference/index.md`](docs/reference/index.md)

Published site: <https://foersben.github.io/PHIDS/>

Serve docs locally:

```bash
uv run zensical serve
```

---

## 🛠 Technology stack

* simulation/math: `numpy`, `scipy`, `numba`, `deap`
* API/runtime: `fastapi`, `uvicorn`, `websockets`
* CLI: `typer`
* validation/modeling boundary: `pydantic` (V2)
* telemetry/data processing: `polars`, `zarr`
* serialization: `zarr` (high-density), `json` (columnar UI streams)
* documentation: `zensical`

---

## 🗂 Repository shape at a glance

```text
src/phids/              canonical runtime package
├── api/                FastAPI routes, Pydantic V2 schemas, HTMX templates, Websockets
├── engine/             The core determinism domain (ECS + Numba Double-Buffered grid fields)
├── analytics/          Evolutionary Design Space Exploration (DSE) and database matching
├── io/                 High-performance Zarr replays and scenario parsing
├── telemetry/          Tick analytics, export routines, and Polars handlers
├── shared/             Common utilities and logging configurations
└── mcp_server.py       Model Context Protocol stdio entrypoint for AI Agents
tests/                  property-based invariant tests, two-pass Numba tests, and API integration
examples/               curated scenario JSON files
docs/                   Zensical documentation corpus
scripts/                local CI and workflow rehearsal helpers
packaging/              PyInstaller configuration
```

---

## 📄 Where to go next

* Want to understand phase semantics? Start at [`docs/technical_architecture/engine_execution.md`](docs/technical_architecture/engine_execution.md).
* Want to build or edit scenarios? Start at [`docs/scenario_guide/index.md`](docs/scenario_guide/index.md).
* Want route and WebSocket details? Start at
  [`docs/technical_architecture/interfaces_and_ui.md`](docs/technical_architecture/interfaces_and_ui.md).
* Want contributor workflow and CI policy? Start at
  [`docs/development_guide/contribution_workflow.md`](docs/development_guide/contribution_workflow.md).

---

## 📄 License

MIT. See [`LICENSE`](LICENSE).
