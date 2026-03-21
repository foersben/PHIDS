# PHIDS Test Suite Layout

The PHIDS test suite is organized by architectural domain so that fast unit checks,
integration boundaries, and heavier replay/e2e workflows can evolve independently
without creating monolithic test modules.

## Directory map

- `tests/unit/`
  - `api/`: schemas, UI state, and presenter helper behavior
  - `engine/core/`: ECS, biotope, and flow-field deterministic unit checks
  - `telemetry/`: per-species telemetry accumulation and metric-shape checks
  - `shared/`: logging and utility-layer invariants
  - `cli/`: command-line entrypoint and namespace compatibility tests
- `tests/integration/`
  - `api/`: route/websocket/export behavior across FastAPI boundaries and UI builder flows
  - `systems/`: multi-system simulation interactions, loop semantics, and batch orchestration
- `tests/e2e/`
  - `scenarios/`: curated scenario fixture execution and compatibility checks
  - `replay_and_io/`: replay persistence and zarr roundtrip compatibility tests
- `tests/benchmarks/`: deterministic performance-regression benchmarks

## Migration approach

This repository is transitioning incrementally from a flat `tests/` layout to this
hierarchy to keep CI stable. Existing root-level modules remain valid while they are
moved in small, verifiable batches.

Coverage guard modules currently remain at the root (`test_coverage_*`). Domain-owned behavior
tests previously grouped in `test_additional_coverage.py` have been migrated into
`tests/integration/api/`, `tests/integration/systems/`, `tests/unit/io/`,
`tests/unit/telemetry/`, `tests/unit/engine/core/`, and `tests/unit/shared/`.

## God test policy

Route and helper regressions must be decomposed into narrowly scoped tests that each validate one
state transition or one helper contract. Avoid multi-branch "God Tests" that chain unrelated
operations because a single early failure obscures downstream regressions and slows diagnosis.

Preferred naming pattern:

- `test_<surface>_<condition>_<expected_behavior>` for API/integration checks.
- `test_<symbol>_<branch_or_invariant>` for pure helper and unit checks.

## Targeted coverage workflow

Use targeted coverage when validating one test module or node while still enforcing the project
coverage floor for the relevant implementation surface.

```zsh
scripts/target_cov.zsh tests/integration/api/test_api_simulation_and_scenario_routes.py phids.api.routers.simulation
scripts/target_cov.zsh tests/unit/api/test_ui_state.py phids.api.services.draft_service
```

This keeps fast debugging (`-o addopts=''`) and applies `--cov-fail-under=80` only to the selected
module, which is the suitable denominator for individual-slice verification.
