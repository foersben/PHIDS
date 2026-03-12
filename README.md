# PHIDS

PHIDS (Plant-Herbivore Interaction & Defense Simulator) is a deterministic ecosystem simulator for
studying plant–herbivore interaction, chemical signaling, spatial spread, and emergent defensive
behavior on a grid.

It combines:

- a data-oriented simulation core built around `SimulationLoop`, `ECSWorld`, and vectorized NumPy
  layers,
- a JSON/WebSocket API for programmatic integration and streaming,
- a server-rendered HTMX/Jinja control center for interactive scenario authoring and live
  inspection.

This `README.md` is the project landing page. The detailed architecture, interface, scenario, and
development guidance lives under `docs/`.

## Highlights

- deterministic tick-ordered simulation
- ECS-based entity storage with spatial hashing
- double-buffered environmental layers
- flow-field-driven herbivore navigation
- trigger-based signaling and toxin rules
- telemetry export, replay support, and termination tracking
- both API-first and browser-based operator surfaces

## Quick start

### Local development with `uv`

```bash
uv sync --all-extras --dev
uv run phids --reload
```

Open:

- UI: `http://127.0.0.1:8000/`
- OpenAPI docs: `http://127.0.0.1:8000/docs`

### Run with containers

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

For more on runtime images, release bundles, and cleanup of local rehearsal artifacts, see
[`docs/development/containers-and-release-automation.md`](docs/development/containers-and-release-automation.md).

## Project shape

The active runtime lives in `src/phids/`.

Important anchors:

- `src/phids/engine/loop.py` — ordered simulation phases via `SimulationLoop`
- `src/phids/engine/core/ecs.py` — entity and spatial-hash storage via `ECSWorld`
- `src/phids/engine/core/biotope.py` — double-buffered environmental layers
- `src/phids/api/main.py` — REST, WebSocket, and HTML surfaces
- `src/phids/api/ui_state.py` — `DraftState` and scenario-builder state
- `src/phids/io/replay.py` — replay/state serialization
- `src/phids/telemetry/` — analytics, export, and termination utilities

## Interfaces

PHIDS intentionally exposes two operator surfaces:

- **API surface** — REST + WebSocket endpoints for scenario loading, simulation control, telemetry,
  and streamed state snapshots
- **Control-center UI** — server-rendered HTMX/Jinja views for editing draft scenarios and
  interacting with the live simulation

For the complete route inventory and transport semantics, see:

- [`docs/interfaces/rest-and-websocket-surfaces.md`](docs/interfaces/rest-and-websocket-surfaces.md)
- [`docs/ui/index.md`](docs/ui/index.md)

## Scenarios and examples

Curated example scenarios live in `examples/`.

Examples include:

- `examples/meadow_defense.json`
- `examples/root_network_alarm_chain.json`
- `examples/wind_tunnel_orchard.json`

Authoring, schema semantics, trigger rules, and curated scenario guidance are documented in:

- [`docs/scenarios/index.md`](docs/scenarios/index.md)
- [`docs/scenarios/schema-and-curated-examples.md`](docs/scenarios/schema-and-curated-examples.md)
- [`docs/scenarios/scenario-authoring-and-trigger-semantics.md`](docs/scenarios/scenario-authoring-and-trigger-semantics.md)

## Quality and contributor workflow

Main local quality commands:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run mkdocs build --strict
```

CI-parity helper:

```bash
./scripts/local_ci.sh all
```

Optional local GitHub Actions rehearsal:

```bash
./scripts/run_ci_with_act.sh --dryrun
```

The canonical CI and workflow guidance lives in:

- [`docs/development/github-actions-and-local-ci.md`](docs/development/github-actions-and-local-ci.md)
- [`docs/development/contribution-workflow-and-quality-gates.md`](docs/development/contribution-workflow-and-quality-gates.md)

## Release and distribution

PHIDS now includes:

- a runtime `Dockerfile`
- `docker-compose.yml` for local containerized development
- `.github/workflows/docker-publish.yml` for GHCR container publishing
- `.github/workflows/release-binaries.yml` for bundled Linux, Windows, and macOS artifacts

These workflows are documented in:

- [`docs/development/containers-and-release-automation.md`](docs/development/containers-and-release-automation.md)

## Documentation

Start here if you want the full project picture:

- documentation home: [`docs/index.md`](docs/index.md)
- architecture overview: [`docs/architecture/index.md`](docs/architecture/index.md)
- engine docs: [`docs/engine/index.md`](docs/engine/index.md)
- interfaces docs: [`docs/interfaces/index.md`](docs/interfaces/index.md)
- development docs: [`docs/development/index.md`](docs/development/index.md)
- reference docs: [`docs/reference/index.md`](docs/reference/index.md)

Serve the documentation locally with:

```bash
uv run mkdocs serve
```

## Technology stack

- simulation/math: `numpy`, `scipy`, `numba`
- API/runtime: `fastapi`, `uvicorn`, `websockets`
- schemas/validation: `pydantic`
- telemetry/data processing: `polars`
- serialization: `msgpack`
- docs: `mkdocs`, `mkdocs-material`, `mkdocstrings`
