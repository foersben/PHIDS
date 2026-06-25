# PHIDS Documentation

PHIDS is a deterministic, headless simulation engine for plant-herbivore dynamics
built around a data-oriented ECS and grid cellular automata model.

## Highlights

- Deterministic simulation loop with explicit tick control.
- NumPy and SciPy powered continuous-space diffusion layers.
- Numba-accelerated global flow-field gradient generation.
- FastAPI REST and WebSocket interface for runtime control and streaming.
- Polars telemetry aggregation and export.

## Run Docs Locally

```bash
uv sync --all-extras --dev
uv run mkdocs serve
```
