---
type: workflow
title: Sequence
status: active
version: '0.1'
description: Process for adding ecological/mathematical behaviors.
tags:
- documentation
timestamp: '2026-07-21T16:01:38Z'
resources: []
name: Implement Scientific Model
---

# Sequence
1. **Theory (Scientific Architect):** Read `docs/scientific_model/`; draft matrix shapes/stochastic boundaries.
2. **Engine (Engine Developer):** Add NumPy arrays to read/write buffers. Implement `@njit` logic (no allocations). Hook into `SimulationLoop` phase.
3. **Telemetry (Engine Developer):** Write outcomes (especially stochastic ones) to Zarr replay schema.
4. **Validation (QA Automator):** Write `pytest-benchmark` (verify TPS baseline) and bounded `hypothesis` pilot (floating-point stability).
5. **Documentation (Docs Librarian):** Auto-update API reference; add link to `docs/reference/requirements-traceability.md`.
