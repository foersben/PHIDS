# Technical Requirements Coverage

This document maps each item from `docs/technical_requirements.md` to the
implemented project artifacts.

## 1. Core Technology Stack

- Environment management (uv): project workflows are uv-first in
  `README.md` and `.github/workflows/ci.yml`.
- Vectorized data structures (numpy): continuous spatial matrices are
  NumPy arrays in `src/phids/engine/core/biotope.py`.
- Mathematical operations (scipy): diffusion uses
  `scipy.signal.convolve2d` in `src/phids/engine/core/biotope.py`.
- JIT compilation (numba): global flow field is generated in
  `src/phids/engine/core/flow_field.py` with `@njit`.
- API/network layer: FastAPI endpoints and WebSocket streaming are in
  `src/phids/api/main.py`.
- Telemetry aggregation (polars): metrics recorder is in
  `src/phids/telemetry/analytics.py`.
- Data validation (pydantic): schemas are in `src/phids/api/schemas.py`.
- Binary serialization (msgpack): replay serialization and per-tick state
  buffering are in `src/phids/io/replay.py` and
  `src/phids/engine/loop.py`.
- Architectural diagramming (mermaid.js): diagrams are in `docs/architecture.md`.

## 2. Development Workflow and CI/CD

- GitHub Actions CI/CD: quality workflow is in `.github/workflows/ci.yml`.
- pre-commit: hooks are configured in `.pre-commit-config.yaml` and enforced in CI.
- ruff + mypy: configured in `pyproject.toml`, executed in CI.
- pytest + pytest-cov + pytest-benchmark: configured in `pyproject.toml`,
  benchmark tests are in `tests/benchmarks/test_flow_field_benchmark.py` and
  `tests/benchmarks/test_spatial_hash_benchmark.py`.
- mkdocs + material + mkdocstrings: configured in `mkdocs.yml` with docs pages
  under `docs/`.

## 3. Architectural and Execution Constraints

- Double-buffering: read/write buffers are enforced for diffusive signal layers and
  pre-allocated local toxin layers in `src/phids/engine/core/biotope.py`.
- Rule of 16: hard caps and pre-allocation constants are in
  `src/phids/shared/constants.py` and used across schemas/environment code.
- ECS garbage collection: dead entities are purged via
  `ECSWorld.collect_garbage` in `src/phids/engine/core/ecs.py` and
  invoked by lifecycle/interaction/signaling systems.

## 4. Computational Optimization Directives

- O(1) spatial queries: grid-cell roster hash map in
  `src/phids/engine/core/ecs.py`.
- Subnormal mitigation: epsilon truncation after convolution in
  `src/phids/engine/core/biotope.py`.
- Unified pathfinding gradient: single global flow field in
  `src/phids/engine/core/flow_field.py` used by interaction logic.

## 5. Interface and Telemetry Specifications

- Required REST/WS routes: implemented in `src/phids/api/main.py`.
- Compressed state streaming: WebSocket frames are msgpack + zlib compressed
  in `src/phids/api/main.py`.
- Telemetry export utilities: CSV/JSON export in
  `src/phids/telemetry/export.py`.
