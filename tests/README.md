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

Coverage- and migration-specific guard modules currently remain at the root (`test_coverage_*`,
`test_additional_coverage.py`) and will be moved in a final consolidation pass after command and
documentation references are fully updated.
