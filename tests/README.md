# PHIDS Test Suite Layout

The PHIDS test suite is organized by architectural domain so that fast unit checks,
integration boundaries, and heavier replay/e2e workflows can evolve independently
without creating monolithic test modules.

## Directory map

- `tests/unit/`
  - `api/`: schema and API-adjacent utility behavior
  - `cli/`: command-line entrypoint and namespace compatibility tests
- `tests/integration/`
  - `api/`: route/websocket/export behavior across FastAPI boundaries
- `tests/e2e/`
  - `replay_and_io/`: replay persistence and roundtrip compatibility tests
- `tests/benchmarks/` (planned): deterministic performance-regression benchmarks

## Migration approach

This repository is transitioning incrementally from a flat `tests/` layout to this
hierarchy to keep CI stable. Existing root-level modules remain valid while they are
moved in small, verifiable batches.
