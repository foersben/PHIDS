# Plant-Herbivore Interaction & Defense Simulator (PHIDS)

PHIDS is a deterministic ecosystem simulator for studying plant–herbivore interaction, chemical signaling, toxin deployment, mycorrhizal relays, and spatial ecological dynamics on a grid.

It is designed for three overlapping audiences:

- **Researchers** who need an inspectable, reproducible plant-defense simulation with explicit
  trigger rules, telemetry, and replay/export surfaces.
- **Users and scenario authors** who want to build, load, run, and inspect ecological scenarios via
  a browser UI or API.
- **Contributors** who need a clear architecture map, engineering invariants, and quality workflow
  before touching performance-sensitive code.

PHIDS combines:

- a data-oriented simulation core built around `SimulationLoop`, `ECSWorld`, and NumPy-backed
  environmental layers,
- a JSON/WebSocket API for control, telemetry, and streaming integration,
- a server-rendered HTMX/Jinja control center for authoring and live inspection.

This `README.md` is the repository landing page. The detailed architecture, interface, scenario,
engine, and contributor guidance lives under `docs/`.

## Why PHIDS exists

PHIDS focuses on deterministic ecological interactions where local encounters can trigger broader
defense behavior:

- herbivore pressure activates plant-owned signals or toxins,
- signals diffuse through the environment and may also relay over mycorrhizal links,
- herbivore movement is driven by flow fields rather than per-agent pathfinding,
- telemetry and replay surfaces make scenario outcomes analyzable after the run.

The result is a simulator that is useful both as an exploratory research tool and as a structured
software platform for ecological systems work.

## Highlights

- deterministic, tick-ordered simulation loop
- ECS-style entity storage with spatial hashing for locality-sensitive interactions
- double-buffered environmental state for predictable read/write semantics
- vectorized NumPy layers and Numba-accelerated hot paths
- trigger-based signaling, toxin activation, and aftereffect handling
- mycorrhizal network links and relay-aware live inspection
- REST, WebSocket, and browser-based operator surfaces
- telemetry export, replay support, and termination tracking

## Python and environment baseline

PHIDS now targets **Python 3.12+**.

This is an intentional project policy change: the repository no longer claims Python 3.11
compatibility, and CI no longer spends time on a Python 3.11 compatibility lane.

Preferred environment manager and command runner:

- `uv`

## Quick start

### 1. Local development install

```bash
uv sync --all-extras --dev
```

### 2. Start the application

```bash
uv run uvicorn phids.api.main:app --reload --app-dir src
```

Open:

- UI: `http://127.0.0.1:8000/`
- OpenAPI docs: `http://127.0.0.1:8000/docs`

### 3. Run a fast focused validation pass

```bash
uv run pytest tests/test_ui_routes.py -q
uv run pytest tests/test_systems_behavior.py tests/test_termination_and_loop.py -q
```

### 4. Run the full local quality gate

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
uv run mkdocs build --strict
```

## Running with containers

For local containerized development:

```bash
docker compose up --build
```

This starts the application with `src/` mounted for live reload.

PHIDS-specific cleanup after local container work:

```bash
docker rm -f phids-local
docker rmi -f phids:test phids:local
docker image prune -f
```

For more on runtime images, binary bundles, and release automation, see
[`docs/development/containers-and-release-automation.md`](docs/development/containers-and-release-automation.md).

## What you can do with PHIDS

### For researchers

- define flora, predator, and substance spaces with bounded deterministic configuration,
- explore trigger-rule combinations for signaling and toxin activation,
- inspect cell-level live state including swarms, signal concentrations, and mycorrhizal links,
- export telemetry and replay artifacts for downstream analysis,
- use curated example scenarios in `examples/` as starting points.

### For users and scenario authors

- build or edit a draft scenario in the HTMX/Jinja UI,
- import/export scenario JSON,
- load a draft into the live simulation only when ready,
- step or run the simulation and inspect dashboard overlays,
- query live or draft cell details through the UI/API.

### For contributors

- work inside the canonical runtime package under `src/phids/`,
- preserve the data-oriented engine architecture,
- use focused tests first and broader quality gates before finishing,
- update documentation when public behavior or workflow policy changes.

## Architectural overview

The active runtime lives in `src/phids/`.

Key anchors:

- `src/phids/engine/loop.py` — ordered simulation phases via `SimulationLoop`
- `src/phids/engine/core/ecs.py` — ECS-style entity and spatial-hash storage
- `src/phids/engine/core/biotope.py` — double-buffered environmental layers
- `src/phids/engine/core/flow_field.py` — Numba-accelerated flow-field generation
- `src/phids/engine/systems/` — lifecycle, interaction, and signaling systems
- `src/phids/api/main.py` — REST, WebSocket, HTML, and live payload assembly
- `src/phids/api/ui_state.py` — `DraftState` and builder-side scenario mutation
- `src/phids/io/replay.py` — replay/state serialization
- `src/phids/telemetry/` — analytics, export, and termination helpers

### Simulation phase order

`SimulationLoop` advances phases in this order:

1. flow field
2. lifecycle
3. interaction
4. signaling
5. telemetry / termination

That ordering matters. UI or API changes that look harmless can still be incorrect if they describe a
state that could not exist at that point in the tick.

## Core engineering invariants

PHIDS is not a free-form object-oriented simulation sandbox. Important repository rules include:

- entities live in `ECSWorld`, not in deep ad-hoc Python object graphs,
- grid/state data belongs in NumPy arrays,
- environmental mutation must respect double buffering,
- species/substance spaces obey the Rule of 16 caps,
- locality-sensitive logic must use the spatial hash instead of O(N²) scans,
- hot-path math belongs in the vectorized / Numba-backed engine core,
- diffusion tails below the signal epsilon threshold are intentionally zeroed.

For the deeper rationale, start with:

- [`AGENTS.md`](AGENTS.md)
- [`docs/architecture.md`](docs/architecture.md)
- [`docs/engine/index.md`](docs/engine/index.md)

## Interfaces

PHIDS intentionally exposes two operator surfaces.

### API surface

- REST endpoints for scenario loading, simulation control, configuration updates, and export
- WebSocket streaming for simulation snapshots and UI-facing lightweight live updates

### Control-center UI

- server-rendered HTMX/Jinja views for draft editing,
- partial refreshes for matrices and species configuration,
- live dashboard inspection with cell-detail tooltips.

Important nuance: the UI is **not** a thin client. Config edits first mutate server-side
`DraftState`; only `POST /api/scenario/load-draft` commits the draft into a live `SimulationLoop`.

Read more in:

- [`docs/interfaces/rest-and-websocket-surfaces.md`](docs/interfaces/rest-and-websocket-surfaces.md)
- [`docs/ui/index.md`](docs/ui/index.md)

## Scenarios and examples

Curated example scenarios live in `examples/`, including:

- `examples/dry_shrubland_cycles.json`
- `examples/meadow_defense.json`
- `examples/mixed_forest_understory.json`
- `examples/root_network_alarm_chain.json`
- `examples/wind_tunnel_orchard.json`

Scenario authoring guidance lives in:

- [`docs/scenarios/index.md`](docs/scenarios/index.md)
- [`docs/scenarios/schema-and-curated-examples.md`](docs/scenarios/schema-and-curated-examples.md)
- [`docs/scenarios/scenario-authoring-and-trigger-semantics.md`](docs/scenarios/scenario-authoring-and-trigger-semantics.md)

## Testing and validation

### Focused checks

```bash
uv run pytest tests/test_ui_routes.py -q
uv run pytest tests/test_systems_behavior.py tests/test_termination_and_loop.py -q
uv run pytest tests/test_flow_field_benchmark.py tests/test_spatial_hash_benchmark.py -q
```

### Requested representative route/system smoke slice

```bash
uv run pytest -o addopts='' tests/test_api_routes.py tests/test_ui_routes.py tests/test_systems_behavior.py tests/test_example_scenarios.py -q
```

### Full repository gate

```bash
./scripts/local_ci.sh all
```

Optional workflow rehearsal:

```bash
./scripts/run_ci_with_act.sh --dryrun
```

## GitHub Actions policy

To reduce unnecessary spend and long-running automation on in-progress branch commits:

- the main CI workflow now runs on **pushes to `main`**, **pull requests targeting `main`**, and manual dispatch,
- it no longer runs on every branch push,
- it therefore does **not** automatically run on `develop`,
- the GHCR image publishing workflow now runs on **pushes to `main`**, **version tags**, and manual dispatch,
- bundled binary publishing remains tag-driven/manual.

This keeps expensive automation focused on review and release boundaries rather than on every commit.

The authoritative workflow documentation lives in:

- [`docs/development/github-actions-and-local-ci.md`](docs/development/github-actions-and-local-ci.md)
- [`docs/development/contribution-workflow-and-quality-gates.md`](docs/development/contribution-workflow-and-quality-gates.md)
- [`docs/development/containers-and-release-automation.md`](docs/development/containers-and-release-automation.md)

## Release and distribution

PHIDS includes:

- a runtime `Dockerfile`,
- `docker-compose.yml` for local containerized development,
- `.github/workflows/docker-publish.yml` for GHCR image publishing on `main` pushes, version tags, and manual runs,
- `.github/workflows/release-binaries.yml` for bundled Linux, Windows, and macOS artifacts.

## Documentation map

If you want the full project picture, start here:

- docs home: [`docs/index.md`](docs/index.md)
- architecture overview: [`docs/architecture/index.md`](docs/architecture/index.md)
- engine docs: [`docs/engine/index.md`](docs/engine/index.md)
- interfaces docs: [`docs/interfaces/index.md`](docs/interfaces/index.md)
- scenarios docs: [`docs/scenarios/index.md`](docs/scenarios/index.md)
- telemetry docs: [`docs/telemetry/index.md`](docs/telemetry/index.md)
- development docs: [`docs/development/index.md`](docs/development/index.md)
- reference docs: [`docs/reference/index.md`](docs/reference/index.md)

Published website:

- GitHub Pages: `https://foersben.github.io/phids/`
- deployment workflow: `.github/workflows/docs-pages.yml` (runs on pushes to `main` and manual dispatch)

Serve the documentation locally with:

```bash
uv run mkdocs serve
```

## Technology stack

- simulation/math: `numpy`, `scipy`, `numba`
- API/runtime: `fastapi`, `uvicorn`, `websockets`
- validation: `pydantic`
- telemetry/data processing: `polars`
- serialization: `msgpack`
- docs: `mkdocs`, `mkdocs-material`, `mkdocstrings`

## Repository shape at a glance

```text
src/phids/              canonical runtime package
tests/                  unit, integration, and benchmark-sensitive test coverage
examples/               curated scenario JSON files
docs/                   MkDocs documentation corpus
scripts/                local CI and workflow rehearsal helpers
packaging/              PyInstaller configuration
```

## Where to go next

- Want to understand the engine? Start at [`docs/engine/index.md`](docs/engine/index.md).
- Want to build or edit scenarios? Start at [`docs/scenarios/index.md`](docs/scenarios/index.md).
- Want the route and WebSocket inventory? Start at
  [`docs/interfaces/rest-and-websocket-surfaces.md`](docs/interfaces/rest-and-websocket-surfaces.md).
- Want contributor workflow and CI expectations? Start at
  [`docs/development/contribution-workflow-and-quality-gates.md`](docs/development/contribution-workflow-and-quality-gates.md).
