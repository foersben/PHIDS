# 🌿 Plant-Herbivore Interaction & Defense Simulator (PHIDS)

PHIDS is a deterministic ecological simulation framework for analyzing how plant populations accumulate energy, respond to herbivore pressure, activate chemically mediated defenses, and propagate information across both airborne and mycorrhizal channels. The project integrates a data-oriented engine core, strict state invariants, and reproducible telemetry surfaces so that scenario outcomes can be interpreted as traceable computational experiments rather than opaque animation artifacts.

Current release line: `v0.6.0`.

[![Python Version](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/downloads/)
[![Build Status](https://github.com/foersben/PHIDS/actions/workflows/ci.yml/badge.svg)](https://github.com/foersben/PHIDS/actions)
[![Coverage Status](https://coveralls.io/repos/github/foersben/PHIDS/badge.svg)](https://coveralls.io/github/foersben/PHIDS)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Live documentation: [https://foersben.github.io/PHIDS/](https://foersben.github.io/PHIDS/ "null")

---

## 🔬 Scientific scope and audience

PHIDS is engineered for three overlapping groups:

- **Research-oriented users (Ecologists & Biologists)** who need transparent rule systems, deterministic phase ordering, and exportable telemetry for ecological analysis of spatially localized trophic interactions.
- **MLOps & Software Engineers** who care about the high-performance ECS, Numba JIT acceleration, Zarr data exports, and the strict FastAPI/HTMX architecture.
- **Scenario authors and operators** who construct and run simulations through a browser control center, API workflows, or via AI-agent integrations.

The core biological motifs currently represented include:

### Lotka-Volterra Population Dynamics (Spatially Constrained)

At its foundation, PHIDS models the classic predator-prey relationship described by Lotka-Volterra dynamics, but translates these principles from theoretical, perfectly-mixed continuous populations into a discrete, spatially-aware environment. Herbivores must actively seek out plants to consume caloric energy for survival and reproduction. Plants, in turn, accumulate energy through photosynthesis. Population scaling is driven by this strict, spatially-dependent metabolic accounting, leading to localized booms, crashes, and persistent oscillation patterns.

### Reaction-Diffusion & Chemical Signaling

Rather than assuming instant global communication, PHIDS utilizes continuous reaction-diffusion fields (coupled with semi-Lagrangian advection for local wind effects) to model the spread of biochemical compounds. Plants can synthesize airborne Volatile Organic Compounds (VOCs) to warn neighboring flora of herbivore pressure, or transmit distress signals via underground mycorrhizal networks. The dispersion of these signals is bound by physical diffusion rates, decay coefficients, and environmental factors, ensuring that ecological communication remains localized and delayed.

### Chemotactic Foraging & Trophic Defenses

Herbivores in PHIDS do not possess omniscient knowledge of the map. They forage via chemotaxis—sensing and navigating localized chemical gradients to find caloric rewards while avoiding toxic compounds. Plants can counter this by deploying both baseline (constitutive) defenses, like camouflage that masks their caloric signature, and reactive (induced) defenses. When grazing pressure reaches a threshold, a plant might synthesize a targeted toxin or release an alarm signal, triggering compound chemical-defense cascades across the ecosystem.

---

## ⚙️ Runtime Architecture & High-Performance Invariants

Following recent massive architectural sweeps, PHIDS is engineered for uncompromised performance, strict data integrity, and determinism. It uses a deliberately layered runtime architecture centered on `src/phids/engine/loop.py` (`SimulationLoop`).

### Strict Data Boundaries (Pydantic V2)

The FastAPI ingress boundary is strictly guarded by **Pydantic V2** schemas (`_condition_adapter.validate_python`). Legacy `Any` types and defensive type-coercion shims have been completely eradicated from the codebase. All scenario configurations, species parameters, and recursive chemical-defense tree cascades are comprehensively validated mathematically before data ever reaches the simulation engine. This ensures a mathematically pure state runtime and prevents poisoned payloads from destabilizing long-running batch experiments.

### Engine: ECS, Numba JIT & Deterministic Double-Buffering

Primary state owners:

- `src/phids/engine/core/ecs.py` (`ECSWorld`) - discrete entities and  spatial hash queries.
- `src/phids/engine/core/biotope.py` (`GridEnvironment`) - vectorized field layers with read/write double-buffering.

To ensure exact determinism and reproducibility, the engine executes a strict phase sequence:

```mermaid
graph TD
    A[1. Flow Field Computation] --> B[2. Lifecycle & Growth]
    B --> C[3. Trophic Interaction]
    C --> D[4. Chemical Signaling & Diffusion]
    D --> E[5. Termination Assessment]
    E --> F[6. Buffer Commit & Telemetry Flush]
    F -.->|Next Tick| A
```

Grid updates rely on explicit read/write double-buffering (Phase 6 Buffer Swaps) to prevent race conditions during continuous diffusion processes. Furthermore, the engine employs  fast-path optimizations, such as the **"Anchoring Heuristic"**, which bypasses costly flow-field pathfinding for swarms currently positioned directly on food sources, drastically reducing CPU overhead during grazing events. Finally, the spatial `GridEnvironment` enforces the **Rule of 16** (maximum 16 species/substances) to ensure predictable  cache utilization and invariant execution times.

### UI & WebSockets: FastAPI, HTMX & TailwindCSS

The web-based control center is served by **FastAPI**, rendered via server-side templates with **HTMX**, and styled using **Tailwind CSS**. To allow the UI to render massive swarms and grids effortlessly without melting browser DOMs, the WebSocket telemetry streams (`/ws/ui/stream`) utilize strictly **columnar JSON payloads** with cache signatures. This prevents redundant encoding overhead on the server and ensures bounded in-place Chart.js updates on the client.

### High-Performance Replay (Zarr & Polars)

Moving away from legacy `msgpack` serialization for high-density outputs, PHIDS now defaults to the **Zarr** storage backend (`src/phids/io/zarr_replay.py`) for replay data and telemetry exports. This enables high-performance, chunked, and memory-decoupled visual slicing of long-running Monte Carlo batch simulations. Analysts can effortlessly load enormous multidimensional datasets into **Polars** or Pandas DataFrames seamlessly without memory exhaustion.

### Agentic Integration: MCP Server Support

PHIDS is natively designed to be operated by AI agents. A specialized, stdio-based **Model Context Protocol (MCP)** server (`src/phids/mcp_server.py`) is included. It allows external LLMs and agents to hook directly into the simulator to safely read the `runtime_snapshot()` (retrieving scenario metadata, grid dimensions, species counts, and tick configuration) and query `recent_logs()`. This enables autonomous scenario tuning, diagnostic debugging, and AI-driven experiment generation without disturbing the HTTP API launcher or breaking the engine's single-writer discipline.

---

## 📊 Batch orchestration and aggregate analytics

The `/api/batch` routes expose an async job runner that orchestrates `SimulationLoop` instances outside the main thread, targeted at statistical analysis rather than live-grid rendering. The operational flow is:

1. run `N` seeded trajectories from a validated draft;
2. persist aggregate outputs to `data/batches/{job_id}_summary.json`;
3. inspect completed jobs in a chart/data-grid detail view;
4. export decimated, publication-oriented aggregate artifacts.

The batch detail pane exposes:

- `Charts` tab with mean±sigma trajectory overlays and survival-probability curve;
- `Data Grid` tab with column projection and tick-stride decimation controls;
- explicit `Apply Chart Settings` and `Apply Table Settings` actions for deterministic UI state transitions;
- chart presets (`Balanced overview`, `Collapse risk focus`, `Herbivore pressure focus`, `Survival probability only`) for rapid comparative evaluation;
- export controls for `CSV`, `LaTeX table`, and `TikZ` with metadata overrides (including survival-focused TikZ export when the survival preset is active).

Telemetry retention is intentionally bounded (`MAX_TELEMETRY_TICKS = 10000`) and table previews show a decimated recent-tail window to keep both backend memory and browser DOM usage stable under long-running observations.

Previously computed batches can be rehydrated into the in-memory ledger using the `Load Persisted Batches` button (backed by `POST /api/batch/load-persisted`).

Reference chapter:
[`docs/ui/batch-runner-and-aggregate-analysis.md`](docs/ui/batch-runner-and-aggregate-analysis.md)

---

## 🧪 Scenario model and curated examples

Scenarios encode bounded experimental setups: grid dimensions, species parameterization, trigger-rule matrices, initial placements, wind conditions, and termination constraints.

Curated examples are provided under `examples/`, including:

- `examples/dry_shrubland_cycles.json`
- `examples/meadow_defense.json`
- `examples/mixed_forest_understory.json`
- `examples/root_network_alarm_chain.json`
- `examples/wind_tunnel_orchard.json`

Authoring references:

- [`docs/scenarios/index.md`](docs/scenarios/index.md)
- [`docs/scenarios/schema-and-curated-examples.md`](docs/scenarios/schema-and-curated-examples.md)
- [`docs/scenarios/scenario-authoring-and-trigger-semantics.md`](docs/scenarios/scenario-authoring-and-trigger-semantics.md)

---

## 🚀 Quick start

### 1) Environment setup (Python 3.13+)

Dependency management, environment isolation, pre-commit hooks, and development extensions are fully automated.

```sh
just setup
```

### 2) Start the application

```sh
just run
```

Open:

- UI: `http://127.0.0.1:8000/`
- OpenAPI docs: `http://127.0.0.1:8000/docs`

---

## ✅ Development, Testing & CI behavior

We enforce strict quality gates to guarantee arithmetic invariants, memory safety, and simulation stability.

### Two-Pass Numba Testing Strategy

The ECS engine relies heavily on Numba JIT compilation. To ensure both logical correctness and memory-safe machine code generation, our CI pipeline (`scripts/local_ci.sh`) employs a strict **Two-Pass Testing Strategy**:

1. **Pass 1: Logic & Coverage (`NUMBA_DISABLE_JIT=1`):** Tests are run with JIT explicitly disabled to enforce pure-Python line coverage and validate branch logic without compilation overhead masking interpreter coverage.
2. **Pass 2: Compilation Verification:** Tests are re-run with JIT enabled to verify safe machine-code compilation, confirming parametric invariants and ensuring zero runtime segfaults during fast-math execution.

### Property Hypothesis Testing

To guarantee invariant ecosystem rules (e.g., mass conservation, correct condition tree algebraic evaluation), PHIDS utilizes property-based testing (via the `hypothesis` library). These pilot tests aggressively explore edge cases in the biological mechanics and trophic interaction rules.

### 🛠️ Local CI Emulation with nektos/act

To guarantee our pipeline remains green without committing and waiting for remote GitHub runners, PHIDS natively supports running exact GitHub actions locally via [nektos/act](https://github.com/nektos/act "null").

#### Prerequisites

1. **Docker Engine** must be running locally.
2. **`act` CLI** installed on your system path (`brew install act` on macOS).
3. **Secrets Setup**: Create a local mock environment file at `.github/workflows/secrets.env` containing standard testing variables to prevent unauthenticated step failures.

#### Local Workflow Automation Targets

We wrap our containerized pipeline actions within safe, isolated tasks in the `Justfile`:

- `just act-ci`: Evaluates formatting (Ruff), types (Mypy), and the Python suite utilizing the Two-Pass strategy.
- `just act-docker`: Builds Alpine UV base images and simulates dispatch commands.
- `just act-release`: Simulates compiling, staging, and packaging operating-system binaries inside an isolated container.
- `just clean-act`: Garbages dangling containers or local bridge networks created during interrupted runs.

### Scripted local CI & `just` commands

Useful `just` Commands:

- `just setup`: Installs all dependency groups, provisions git hooks, and sets up editor extensions.
- `just test`: Run the full test suite via pytest.
- `just ci-test`: Run test suites through the local CI wrapper pipeline.
- `just ci-local`: Execute the full multi-pass local verification script (linting, two-pass tests, docs compilation).
- `just lint`: Automatically fix formatting and run static analysis (Ruff & Mypy).
- `just check`: Run all pre-commit validation hooks across the repository codebase.
- `just docs`: Compile production-ready static documentation artifacts.
- `just serve`: Build and serve the live Zensical documentation corpus locally at localhost:9000.
- `just clean`: Evict all transient build artifacts, interpreter caches, coverage data, and test environments.

GitHub Actions policy summary:

- CI runs on pushes to `main`, PRs targeting `main`, and manual dispatch.
- `develop` is intentionally not configured as an automatic CI trigger.
- Container publishing is release-focused (main/tag boundaries).

References:

- [`docs/development/github-actions-and-local-ci.md`](docs/development/github-actions-and-local-ci.md "null")
- [`docs/development/contribution-workflow-and-quality-gates.md`](docs/development/contribution-workflow-and-quality-gates.md "null")

---

## 🐳 Containerized execution

For local containerized development:

```sh
docker compose up --build
```

The compose workflow mounts `src/` for iterative development. To reset your environment and clear out old images:

```sh
just docker-clean
```

Release and packaging policy:
[`docs/development/containers-and-release-automation.md`](docs/development/containers-and-release-automation.md)

---

## 📦 Release and distribution surfaces

The repository includes:

- `Dockerfile` and `docker-compose.yml` for container workflows
- `.github/workflows/docker-publish.yml` for GHCR publication policy
- `.github/workflows/release-binaries.yml` for bundled Linux/Windows/macOS artifacts

### Release runbook (main + tag)

The canonical automated release flow is:

1. merge `develop` into `main` through a reviewed PR,
2. push a semantic tag from `main` (for example `v0.4.0`),
3. allow GitHub Actions to publish all release artifacts.

Expected automation outcomes:

- `Docs Pages` workflow publishes updated documentation to GitHub Pages,
- `Build and Publish Release Binaries` workflow attaches OS-specific bundles to the GitHub release,
- `Build and Publish Docker Image` workflow publishes multi-arch GHCR images for the release tag.

---

## 📚 Documentation map

Start here for full subsystem detail:

- docs home: [`docs/index.md`](docs/index.md)
- architecture: [`docs/architecture/index.md`](docs/architecture/index.md)
- engine: [`docs/engine/index.md`](docs/engine/index.md)
- interfaces: [`docs/interfaces/index.md`](docs/interfaces/index.md)
- scenarios: [`docs/scenarios/index.md`](docs/scenarios/index.md)
- telemetry: [`docs/telemetry/index.md`](docs/telemetry/index.md)
- development: [`docs/development/index.md`](docs/development/index.md)
- reference: [`docs/reference/index.md`](docs/reference/index.md)

Published site: [https://foersben.github.io/PHIDS/](https://foersben.github.io/PHIDS/ "null")

Serve docs locally for real-time authoring feedback:

```sh
just serve
```

---

## 🛠 Technology stack

- simulation/math: `numpy`, `scipy`, `numba`
- API/runtime: `fastapi`, `uvicorn`, `websockets`
- CLI: `typer`
- validation/modeling boundary: `pydantic` (V2)
- telemetry/data processing: `polars`, `zarr`
- serialization: `zarr` (high-density), `json` (columnar UI streams)
- documentation: `zensical`

---

## 🗂 Repository shape at a glance

```text
src/phids/              canonical runtime package
├── api/                FastAPI routes, Pydantic V2 schemas, HTMX templates, Websockets
├── engine/             The core determinism domain (ECS + Numba Double-Buffered grid fields)
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

- Want to understand phase semantics? Start at [`docs/engine/index.md`](docs/engine/index.md).
- Want to build or edit scenarios? Start at [`docs/scenarios/index.md`](docs/scenarios/index.md).
- Want route and WebSocket details? Start at
  [`docs/interfaces/rest-and-websocket-surfaces.md`](docs/interfaces/rest-and-websocket-surfaces.md).
- Want contributor workflow and CI policy? Start at
  [`docs/development/contribution-workflow-and-quality-gates.md`](docs/development/contribution-workflow-and-quality-gates.md).

---

## 📄 License

MIT. See [`LICENSE`](LICENSE).
