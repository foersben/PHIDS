# 🌿 Plant-Herbivore Interaction & Defense Simulator (PHIDS)

PHIDS is a deterministic ecological simulation framework for analyzing how plant populations
accumulate energy, respond to herbivore pressure, activate chemically mediated defenses, and
propagate information across both airborne and mycorrhizal channels. The project integrates a
data-oriented engine core, strict state invariants, and reproducible telemetry surfaces so that
scenario outcomes can be interpreted as traceable computational experiments rather than opaque
animation artifacts.

Current release line: `v0.4.0`.

Live documentation: <https://foersben.github.io/PHIDS/>

---

## 🔬 Scientific scope and audience

PHIDS is engineered for three overlapping groups:

- **Research-oriented users** who need transparent rule systems, deterministic phase ordering, and
  exportable telemetry for ecological analysis.
- **Scenario authors and operators** who construct and run simulations through a browser control
  center or API workflows.
- **Contributors** who extend engine behavior under explicit constraints (ECS locality,
  vectorization, bounded dimensions, and reproducible quality gates).

The core biological motifs currently represented include growth and reproduction dynamics,
herbivore pressure, volatile signaling, local toxin defense, mycorrhizal relay, and
population-level metabolic attrition.

---

## ⚙️ Runtime architecture in one page

PHIDS uses a deliberately layered runtime architecture centered on
`src/phids/engine/loop.py` (`SimulationLoop`).

Primary state owners:

- `src/phids/engine/core/ecs.py` (`ECSWorld`) — discrete entities and O(1) spatial hash queries
- `src/phids/engine/core/biotope.py` (`GridEnvironment`) — vectorized field layers with
  read/write buffering for diffusion-sensitive state, including local-wind
  semi-Lagrangian signal advection
- `src/phids/telemetry/analytics.py` and `src/phids/io/replay.py` — per-tick analytical and
  replay outputs

Simulation tick phase order:

1. flow field
2. lifecycle
3. interaction
4. signaling
5. telemetry / termination

This ordering is a semantic contract. Observable state at each phase boundary is defined by this
sequence, not by ad-hoc update interleavings.

Recent engine refinements ensure that heterogeneous wind fields now influence signal transport
locally (rather than through global wind averaging), and lifecycle enforces same-pass viability
cleanup for edge-case mycorrhizal connection costs to preserve causal telemetry attribution.

For the canonical architecture chapter, see
[`docs/architecture/index.md`](docs/architecture/index.md).

---

## 🧱 Non-negotiable modeling and engineering invariants

PHIDS is not implemented as an unconstrained object-graph simulation. The current implementation
follows explicit structural rules:

- **Data-oriented entities**: runtime organisms and substances reside in `ECSWorld` components,
  not deep behavioral object hierarchies.
- **Vectorized fields**: spatial state uses NumPy arrays; native Python multi-dimensional lists
  are not accepted for grid math.
- **Buffered environmental updates**: field-level read/write discipline is enforced where diffusion
  and field aggregation require deterministic visibility.
- **Rule of 16 caps**: flora, herbivores, and substances are bounded to pre-allocated maximum
  dimensions (`src/phids/shared/constants.py`).
- **O(1) locality checks**: interaction and signaling must use spatial hash lookups rather than
  O(N^2) global scans.
- **Hot-path optimization discipline**: flow-field kernels remain Numba-oriented and benchmarked.
- **Subnormal truncation policy**: diffusion tails below `SIGNAL_EPSILON` are zeroed to preserve
  sparse numeric behavior and runtime stability.

Project-level guidance is mirrored in [`AGENTS.md`](AGENTS.md) and
[`docs/engine/index.md`](docs/engine/index.md).

---

## 📡 Interfaces and control surfaces

PHIDS intentionally exposes two complementary interfaces.

### API surface

- REST endpoints for scenario loading, simulation control, environmental updates, and export
- WebSocket streams for simulation-state transport and UI-oriented lightweight frames

See [`docs/interfaces/rest-and-websocket-surfaces.md`](docs/interfaces/rest-and-websocket-surfaces.md).

### Server-rendered UI surface

- HTMX/Jinja control center for scenario drafting, matrix editing, and live diagnostics
- partial update routes for high-frequency operator interactions

Critical boundary: the UI does not mutate live runtime state directly. Configuration first changes
server-side `DraftState` (`src/phids/api/ui_state.py`) through `DraftService`
(`src/phids/api/services/draft_service.py`), and only
`POST /api/scenario/load-draft` commits that draft into a live `SimulationLoop`.

See [`docs/ui/index.md`](docs/ui/index.md).

### Batch evaluation control center

The batch surface (`/ui/batch`) is designed for post-hoc statistical analysis rather than
live-grid rendering. The operational flow is:

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

Telemetry retention is intentionally bounded (`MAX_TELEMETRY_TICKS = 10000`) and table previews
show a decimated recent-tail window to keep both backend memory and browser DOM usage stable under
long-running observations.

Previously computed batches can be rehydrated into the in-memory ledger using the
`Load Persisted Batches` button (backed by `POST /api/batch/load-persisted`).

Reference chapter:
[`docs/ui/batch-runner-and-aggregate-analysis.md`](docs/ui/batch-runner-and-aggregate-analysis.md).

---

## 🧪 Scenario model and curated examples

Scenarios encode bounded experimental setups: grid dimensions, species parameterization,
trigger-rule matrices, initial placements, wind conditions, and termination constraints.

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

### 1) Environment setup (Python 3.12+)

```bash
uv sync --all-extras --dev
```

### 2) Start the application

```bash
uv run phids --reload
```

Equivalent direct ASGI launch remains available when needed:

```bash
uv run uvicorn phids.api.main:app --reload --app-dir src
```

Open:

- UI: `http://127.0.0.1:8000/`
- OpenAPI docs: `http://127.0.0.1:8000/docs`

### 3) Focused validation pass

```bash
uv run pytest tests/integration/api/test_ui_routes.py -q
uv run pytest tests/integration/systems/test_systems_behavior.py tests/integration/systems/test_termination_and_loop.py -q
```

### 4) Full local quality gate

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
uv run mkdocs build --strict
```

### 5) Install repository hook gates

PHIDS uses a staged `pre-commit` regimen so that the commit boundary remains fast enough for
iterative work while the push boundary still rehearses the expensive integrity checks that protect
the engine, the documentation corpus, and the public contributor surface. The `pre-commit` stage
enforces repository hygiene, Ruff linting/formatting, YAML and TOML validity, merge-conflict
detection, secret scanning, and spelling review. The `pre-push` stage escalates to green,
repository-wide executable validation through strict source `mypy`, `pytest`, and
`mkdocs build --strict`, thereby
turning each push into a compact rehearsal of the same scientific reproducibility standards
expected from merge-ready work. The current type boundary checks `src/phids`.

Install both hook types once per clone:

```bash
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
```

Rehearse them manually when needed:

```bash
uv run pre-commit run --all-files
uv run pre-commit run --all-files --hook-stage pre-push
```

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
[`docs/development/containers-and-release-automation.md`](docs/development/containers-and-release-automation.md)

---

## ✅ Testing, benchmarks, and CI behavior

Current verified state (local full-suite run):

- `196 passed`
- repository-wide coverage: `89.65%`
- all currently reported runtime modules in `src/phids/*` are at `>=80%` coverage

Focused checks:

```bash
uv run pytest tests/integration/api/test_ui_routes.py -q
uv run pytest tests/integration/systems/test_systems_behavior.py tests/integration/systems/test_termination_and_loop.py -q
uv run pytest tests/benchmarks/test_flow_field_benchmark.py tests/benchmarks/test_spatial_hash_benchmark.py -q
```

Coverage-uplift regression checks (entrypoint + batch orchestration):

```bash
uv run pytest tests/unit/cli/test_cli_main.py tests/integration/systems/test_batch_runner.py -q
```

If you want to list only modules below 80% after a full run:

```bash
uv run pytest tests/ --no-header 2>&1 | awk '/^src\/phids\// {gsub("%","",$4); if (($4+0) < 80) print $0}'
```

Representative route/system smoke slice:

```bash
uv run pytest -o addopts='' tests/integration/api/test_api_routes.py tests/integration/api/test_ui_routes.py tests/integration/systems/test_systems_behavior.py tests/e2e/scenarios/test_example_scenarios.py -q
```

Focused batch/UI smoke slice:

```bash
uv run pytest tests/integration/api/test_ui_routes.py tests/integration/api/test_api_routes.py -q
```

Scripted local CI:

```bash
./scripts/local_ci.sh all
```

Hook-only verification:

```bash
uv run pre-commit run --all-files
uv run pre-commit run --all-files --hook-stage pre-push
```

Optional workflow rehearsal:

```bash
./scripts/run_ci_with_act.sh --dryrun
```

GitHub Actions policy summary:

- CI runs on pushes to `main`, PRs targeting `main`, and manual dispatch.
- `develop` is intentionally not configured as an automatic CI trigger.
- Container publishing is release-focused (main/tag boundaries).

References:

- [`docs/development/github-actions-and-local-ci.md`](docs/development/github-actions-and-local-ci.md)
- [`docs/development/contribution-workflow-and-quality-gates.md`](docs/development/contribution-workflow-and-quality-gates.md)

---

## 📦 Release and distribution surfaces

The repository includes:

- `Dockerfile` and `docker-compose.yml` for container workflows
- `.github/workflows/docker-publish.yml` for GHCR publication policy
- `.github/workflows/release-binaries.yml` for bundled Linux/Windows/macOS artifacts

### v0.4.0 release highlights

- Engine thermodynamic invariants hardened in toxin lethality, starvation attrition, and reproduction-cost handling.
- API export routes remain async-safe under load via threadpool offloading of heavy serialization paths.
- Telemetry visualization now uses bounded in-place Chart.js updates, preventing long-run client memory growth.
- Batch summaries persist strict JSON payloads (non-finite values normalized) for robust browser parsing.

### Release runbook (main + tag)

The canonical automated release flow is:

1. merge `develop` into `main` through a reviewed PR,
2. push a semantic tag from `main` (for example `v0.4.0`),
3. allow GitHub Actions to publish all release artifacts.

```bash
git checkout main
git pull --ff-only origin main
git tag v0.4.0
git push origin v0.4.0
```

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

Published site: <https://foersben.github.io/PHIDS/>

Serve docs locally:

```bash
uv run mkdocs serve
```

---

## 🛠 Technology stack

- simulation/math: `numpy`, `scipy`, `numba`
- API/runtime: `fastapi`, `uvicorn`, `websockets`
- CLI: `typer`
- validation/modeling boundary: `pydantic`
- telemetry/data processing: `polars`
- serialization: `msgpack`
- documentation: `mkdocs`, `mkdocs-material`, `mkdocstrings`

---

## 🗂 Repository shape at a glance

```text
src/phids/              canonical runtime package
tests/                  unit, integration, and benchmark-sensitive coverage
examples/               curated scenario JSON files
docs/                   MkDocs documentation corpus
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
