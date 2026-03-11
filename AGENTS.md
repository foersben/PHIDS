# AGENTS.md – PHIDS AI coding guide

## Big picture
- PHIDS is a deterministic ecosystem simulator with two surfaces: a JSON/WebSocket API and a server-rendered HTMX/Jinja UI. The canonical and only runtime package is `phids.*`, implemented under `src/phids/`.
- The engine core is `SimulationLoop` in `src/phids/engine/loop.py`, which advances phases in this order: flow field → lifecycle → interaction → signaling → telemetry/termination.
- The UI is not a thin client: config edits first mutate a server-side `DraftState` in `src/phids/api/ui_state.py`; only `POST /api/scenario/load-draft` commits that draft into a live `SimulationLoop`.

## Non-negotiables
- Keep the data-oriented model: entities live in `ECSWorld` (`src/phids/engine/core/ecs.py`), not as ad-hoc Python object graphs.
- Use NumPy arrays for grid/state data; respect the Rule of 16 caps from `src/phids/shared/constants.py`.
- Preserve double-buffering in `GridEnvironment` (`src/phids/engine/core/biotope.py`): read current layers, write to `_..._write`, then swap.
- Use the spatial hash (`register_position`, `move_entity`, `entities_at`) for locality; never add O(N²) distance scans.
- Hot-path math belongs in `src/phids/engine/core/flow_field.py` with `@numba.njit`; avoid Python objects and dynamic resizing there.
- After diffusion, zero tiny tails using `SIGNAL_EPSILON`; this is a performance invariant, not cosmetic cleanup.

## Edit map
- Schemas and validation: `src/phids/api/schemas.py`.
- UI draft/builder behavior: `src/phids/api/ui_state.py` + Jinja templates in `src/phids/api/templates/`.
- REST + HTMX endpoints: `src/phids/api/main.py`.
- Simulation systems: `src/phids/engine/systems/{lifecycle,interaction,signaling}.py`.
- Telemetry/export/termination: `src/phids/telemetry/{analytics,export,conditions}.py`.
- Replay/state serialization: `src/phids/io/replay.py`.

## Workflows that matter
- Environment/dev server:
  `uv sync --all-extras --dev`
  `uv run uvicorn phids.api.main:app --reload --app-dir src`
- Prefer Python 3.12 locally; `pyproject.toml` allows `>=3.11`, but Ruff targets `py312`.
- Full quality gate:
  `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest && uv run mkdocs build --strict`
- Focused checks:
  `uv run pytest tests/test_ui_routes.py -q`
  `uv run pytest tests/test_systems_behavior.py tests/test_termination_and_loop.py -q`
  `uv run pytest tests/test_flow_field_benchmark.py tests/test_spatial_hash_benchmark.py -q`

## Repo-specific patterns
- Pydantic v2 is the API boundary; validate at ingress, then operate on trusted internal state.
- System modules often use local imports to avoid circular dependencies—follow that pattern instead of “fixing” it globally.
- UI changes usually require touching both route handlers and partial templates; `tests/test_ui_routes.py` is the fastest regression net.
- Trigger logic is rule-based now: `DraftState.trigger_rules` allows multiple substance rules per `(flora, predator)` pair.
- WebSocket surfaces differ intentionally: `/ws/simulation/stream` sends msgpack+zlib bytes, `/ws/ui/stream` sends lightweight JSON for canvas rendering.

## Common pitfalls
- Do not confuse draft state with live simulation state.
- When deleting species/substances, compact IDs and clean dependent matrices, trigger rules, and placements.
- If you change diffusion, flow-field logic, or spatial hashing, run the benchmark tests, not just unit tests.
- Keep docstrings in Google style; docs are built with MkDocs + mkdocstrings from `docs/`.
