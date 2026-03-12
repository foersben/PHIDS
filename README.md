# PHIDS

PHIDS (Plant-Herbivore Interaction & Defense Simulator) is a deterministic
ecosystem simulation engine based on a data-oriented ECS architecture and
grid cellular automata. It ships both a JSON/WebSocket API and a server-driven
HTMX/Jinja control-center GUI.

## Stack

- Runtime: `numpy`, `scipy`, `numba`
- API/streaming: `fastapi`, `uvicorn`, `websockets`
- Validation: `pydantic`
- Telemetry: `polars`
- State serialization: `msgpack`
- Docs: `mkdocs`, `mkdocs-material`, `mkdocstrings`

## Quickstart (uv)

```bash
uv sync --all-extras --dev
uv run phids --reload
```

Then open the GUI at `http://127.0.0.1:8000/`.

## Containers

PHIDS now ships a project `Dockerfile`, a local `docker-compose.yml`, and GitHub Actions workflows
for publishing both container images and bundled desktop/server binaries.

### Local container run

```bash
docker compose up --build
```

This starts the `phids` service on `http://127.0.0.1:8000/` with `./src` mounted into the
container and `--reload` enabled.

### Local container cleanup

These are the PHIDS-specific cleanup commands used after local container testing:

```bash
docker rm -f phids-local
docker rmi -f phids:test phids:local
docker image prune -f
```

The first two commands target only the container/image names introduced by this repository. The
final prune removes dangling intermediate layers left behind by interrupted local builds.

### Why packages may appear to download twice

You may see dependency downloads more than once for two separate reasons:

1. `uv sync --all-extras --dev` installs into your **local** development environment.
2. `docker build` installs into a **separate container build environment** inside the Docker image.

Within the `Dockerfile` itself, PHIDS intentionally runs two `uv sync` commands:

- `uv sync --frozen --no-dev --no-install-project` builds a cacheable dependency layer.
- `uv sync --frozen --no-dev` installs the project itself after `src/` is copied.

That pattern keeps dependency layers reusable when only application code changes. If a build is
interrupted before the dependency layer is committed, retrying the build will download those wheels
again because the previous layer never finished caching.

GitHub Actions also installs dependencies independently per job and per operating-system runner, so
the Linux, Windows, and macOS release jobs each resolve their own environment.

## Published artifacts

- `.github/workflows/docker-publish.yml` publishes a multi-architecture image to GitHub Container
  Registry (`ghcr.io`).
- `.github/workflows/release-binaries.yml` builds bundled binaries for Linux, Windows, and macOS.

`docker-publish.yml` runs on pushes to `main`, on version tags matching `v*.*.*`, and on manual
dispatch. `release-binaries.yml` runs on version tags and on manual dispatch; tagged runs also
attach the generated archives to the corresponding GitHub release.

## Quality Gates

- Lint/format: `uv run ruff check .` and `uv run ruff format --check .`
- Tests + coverage + benchmarks: `uv run pytest`
- Docs build: `uv run mkdocs build --strict`

Additional local hygiene tooling remains available via:

- Pre-commit hooks: `uv run pre-commit run --all-files`
- Type check cleanup target: `uv run mypy`

These broader hooks are useful for incremental cleanup, but the current GitHub Actions workflow is
kept on the repository's green path: Ruff, pytest, compatibility smoke tests, and strict docs.

## Documentation

- Site entry point: `docs/index.md`
- Local docs server: `uv run mkdocs serve`
- Generated Python reference: `docs/reference/api.md`
- Documentation handoff / open TODOs: `docs/development/documentation-status-and-open-work.md`

## CI and Local Rehearsal

- Main GitHub Actions workflow: `.github/workflows/ci.yml`
- Current-interpreter CI parity helper: `./scripts/local_ci.sh`
- Local GitHub Actions rehearsal with `act`: `./scripts/run_ci_with_act.sh`
- `act` runner image mapping: `.actrc`

Typical local rehearsal flow:

```bash
./scripts/local_ci.sh all
./scripts/run_ci_with_act.sh --dryrun
./scripts/run_ci_with_act.sh --job tests-py312
```

The `act` rehearsal path requires a running Docker or Podman daemon. When Podman is installed with
user systemd services, the helper script will try to start `podman.socket` automatically.

## Key Interface Endpoints

### Scenario ingress

- `POST /api/scenario/load`
- `POST /api/scenario/load-draft`
- `GET /api/scenario/export`
- `POST /api/scenario/import`

### Simulation lifecycle

- `POST /api/simulation/start`
- `POST /api/simulation/pause`
- `POST /api/simulation/step`
- `POST /api/simulation/reset`
- `GET /api/simulation/status`
- `PUT /api/simulation/wind`

### Telemetry and streams

- `GET /api/telemetry/export/csv`
- `GET /api/telemetry/export/json`
- `WS /ws/simulation/stream` (msgpack + zlib frames)
- `WS /ws/ui/stream` (lightweight JSON for the control-center canvas)

### UI surfaces

- `GET /`
- `GET /ui/dashboard`
- `GET /ui/biotope`
- `GET /ui/flora`
- `GET /ui/predators`
- `GET /ui/substances`
- `GET /ui/diet-matrix`
- `GET /ui/trigger-rules`
- `GET /ui/placements`

For the fuller route inventory and response semantics, see
[`docs/interfaces/rest-and-websocket-surfaces.md`](docs/interfaces/rest-and-websocket-surfaces.md).
