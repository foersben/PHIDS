---
type: workflow
description: Coordinated pipeline for building full-stack simulation features.
---

# Sequence

1. **Theory (Scientific Architect):** Define mathematical decay/interactions, substance parameters, and biotope array structures.
2. **Core (Engine Developer):** Implement JIT-compiled `@njit` ECS systems. Enforce double-buffering (`_write` layer) and array capacities.
3. **Telemetry (Telemetry & Data Engineer):** Update Zarr replay schema and Polars aggregations to record new state variables tick-by-tick.
4. **Interface (API & UI Developer):** Integrate features into fastapi/HTMX Draft State UI configurations and update WebSocket streaming.
5. **Testing (QA Automator):** Write pytest assertions, Mutation-resistance tests, and verify HTMX partials.
6. **Release (Git Operator):** Slice atomic commits; execute signed commit handoff.
