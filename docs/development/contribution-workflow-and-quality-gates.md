# Contribution Workflow and Quality Gates

PHIDS is not an unconstrained Python project. It is a deterministic simulation system with strong
architectural rules, benchmark-sensitive hot paths, and a dual interface surface that must remain
internally consistent. This chapter documents how a contributor should approach changes in the
current repository.

## Development as Controlled Change

A useful way to think about PHIDS development is that every change touches one or more of four
boundaries:

1. **validated ingress** — schemas and scenario language,
2. **runtime execution** — `SimulationLoop`, engine systems, ECS, and biotope layers,
3. **operator surfaces** — REST, WebSocket, and HTMX/Jinja UI,
4. **analytical outputs** — telemetry, replay, exports, and documentation.

Good contributions preserve the invariants at those boundaries instead of only making a local test
pass.

## Canonical Engineering Non-Negotiables

The strongest repository-level rules are repeated across `AGENTS.md`,
`.github/copilot-instructions.md`, and the current engine implementation.

### 1. Data-oriented runtime model

Entities belong in `ECSWorld`. They should not be refactored into deep ad-hoc object graphs.

### 2. NumPy-backed field state

Environmental and matrix-like state belongs in NumPy arrays, not nested Python lists.

### 3. Buffered environmental semantics

`GridEnvironment` owns read/write buffer pairs for key environmental layers. Changes that bypass
these mechanics risk breaking determinism and visibility ordering.

### 4. Rule of 16 discipline

Species and substance spaces are bounded by the shared constants and corresponding schema limits.
Hot-path code must not rely on dynamic matrix growth inside the simulation loop.

### 5. Spatial locality over pairwise search

Local ecological interactions must use the spatial hash (`register_position`, `move_entity`,
`entities_at`) rather than O(N²) scans.

### 6. Benchmark-sensitive hot paths

Flow-field and spatial-hash behavior are not merely functionally correct surfaces; they are also
performance contracts.

## Primary Edit Map

A contributor should first identify which subsystem actually owns the behavior they want to change.

### Schemas and configuration boundary

- `src/phids/api/schemas.py`
- `src/phids/io/scenario.py`

Use these when changing:

- scenario structure,
- validation rules,
- trigger schema semantics,
- configuration bounds.

### UI draft and builder behavior

- `src/phids/api/ui_state.py`
- `src/phids/api/templates/`
- `src/phids/api/main.py`

Use these when changing:

- the builder workflow,
- draft-state mutations,
- partial rendering,
- load/import/export behavior.

### Engine runtime behavior

- `src/phids/engine/loop.py`
- `src/phids/engine/core/`
- `src/phids/engine/systems/`

Use these when changing:

- tick ordering,
- flow-field generation,
- buffering semantics,
- lifecycle, interaction, and signaling behavior.

### Telemetry and persistence

- `src/phids/telemetry/analytics.py`
- `src/phids/telemetry/conditions.py`
- `src/phids/telemetry/export.py`
- `src/phids/io/replay.py`

Use these when changing:

- exported metrics,
- replay framing,
- termination semantics,
- analytics artifacts.

## Draft vs Live State

One of the most important contribution pitfalls is confusing the UI draft with the live runtime.

### Draft state

`DraftState` is the editable scenario accumulator used by the server-rendered UI.

### Live state

`SimulationLoop` is the active runtime created only after scenario load or load-draft.

Practical consequence:

- if a change affects how the UI edits a scenario, it usually belongs in `ui_state.py`, templates,
  and builder routes,
- if a change affects what happens once the simulation is running, it usually belongs in engine code
  and possibly the schema layer.

## Suggested Workflow for a Change

A good current-state workflow for a non-trivial contribution is:

1. identify the owning subsystem,
2. verify the relevant invariants in code and docs,
3. make the smallest coherent change,
4. run focused tests for the touched surface,
5. run broader gates if the change hits shared/runtime-critical code,
6. rebuild the docs if prose, docstrings, or public structure changed.

## Tooling Baseline

The repository uses `uv` as its environment and execution entry point.

Current setup commands documented in the repo are:

```bash
uv sync --all-extras --dev
uv run uvicorn phids.api.main:app --reload --app-dir src
```

The project metadata currently declares:

- Python `>=3.11`,
- Ruff targeting `py312`,
- strict mypy over `src/phids` and `tests`,
- pytest with coverage and benchmark addopts,
- Google-style docstrings via `pydocstyle`.

## Quality Gates in Current Configuration

### Ruff

Configured in `pyproject.toml` and mirrored in CI.

### mypy

Runs in strict mode and uses the Pydantic mypy plugin.

### pytest with coverage and benchmarks

The project-level pytest configuration includes:

- coverage over `src/phids`,
- fail-under threshold `80`,
- benchmark sorting and GC control.

### MkDocs strict build

Documentation is part of the quality gate and must pass:

```bash
uv run mkdocs build --strict
```

## CI Parity

The current GitHub Actions workflow expresses CI as focused jobs rather than one long serial lane.

The active jobs are:

1. `quality` — `uv run ruff check .` and `uv run ruff format --check .`
2. `tests-py312` — `uv run pytest`
3. `compatibility-smoke-py311` — `uv run pytest -o addopts='' tests/test_api_routes.py tests/test_ui_routes.py tests/test_systems_behavior.py tests/test_example_scenarios.py -q`
4. `docs` — `uv run mkdocs build --strict`

A contributor should treat this as the authoritative parity target for merge-ready work.

`pre-commit` and `mypy` still exist as useful local cleanup tools, but they are not currently part
of the merge-blocking CI path because the repository still carries pre-existing type/docstyle debt.

For the reasoning behind that split and how to rehearse it locally with `act`, see:

- [`github-actions-and-local-ci.md`](github-actions-and-local-ci.md)

## Pre-commit Responsibilities

The current pre-commit setup runs:

- Ruff with `--fix`,
- Ruff format,
- mypy,
- whitespace and file-ending hygiene hooks,
- YAML/TOML validity checks,
- merge-conflict checks,
- `pydocstyle --convention=google`.

This means style and structural hygiene are enforced before CI, not only inside it.

## Focused Test Selection

Not every change requires the entire test suite first. The repo provides strong focused nets.

The canonical testing guidance now lives in:

- [`testing-strategy-and-benchmark-policy.md`](testing-strategy-and-benchmark-policy.md)

### UI and route changes

Use:

```bash
uv run pytest tests/test_ui_routes.py -q
```

### Engine system changes

Use:

```bash
uv run pytest tests/test_systems_behavior.py tests/test_termination_and_loop.py -q
```

### Benchmark-sensitive changes

If a change touches diffusion, flow field, or spatial hashing, also run:

```bash
uv run pytest tests/test_flow_field_benchmark.py tests/test_spatial_hash_benchmark.py -q
```

This is especially important because benchmark-sensitive regressions may not show up as functional
failures.

## Documentation Standards for Contributors

PHIDS documentation is now organized as a scientific MkDocs corpus. Contributors should ensure that
new prose:

- describes current behavior rather than aspirational behavior,
- links claims to concrete modules and symbols,
- cites tests when describing validated behavior,
- preserves provenance when migrating legacy content,
- remains navigable and buildable under strict mode.

## Docstrings and mkdocstrings

The project’s API reference is generated through mkdocstrings, so docstrings are part of the public
documentation surface.

Current rules include:

- Google-style docstrings,
- `pydocstyle` enforcement,
- clear Args/Returns/Notes structure when useful,
- alignment with actual runtime behavior.

Contributors should not treat docstrings as optional commentary; they are part of the documentation
contract.

## Common Pitfalls

### Confusing draft and live state

A very common mistake is implementing a runtime behavior change in the draft layer only, or vice
versa.

### Forgetting dependent compaction

Deleting flora, predator, or substance definitions usually requires cleanup of:

- IDs,
- matrices,
- trigger rules,
- placements,
- condition-tree references.

### Missing benchmark runs

Changes to flow-field logic, spatial hashing, or diffusion should trigger benchmark tests, not just
unit tests.

### Overstating idealized double-buffering

Current PHIDS most concretely implements buffered environmental state through `GridEnvironment`.
Contributors should document and reason about the current implementation precisely.

## A Useful Mental Model

A practical mental model for contributing to PHIDS is:

- **schemas define what may exist**,
- **draft state defines what may be edited**,
- **simulation loop defines what runs**,
- **telemetry and replay define what can be studied afterward**.

Good contributions preserve this chain instead of short-circuiting it.

## Verified Current-State Evidence

- `AGENTS.md`
- `.github/copilot-instructions.md`
- `pyproject.toml`
- `.pre-commit-config.yaml`
- `.github/workflows/ci.yml`
- `README.md`
- `src/phids/api/ui_state.py`
- `src/phids/api/main.py`
- `src/phids/engine/loop.py`
- `src/phids/engine/core/biotope.py`
- `src/phids/engine/core/ecs.py`
- `src/phids/engine/core/flow_field.py`

## Where to Read Next

- For the engine ownership model: [`../engine/index.md`](../engine/index.md)
- For draft-to-live semantics: [`../ui/draft-state-and-load-workflow.md`](../ui/draft-state-and-load-workflow.md)
- For the architecture-level state boundary overview: [`../architecture/index.md`](../architecture/index.md)
- For the current docs handoff and deferred work: [`documentation-status-and-open-work.md`](documentation-status-and-open-work.md)

