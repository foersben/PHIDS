# AGENTS.md – PHIDS AI coding guide

## Big picture
- PHIDS is a deterministic ecosystem simulator with two surfaces: a JSON/WebSocket API and a server-rendered HTMX/Jinja UI. The canonical and only runtime package is `phids.*`, implemented under `src/phids/`.
- The engine core is `SimulationLoop` in `src/phids/engine/loop.py`, which advances phases in this order: flow field → lifecycle → interaction → signaling → telemetry/termination.
- The UI is not a thin client: config edits invoke `DraftService` in `src/phids/api/services/draft_service.py` to mutate server-side `DraftState` in `src/phids/api/ui_state.py`; only `POST /api/scenario/load-draft` commits that draft into a live `SimulationLoop`.

## Non-negotiables
- Keep the data-oriented model: entities live in `ECSWorld` (`src/phids/engine/core/ecs.py`), not as ad-hoc Python object graphs.
- Use NumPy arrays for grid/state data; respect the Rule of 16 caps from `src/phids/shared/constants.py`.
- Preserve double-buffering in `GridEnvironment` (`src/phids/engine/core/biotope.py`): read current layers, write to `_..._write`, then swap.
- Use the spatial hash (`register_position`, `move_entity`, `entities_at`) for locality; never add O(N²) distance scans.
- Hot-path math belongs in `src/phids/engine/core/flow_field.py` with `@numba.njit`; avoid Python objects and dynamic resizing there.
- After diffusion, zero tiny tails using `SIGNAL_EPSILON`; this is a performance invariant, not cosmetic cleanup.

## Edit map
- Schemas and validation: `src/phids/api/schemas.py`.
- UI draft/builder behavior: `src/phids/api/services/draft_service.py`, `src/phids/api/ui_state.py`, and Jinja templates in `src/phids/api/templates/`.
- REST + HTMX endpoints: `src/phids/api/routers/{ui,telemetry,config,simulation,batch}.py`.
- WebSocket streaming managers: `src/phids/api/websockets/manager.py`.
- App composition/bootstrap: `src/phids/api/main.py`.
- Simulation systems: `src/phids/engine/systems/{lifecycle,interaction,signaling}.py`.
- Telemetry/export/termination: `src/phids/telemetry/{analytics,export,conditions}.py`.
- Replay/state serialization: `src/phids/io/{replay,zarr_replay}.py`.

## Workflows that matter
- Environment/dev server:
  `uv sync --all-extras --dev`
  `uv run uvicorn phids.api.main:app --reload --app-dir src`
- Use Python 3.12 or newer locally; `pyproject.toml` now requires `>=3.12` and Ruff targets `py312`.
- Full quality gate:
  `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest && uv run mkdocs build --strict`
- Focused checks:
  `uv run pytest tests/integration/api/test_ui_routes.py -q`
  `uv run pytest tests/integration/systems/test_systems_behavior.py tests/integration/systems/test_termination_and_loop.py -q`
  `uv run pytest tests/benchmarks/test_flow_field_benchmark.py tests/benchmarks/test_spatial_hash_benchmark.py -q`
- Fast local loop (skip benchmark suite):
  `uv run pytest -m 'not benchmark' -q`
- If repo-level `addopts` interfere with targeted debugging, use:
  `uv run pytest -o addopts='' <path-or-node> -q`

## Repo-specific patterns
- Pydantic v2 is the API boundary; validate at ingress, then operate on trusted internal state.
- System modules often use local imports to avoid circular dependencies—follow that pattern instead of “fixing” it globally.
- UI changes usually require touching router handlers and partial templates; `tests/integration/api/test_ui_routes.py` is the fastest regression net.
- Trigger logic is rule-based now: `DraftState.trigger_rules` allows multiple substance rules per `(flora, herbivore)` pair.
- WebSocket surfaces differ intentionally: `/ws/simulation/stream` sends msgpack+zlib bytes, `/ws/ui/stream` sends lightweight JSON for canvas rendering.
- Long replay persistence should use Zarr-backed paths (`src/phids/io/zarr_replay.py`), while bounded in-memory snapshots remain in `src/phids/io/replay.py`.

## Common pitfalls
- Do not confuse draft state with live simulation state.
- When deleting species/substances, compact IDs and clean dependent matrices, trigger rules, and placements.
- If you change diffusion, flow-field logic, or spatial hashing, run the benchmark tests, not just unit tests.
- Keep docstrings in Google style; docs are built with MkDocs + mkdocstrings from `docs/`.
- Do not reintroduce file-local `AsyncClient` factories in API integration tests; use shared fixtures from `tests/conftest.py`.

## Test Docstring Hygiene (Required)
- Do not generate boilerplate pytest docstrings like "Validates the ... invariant".
- For test functions, write concise 1-2 sentence docstrings that describe the actual assertion behavior.
- Remove meaningless `Args:` / `Returns:` sections from ordinary pytest tests unless a complex parameterized input requires explicit clarification.
- Keep the wording human-readable and specific to the endpoint, branch, invariant, or regression being exercised.

## Test Structure Conventions (Required)
- Keep tests aligned to the current domain hierarchy: `tests/unit/*`, `tests/integration/*`, `tests/e2e/*`, `tests/benchmarks/*`.
- Avoid "God tests" that chain many unrelated endpoint calls; split by one state transition/invariant per test.
- Prefer `pytest.mark.parametrize` for branch matrices and coercion helpers so each row reports independently.
- Reuse shared builders/fixtures from `tests/conftest.py` (`config_builder`, `loop_config_builder`, `add_plant`, `add_swarm`) before introducing file-local setup helpers.

## Test Harness Conventions (Required)
- Global state isolation is centralized in `tests/conftest.py::safe_global_reset` (autouse). It resets draft state each test, cancels dangling `api_main._sim_task`, and clears `_sim_loop`/`_sim_substance_names` after each test.
- API integration tests must use `tests/conftest.py::api_client` (`AsyncClient` bound to in-process `ASGITransport`) instead of creating ad-hoc clients.
- In async route tests, either direct fixture calls (`await api_client.get(...)`) or `async with api_client as client` are acceptable; do not mix in `_default_client` helpers.
- HTTP status assertions must include response diagnostics so failures are actionable:
  `assert resp.status_code == 200, resp.text`
  `assert resp.status_code == 400, resp.text`
- Keep benchmark tests explicitly marked with `@pytest.mark.benchmark` in `tests/benchmarks/*` so selection via `-m 'not benchmark'` remains deterministic.
- Prefer small route tests that verify one endpoint contract plus one invariant, especially in `tests/integration/api/test_ui_routes.py`.

## Documentation & Writing Style
When writing docstrings, comments, or markdown documentation, you MUST adhere to a rigorous,
scholarly, and scientific writing style:

1. **Explanatory Depth (Floating Texts):** Do not write terse, one-line summaries. Module and class
   docstrings must contain long, precise, and comprehensive explanatory paragraphs (floating texts)
   that detail the algorithmic mechanics AND the biological rationale.
2. **Academic Tone:** Use a formal, academic tone. Avoid colloquialisms, conversational filler
   (e.g., "basically", "just", "so"), and first-person pronouns.
3. **Domain Precision:** Strictly use the project's scientific and mathematical terminology (e.g.,
   "systemic acquired resistance", "metabolic attrition", "O(1) spatial hash lookups", "mitosis",
   "Gaussian diffusion").
4. **Structure:**
   - Start with a precise declarative sentence.
   - Follow with a detailed paragraph explaining the *why* and *how* of the system.
   - Explicitly state the relationship between the computational logic (e.g., ECS,
     double-buffering) and the biological phenomena it simulates.
5. **Formatting:** Adhere strictly to Google-style docstrings, but expand the top-level description
   into a mini-essay or scholarly abstract.

## Documentation Mode Selection (Required)
- Use a **scientific formal mode** for engine, modeling, simulation, and algorithm pages (for example `docs/engine/*`, `docs/foundations/*`, and analytical sections in `docs/reference/*`). In these pages, extensive floating text, formal terminology, equations, Mermaid state-flow diagrams, and TikZ vector graphics are encouraged when they improve explanatory precision.
- Use an **operational prose mode** for administrative checklists, CI/CD workflows, release processes, contributor onboarding, and project-management notes (for example `docs/development/*`, process-heavy parts of `README.md`, and runbook-like pages). In these pages, avoid equation-heavy formalization and avoid symbolic predicates unless they are strictly necessary for implementation clarity.
- For operational prose mode, prefer clear narrative explanations, compact Mermaid process diagrams, and copyable command snippets. Keep mathematical notation minimal or absent.
- Do not translate routine governance text into pseudo-theorem style. Documentation quality for these pages is defined by practical clarity, reproducibility of steps, and compatibility with GitHub Actions and GitHub Pages build constraints.
