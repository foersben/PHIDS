# Testing Strategy and Benchmark Policy

PHIDS testing is designed to protect both **correctness** and **performance invariants**. Because the
project is a deterministic simulation system with benchmark-sensitive hot paths, a good testing
strategy is not only about maximizing coverage; it is about selecting the right test surface for the
kind of change being made.

## Testing Philosophy

A useful way to read the PHIDS test suite is as a layered defense model:

1. **schema and invariant tests** protect configuration boundaries and hard architectural rules,
2. **system and loop tests** protect runtime behavior across phases,
3. **UI/API tests** protect operator surfaces and draft/live semantics,
4. **example-scenario tests** protect curated experimental fixtures,
5. **benchmark tests** protect performance-sensitive contracts.

This layered structure reflects the architecture of the project itself.

## Current Pytest Configuration

The active pytest settings live in `pyproject.toml`.

Current repository-wide defaults include:

- coverage over `src/phids`,
- `--cov-fail-under=80`,
- benchmark GC control,
- benchmark sorting by mean runtime.

This means that a plain repository-level run:

```bash
uv run pytest
```

is both a functional and coverage-enforcing quality gate.

## Full Quality-Gate Test Run

For merge-ready confidence, the project expects contributors to be able to run:

```bash
uv run pytest
```

This is the command mirrored by CI and should be treated as the canonical whole-suite check.

## Focused Functional Runs

For local iteration, PHIDS also supports focused functional runs on selected files.

Because the project-level pytest configuration injects coverage arguments, contributors may prefer to
clear `addopts` when they want a quick subsystem-only run without the global coverage gate.

Typical pattern:

```bash
uv run pytest -o addopts='' tests/<target_file>.py -q
```

This is useful for rapid feedback while editing one subsystem, as long as the contributor still runs
broader gates before considering the work complete.

## Suite Topology by Surface

### API route presence and top-level contracts

Representative file:

- `tests/integration/api/test_api_routes.py`

Use this when you need to confirm that expected route surfaces still exist.

### HTMX/UI rendering and draft/live interaction

Representative files:

- `tests/integration/api/test_ui_routes.py`
- `tests/unit/api/test_ui_state.py`
- `tests/integration/api/test_api_builder_and_helpers.py`

These protect:

- partial rendering,
- diagnostics tabs,
- draft mutation behavior,
- scenario import/export through the UI,
- load-draft semantics,
- helper functions that support the control center.

### Engine systems and phase behavior

Representative files:

- `tests/integration/systems/test_systems_behavior.py`
- `tests/integration/systems/test_termination_and_loop.py`

These protect:

- lifecycle behavior,
- interaction behavior,
- signaling behavior,
- termination semantics,
- loop integration,
- replay/telemetry integration.

### Core invariants and structural rules

Representative files:

- `tests/unit/api/test_schemas_and_invariants.py`
- `tests/unit/engine/core/test_biotope_diffusion.py`
- `tests/unit/engine/core/test_ecs_world.py`
- `tests/unit/engine/core/test_flow_field.py`

These protect:

- Rule-of-16 bounds,
- schema validation,
- buffering behavior,
- spatial-hash properties,
- flow-field semantics,
- subnormal-threshold behavior.

### Curated scenario fixtures

Representative file:

- `tests/e2e/scenarios/test_example_scenarios.py`

This protects the curated example pack as both a validation and runtime-compatibility surface.

## Recommended Focused Runs by Change Type

## Coverage Uplift Playbook (March 2026)

To keep module-level coverage robust under repository growth, PHIDS now includes
targeted regression tests for two historically under-covered operational paths:

- CLI launcher orchestration in `src/phids/__main__.py` via
  `tests/unit/cli/test_cli_main.py`.
- Batch executor orchestration in `src/phids/engine/batch.py` via
  additional tests in `tests/integration/systems/test_batch_runner.py` that cover:
  - `_run_and_save` tuple-unpacking delegation,
  - `_run_single_headless` early-termination break semantics,
  - `BatchRunner.execute_batch` success/failure future collection,
  - strict JSON summary persistence with non-finite value sanitization.

Recommended fast verification command for this specific coverage surface:

```bash
uv run pytest -o addopts='' tests/unit/cli/test_cli_main.py tests/integration/systems/test_batch_runner.py -q
```

To audit whether any runtime module dropped below 80% in a full run, use:

```bash
uv run pytest tests/ --no-header 2>&1 | awk '/^src\/phids\// {gsub("%","",$4); if (($4+0) < 80) print $0}'
```

An empty result means all currently reported modules satisfy the `>=80%` threshold.

### UI and builder changes

When editing:

- `src/phids/api/main.py`
- `src/phids/api/ui_state.py`
- `src/phids/api/templates/`

start with:

```bash
uv run pytest -o addopts='' tests/integration/api/test_ui_routes.py tests/unit/api/test_ui_state.py tests/integration/api/test_api_builder_and_helpers.py -q
```

### Engine system changes

When editing:

- `src/phids/engine/systems/`
- `src/phids/engine/loop.py`

start with:

```bash
uv run pytest -o addopts='' tests/integration/systems/test_systems_behavior.py tests/integration/systems/test_termination_and_loop.py -q
```

### Schema and scenario-language changes

When editing:

- `src/phids/api/schemas.py`
- `src/phids/io/scenario.py`
- scenario import/export behavior

start with:

```bash
uv run pytest -o addopts='' tests/unit/api/test_schemas_and_invariants.py tests/e2e/scenarios/test_example_scenarios.py tests/unit/api/test_ui_state.py -q
```

### Replay, telemetry, and export changes

When editing:

- `src/phids/telemetry/`
- `src/phids/io/replay.py`

start with:

```bash
uv run pytest -o addopts='' tests/integration/systems/test_termination_and_loop.py tests/integration/systems/test_lifecycle_reproduction.py tests/unit/io/test_replay_buffer.py tests/unit/telemetry/test_export_helpers.py tests/e2e/replay_and_io/test_replay_roundtrip.py -q
```

## Benchmark Policy

PHIDS has a small but important benchmark layer. These tests are not decorative; they express
performance-sensitive expectations for core runtime surfaces.

### Current dedicated benchmark files

- `tests/benchmarks/test_flow_field_benchmark.py`
- `tests/benchmarks/test_spatial_hash_benchmark.py`

### What they currently cover

- flow-field generation cost on a representative grid,
- hot-cell spatial-hash query behavior.

## When Benchmarks Are Mandatory

Benchmark tests should be run whenever a change touches:

- `src/phids/engine/core/flow_field.py`
- `src/phids/engine/core/ecs.py` spatial-hash behavior,
- any code that materially changes the work performed by those subsystems,
- diffusion-adjacent or locality-sensitive behavior that could indirectly degrade those paths.

Even if the change is functionally correct, a regression in these hotspots can violate important
project expectations.

## Benchmark Commands

Use:

```bash
uv run pytest -o addopts='' tests/benchmarks/test_flow_field_benchmark.py tests/benchmarks/test_spatial_hash_benchmark.py -q
```

For CI-parity whole-suite benchmarking, the repository-level `uv run pytest` remains the canonical
full run.

## Current Benchmark Scope Limits

The current benchmark layer does **not** mean every performance-sensitive subsystem has a dedicated
benchmark file.

In particular:

- flow field has a dedicated benchmark,
- spatial hash has a dedicated benchmark,
- diffusion is benchmark-sensitive in policy, but does not currently have a dedicated benchmark test
  file of its own.

Contributors should document and reason about that current state precisely.

## Coverage Strategy

Coverage is a project-level quality gate, but PHIDS has already demonstrated that the right response
to missing coverage is usually to add meaningful tests rather than weaken the threshold.

A good contribution should therefore:

- add focused tests for new behavior,
- prefer tests close to the owning subsystem,
- avoid bypassing the full-suite coverage gate as a final validation step.

## CI Parity

The current CI workflow distributes validation across three focused jobs:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mkdocs build --strict
```

In practice, the jobs are:

- `quality` for the repository's currently green Ruff lint/format checks,
- `tests-py312` for the full suite,
- `docs` for the strict MkDocs build.

The workflow is now intentionally triggered only for pull requests targeting `main` and manual
dispatch runs, which keeps expensive validation off intermediate branch pushes and off `develop`.

Any serious contribution should be considered in relation to this path, even if local iteration uses
smaller commands first. For the workflow structure and local `act` rehearsal commands, see
[`github-actions-and-local-ci.md`](github-actions-and-local-ci.md).

## Testing as Architectural Verification

In PHIDS, tests are especially valuable because many of the most important properties are not merely
function outputs; they are architectural invariants.

Examples include:

- draft state being distinct from live runtime state,
- environmental buffering behavior,
- root-network growth cadence,
- activation-condition tree semantics,
- flow-field linearity and toxin summation,
- replay framing and termination semantics.

These are the kinds of behaviors contributors should protect first when making changes.

## Practical Change-to-Test Matrix

| Change surface | First focused tests | Broader follow-up |
| --- | --- | --- |
| UI partials / builder routes | `tests/integration/api/test_ui_routes.py`, `tests/unit/api/test_ui_state.py`, `tests/integration/api/test_api_builder_and_helpers.py` | `uv run pytest` |
| Engine systems | `tests/integration/systems/test_systems_behavior.py`, `tests/integration/systems/test_termination_and_loop.py` | `uv run pytest` |
| Flow field | `tests/unit/engine/core/test_flow_field.py`, `tests/benchmarks/test_flow_field_benchmark.py` | `uv run pytest` |
| Spatial hash / ECS locality | `tests/unit/engine/core/test_ecs_world.py`, `tests/benchmarks/test_spatial_hash_benchmark.py` | `uv run pytest` |
| Scenario schema / import-export | `tests/unit/api/test_schemas_and_invariants.py`, `tests/e2e/scenarios/test_example_scenarios.py`, `tests/unit/api/test_ui_state.py` | `uv run pytest` |
| Replay / telemetry | `tests/e2e/replay_and_io/test_replay_roundtrip.py`, `tests/integration/systems/test_termination_and_loop.py`, `tests/unit/io/test_replay_buffer.py`, `tests/unit/telemetry/test_export_helpers.py` | `uv run pytest` |

## Verified Current-State Evidence

- `pyproject.toml`
- `.github/workflows/ci.yml`
- `README.md`
- `tests/integration/api/test_api_routes.py`
- `tests/integration/api/test_ui_routes.py`
- `tests/unit/api/test_ui_state.py`
- `tests/integration/api/test_api_builder_and_helpers.py`
- `tests/integration/systems/test_systems_behavior.py`
- `tests/integration/systems/test_termination_and_loop.py`
- `tests/unit/engine/core/test_flow_field.py`
- `tests/unit/engine/core/test_biotope_diffusion.py`
- `tests/unit/engine/core/test_ecs_world.py`
- `tests/e2e/scenarios/test_example_scenarios.py`
- `tests/benchmarks/test_flow_field_benchmark.py`
- `tests/benchmarks/test_spatial_hash_benchmark.py`

## Where to Read Next

- For contributor workflow around these checks: [`contribution-workflow-and-quality-gates.md`](contribution-workflow-and-quality-gates.md)
- For quality-gate traceability: [`../reference/requirements-traceability.md`](../reference/requirements-traceability.md)
- For benchmark-sensitive runtime subsystems: [`../engine/flow-field.md`](../engine/flow-field.md) and [`../engine/ecs-and-spatial-hash.md`](../engine/ecs-and-spatial-hash.md)
