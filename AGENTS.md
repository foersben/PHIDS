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
- CLI entrypoint and process startup flags: `src/phids/__main__.py` (Typer-based `phids` command).
- Simulation systems: `src/phids/engine/systems/{lifecycle,interaction,signaling}.py`.
- Telemetry/export/termination: `src/phids/telemetry/{analytics,export,conditions}.py`.
- Replay/state serialization: `src/phids/io/{replay,zarr_replay}.py`.

## Workflows that matter
- Environment/dev server:
  `uv sync --all-extras --dev`
  `uv run phids --reload`
  `uv run uvicorn phids.api.main:app --reload --app-dir src` (direct ASGI fallback)
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
- For targeted module-level coverage closure (>=80%) on focused slices, use:
  `scripts/target_cov.zsh <test-path-or-node> <cov-module>`

## Repo-specific patterns
- Pydantic v2 is the API boundary; validate at ingress, then operate on trusted internal state.
- CLI parsing is Typer-driven in `src/phids/__main__.py`; preserve `main(argv)` compatibility for tests and embedding contexts.
- System modules often use local imports to avoid circular dependencies—follow that pattern instead of “fixing” it globally.
- UI changes usually require touching router handlers and partial templates; `tests/integration/api/test_ui_routes.py` is the fastest regression net.
- `build_live_dashboard_payload` now emits columnar `plants`/`swarms` tables (parallel arrays) for `/ws/ui/stream`; do not reintroduce per-entity list-of-dict payload assembly in that hot path.
- Per-tick ECS aggregation is shared via `TickMetrics` (`src/phids/telemetry/tick_metrics.py`), then consumed by both `TelemetryRecorder.record` and `check_termination` to avoid duplicate scans.
- Trigger logic is rule-based now: `DraftState.trigger_rules` allows multiple substance rules per `(flora, herbivore)` pair.
- Trigger semantics are canonical via `activation_condition` across draft/runtime paths; legacy precursor fields (`precursor_signal_id`, `precursor_signal_ids`, `required_signal_ids`) are removed and must not be reintroduced.
- WebSocket surfaces differ intentionally: `/ws/simulation/stream` sends msgpack+zlib bytes, `/ws/ui/stream` sends lightweight JSON for canvas rendering.
- Long replay persistence should use Zarr-backed paths (`src/phids/io/zarr_replay.py`), while bounded in-memory snapshots remain in `src/phids/io/replay.py`.

## Common pitfalls
- Do not confuse draft state with live simulation state.
- When deleting species/substances, compact IDs and clean dependent matrices, trigger rules, and placements.
- When migrating or extending trigger configuration, target `activation_condition` only; do not branch on removed precursor fields or legacy shorthand parameters.
- If you change diffusion, flow-field logic, or spatial hashing, run the benchmark tests, not just unit tests.
- Keep docstrings in Google style; docs are built with MkDocs + mkdocstrings from `docs/`.
- Do not reintroduce file-local `AsyncClient` factories in API integration tests; use shared fixtures from `tests/conftest.py`.

## Test Docstring Hygiene (Required)
- Avoid empty boilerplate docstrings (for example, "Validates the ... invariant") that add no technical meaning.
- Keep test docstrings specific to the asserted contract, branch, or regression surface.
- Apply Google-style sections when applicable to the signature/behavior (`Args`, `Returns`, `Raises`, `Attributes`, `Yields`, `Examples`, `Notes`).
- For parameterized tests and fixture-heavy tests, include `Args` when it improves reproducibility of the assertion context.

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

## Documentation Agent Orchestration
- Agent definitions live under `.github/agents/*.agent.md`; keep scope-specific behavior there to avoid policy duplication here.
- `docs-librarian`, `docs-scientist`, and `docs-operator` each have whole-`docs/` primary accessible scope.
- `docs-librarian` is the coordinator and final QA gate: assign concrete file targets and writing mode before delegation.
- Default delegation is by specialty:
  - Scientific/engine/foundations and analytical reference docs -> `docs-scientist`.
  - Development workflows, runbooks, CI/CD, and contributor operations -> `docs-operator`.
  - Python docstring-only work (`src/phids/**/*.py`, `tests/**/*.py`) -> `docs-annotator`.
- Delegation is the default; explicit user tagging is optional when scope can be inferred reliably.
- `docs-librarian` validates delegated outputs for implementation-truth alignment, link/nav integrity, and writing-mode compliance.
- If scope is mixed or drift is detected, `docs-librarian` retasks/subdivides and revalidates before completion.

## Documentation Policy Sources
- Core architectural and language rules: `.github/copilot-instructions.md`.
- Docstring execution constraints and section ordering: `.github/prompts/docstrings.md.prompt.md`.
- Mode-specific writing behavior: `.github/agents/docs-scientist.agent.md`, `.github/agents/docs-operator.agent.md`, `.github/agents/docs-annotator.agent.md`.
- Canonical agent and MCP governance docs: `docs/development/agent-ecosystem-and-governance.md`, `docs/development/agent-ownership-delegation.md`, `docs/development/agent-invocation-and-reporting.md`, `docs/development/mcp-capability-model.md`, `docs/development/mcp-lifecycle.md`, `docs/development/agent-target-state-blueprint.md`.
- Use those chapters as source-of-truth for implemented vs planned agent capabilities; keep this file as a concise routing guide.
- Documentation work is not complete until `uv run mkdocs build --strict` passes.

## Git Operations Agent
- `git-ops` is the dedicated agent for repository lifecycle work: status inspection, staged slicing, signed commits, branch management, merge/rebase flows, push/publish, and release tagging.
- Route Git-centric tasks directly to `git-ops` (for example: commit preparation, branch creation, PR publication, merge workflows, rollback support).
- `git-ops` executes push/publish, pull-request actions, release-tag workflows, and release publication after explicit in-session instruction from a human operator.
- `git-ops` runs with tool-backed execution through `.github/agents/git-ops.agent.md` and reports resulting refs, SHAs, and next verification actions.

## Test Operations Agent
- `test-ops` is the dedicated testing specialist for deterministic execution, failure isolation, coverage triage, and verification handoff.
- Route test-centric work (failing suites, flaky behavior, missing coverage, gate triage) to `test-ops` through `.github/agents/test-ops.agent.md`.
- Default escalation path: when `git-ops` encounters failing tests or coverage gates, it delegates remediation to `test-ops` and resumes publish flow only after recheck results are returned.
