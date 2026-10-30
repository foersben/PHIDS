---
name: implement-scientific-model
type: Agent Skill
title: Scientific Model Implementation
status: stable
stale_after: "2027-01-01T00:00:00Z"
version: 1.0
description: Process for adding ecological, biochemical, or mathematical behaviors to ECS arrays and simulation loop.
tags: [scientific-model, ecs, implementation, math]
generated: {by: process:agent-os-refactor, at: "2026-10-30T00:00:00Z"}
verified: {by: process:agent-os-refactor, at: "2026-10-30T00:00:00Z"}
---

# Scientific Model Implementation

Process for adding ecological and mathematical behaviors to the PHIDS simulation engine.

## Trigger

Run via `/implement-scientific-model` when introducing new ecological mechanisms, substance interactions, or physical dynamics into the ECS architecture.

## Sequence

1. **Theory (Scientific Architect):** Read `docs/scientific_model/`; draft matrix shapes and stochastic boundaries.
2. **Engine (Engine Developer):** Add NumPy arrays to read/write buffers. Implement `@njit` logic (no allocations). Hook into `SimulationLoop` phase.
3. **Telemetry (Engine Developer):** Write outcomes (especially stochastic ones) to Zarr replay schema.
4. **Validation (QA Automator):** Write `pytest-benchmark` (verify TPS baseline) and bounded `hypothesis` pilot (floating-point stability).
5. **Documentation (Docs Librarian):** Auto-update API reference; add link to `docs/reference/requirements-traceability.md`.
