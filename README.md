# PHIDS

PHIDS (Plant-Herbivore Interaction & Defense Simulator) is a deterministic,
headless ecosystem simulation engine based on a data-oriented ECS architecture
and grid cellular automata.

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
uv run uvicorn phytodynamics.api.main:app --reload --app-dir src
```

## Quality Gates

- Lint/format: `uv run ruff check .` and `uv run ruff format --check .`
- Type check: `uv run mypy`
- Tests + coverage + benchmarks: `uv run pytest`
- Pre-commit: `uv run pre-commit run --all-files`
- Docs build: `uv run mkdocs build --strict`

## API Endpoints

- `POST /api/scenario/load`
- `POST /api/simulation/start`
- `POST /api/simulation/pause`
- `GET /api/simulation/status`
- `PUT /api/simulation/wind`
- `WS /ws/simulation/stream` (msgpack + zlib frames)
- `GET /api/telemetry/export/csv`
- `GET /api/telemetry/export/json`
