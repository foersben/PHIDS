---
type: Reference
title: Python API Reference
status: stable
stale_after: "2027-01-01T00:00:00Z"
version: 0.1
description: Documentation for Python API Reference in the PHIDS framework.
tags: [phids, ecs, python]
generated: {by: process:okf-updater, at: "2026-07-21T16:01:38Z"}
verified: {by: process:okf-updater, at: "2026-08-14T16:00:00Z"}
---

# Python API & Service Contract Reference

The PHIDS application exposes an enterprise FastAPI service alongside a data-oriented Python API designed to orchestrate high-performance simulation runs, spatiotemporal PDE diffusions, and real-time telemetry streaming under strict zero-allocation hot-path constraints.

---

## 1. Architectural Guardrails: Async Event Loop Safety

**Threadpool Offloading (Rule 06 Mandate):**
All synchronous CPU-intensive, disk I/O, or database operations - including scenario YAML/JSON ingestion, Polars data transformations, DuckDB biological trait queries, and synchronous Zarr slice reads - must be offloaded to an AnyIO worker threadpool using `await asyncio.to_thread(...)` or `await anyio.to_thread.run_sync(...)`.

**Computational Rationale:**
FastAPI operates on a single-threaded cooperative event loop. Executing synchronous I/O or PDE computations directly inside `async def` route handlers blocks the event loop thread, preventing the server from accepting incoming HTTP requests or serving WebSocket keep-alive frames. Offloading CPU/IO bursts ensures the event loop remains responsive with sub-5ms latency percentiles.

---

## 2. Zero-Allocation Hot Path & Double-Buffered Arrays

Simulation state transformations inside `src/phids/engine/` operate on pre-allocated NumPy array layers:
* **Double-Buffering Invariant:** Systems read exclusively from immutable current layer arrays and write to `_write` layers.
* **Float Mask Gating (Rule 05-B):** State transitions execute branchlessly via float multipliers (`0.0` or `1.0`), eliminating dynamic allocations, Python closures, and scalar branching from JIT loops.
* **WebSocket Serialization:** State broadcasts serialize contiguous component buffers directly into compact binary payloads or lightweight JSON telemetry summaries without intermediate heap copies.

---

## 3. Schemas and Ingress

::: phids.api.schemas.base

::: phids.api.schemas.ecs

::: phids.api.schemas.conditions

::: phids.api.schemas.triggers

::: phids.api.schemas.species

::: phids.api.schemas.placement

::: phids.api.schemas.simulation

::: phids.api.schemas.responses

::: phids.io.scenario

## API and UI state surfaces

::: phids.api.main

::: phids.api.ui_state

::: phids.api.websockets.manager

### API Presenters

::: phids.api.presenters.dashboard.shared

::: phids.api.presenters.dashboard.payloads

::: phids.api.presenters.dashboard.mycorrhizal

::: phids.api.presenters.dashboard.cell_details.live

::: phids.api.presenters.dashboard.cell_details.preview

::: phids.api.presenters.diagnostics.model

::: phids.api.presenters.diagnostics.badge

::: phids.api.presenters.telemetry.svg

::: phids.api.presenters.trigger_rules.context

### API Services

::: phids.api.services.draft.biotope

::: phids.api.services.draft.diet

::: phids.api.services.draft.helpers

::: phids.api.services.draft.placements

::: phids.api.services.draft.species

::: phids.api.services.draft.substances

::: phids.api.services.draft.trigger_rules

::: phids.api.services.dse.task_manager

## Engine orchestration

::: phids.engine.loop

::: phids.engine.spawner

::: phids.engine.batch

## ECS components

::: phids.engine.components.plant

::: phids.engine.components.swarm

::: phids.engine.components.substances

## Core runtime structures

::: phids.engine.core.biotope

::: phids.engine.core.diffusion

::: phids.engine.core.ecs

::: phids.engine.core.flow

::: phids.engine.core.placement

## Engine systems

::: phids.engine.systems.lifecycle

::: phids.engine.systems.interaction.feeding

::: phids.engine.systems.interaction.metabolism

::: phids.engine.systems.interaction.movement

::: phids.engine.systems.interaction.population

::: phids.engine.systems.signaling

## Evolutionary Encapsulated Multi-Stage Design Space Exploration (EEDSE)

::: phids.analytics.bio_database

::: phids.analytics.dse_genotype

::: phids.analytics.dse_optimizer

::: phids.analytics.dse_pruning

::: phids.analytics.tuning

## Telemetry and replay

::: phids.telemetry.analytics

::: phids.telemetry.conditions

::: phids.telemetry.tick_metrics

::: phids.telemetry.export.core

::: phids.telemetry.export.latex

::: phids.telemetry.export.png

::: phids.telemetry.export.structured

::: phids.telemetry.export.tikz

::: phids.io.zarr_replay

::: phids.io.replay_types

## Integration

::: phids.mcp

## Shared utilities

::: phids.shared.coercion

::: phids.shared.constants

::: phids.shared.logging_config
