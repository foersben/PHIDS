---
name: vertical-slice-development
type: Agent Skill
title: Vertical Slice Development
status: stable
stale_after: "2027-01-01T00:00:00Z"
version: 1.0
description: Coordinated pipeline for building full-stack simulation features spanning models, ECS, telemetry, and UI.
tags: [vertical-slice, ecs, full-stack, pipeline]
generated: {by: process:agent-os-refactor, at: "2026-10-30T00:00:00Z"}
verified: {by: process:agent-os-refactor, at: "2026-10-30T00:00:00Z"}
---

# Vertical Slice Development

Coordinated pipeline for building full-stack simulation features.

## Trigger

Run via `/vertical-slice-development` when creating an end-to-end feature integrating scientific kinetics, ECS arrays, Zarr telemetry, and HTMX UI views.

## Sequence

1. **Theory (Scientific Architect):** Define mathematical decay/interactions, substance parameters, and biotope array structures.
2. **Core (Engine Developer):** Implement JIT-compiled `@njit` ECS systems. Enforce double-buffering (`_write` layer) and array capacities.
3. **Telemetry (Telemetry & Data Engineer):** Update Zarr replay schema and Polars aggregations to record new state variables tick-by-tick.
4. **Interface (API & UI Developer):** Integrate features into fastapi/HTMX Draft State UI configurations and update WebSocket streaming.
5. **Testing (QA Automator):** Write pytest assertions, Mutation-resistance tests, and verify HTMX partials.
6. **Release (Git Operator):** Slice atomic commits; execute signed commit handoff.
