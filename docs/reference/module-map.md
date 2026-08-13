---
type: reference
title: Module Map and Symbol Guide
status: active
version: 0.3
description: Whole-project inventory of active phids.* runtime packages, presenters, UI templates, and symbol responsibilities.
tags:
- phids
- ecs
- chemotaxis
- dual-proxy
- dashboard-ui
timestamp: "2026-08-13T19:30:00Z"
resources:
- api.md
- ../development_guide/contribution_workflow.md
- ../technical_architecture/interfaces_and_ui.md
- ../scientific_model/future_prospects/biological_abstractions_and_grid_mechanics.md
---

This page provides a whole-project inventory of the active `phids.*` runtime package. It is intended
as the quickest canonical answer to the question: *where in the codebase does a given concern
actually live?*

Unlike the narrative chapters elsewhere in the docs, this page is organized by package ownership and
symbol responsibility.

## How to Use This Page

This guide is intended for resolving the following inquiries:

* which module owns a behavior,
* which package defines a particular symbol,
* where a change should be made,
* where to jump from a narrative chapter into implementation reference.

## Top-Level Package Structure

The active runtime package is `phids.*` under `src/phids/`.

Its top-level subpackages are:

* `phids.api`
* `phids.engine`
* `phids.io`
* `phids.shared`
* `phids.telemetry`

## `phids.api`

This package owns schema validation, route surfaces, and the server-side UI draft state.

### `phids.api.schemas` (Package)

Primary responsibility:

* validated schema boundary for scenarios, triggers, placements, and API payloads.

Key symbols:

* `phids.api.schemas.simulation.SimulationConfig`
* `phids.api.schemas.triggers.TriggerConditionSchema`
* `phids.api.schemas.species.FloraSpeciesParams`
* `phids.api.schemas.species.HerbivoreSpeciesParams`
* `DietCompatibilityMatrix`
* `SimulationStatusResponse`
* `WindUpdatePayload`

Narrative docs:

* `docs/scenario_guide/`
* `docs/technical_architecture/`

### `phids.api.main`

Primary responsibility:

* FastAPI application, REST routes, HTMX partial routes, and WebSocket endpoints.

Key concerns:

* scenario load/import/export,
* simulation lifecycle control,
* UI polling and diagnostics,
* `/ws/simulation/stream`,
* `/ws/ui/stream`.

Narrative docs:

* `docs/technical_architecture/interfaces_and_ui.md`

### `phids.api.ui_state`

Primary responsibility:

* mutable server-side `DraftState` used by the scenario builder.

Key symbols:

* `DraftState`
* `TriggerRule`
* `SubstanceDefinition`
* `PlacedPlant`
* `PlacedSwarm`
* `get_draft`
* `set_draft`
* `reset_draft`

Narrative docs:

* `docs/technical_architecture/interfaces_and_ui.md`
* `docs/scenario_guide/scenario_authoring.md`

## `phids.engine`

This package owns the deterministic runtime execution model.

### `phids.engine.loop`

Primary responsibility:

* orchestrate the ordered simulation phases.

Key symbol:

* `SimulationLoop`

Narrative docs:

* `docs/technical_architecture/engine_execution.md`
* `docs/technical_architecture/system_architecture.md`

### `phids.engine.components`

Primary responsibility:

* runtime ECS component dataclasses.

Modules and symbols:

* `phids.engine.components.plant` - `PlantComponent` (includes `structural_mass`, `max_structural_mass`, and `growth_rate_structural` dual-proxy fields)
* `phids.engine.components.swarm` - `SwarmComponent` (includes `last_caloric_intake` and `metabolism_upkeep` MVT fields)
* `phids.engine.components.substances` - `SubstanceComponent`

Narrative docs:

* `docs/scientific_model/flora_and_symbiosis.md`
* `docs/scientific_model/herbivore_behavior.md`
* `docs/scientific_model/chemotaxis.md`

### `phids.engine.core.biotope`

Primary responsibility:

* vectorized environmental state and buffering.

Key symbol:

* `GridEnvironment`

Narrative docs:

* `docs/technical_architecture/engine_execution.md`

### `phids.engine.core.ecs`

Primary responsibility:

* ECS registry, component indexing, and spatial hash.

Key symbols:

* `Entity`
* `ECSWorld`

Narrative docs:

* `docs/technical_architecture/engine_execution.md`

### `phids.engine.core.flow_field`

Primary responsibility:

* global flow-field generation and camouflage attenuation.

Key symbols:

* `compute_flow_field`
* `apply_camouflage`

Narrative docs:

* `docs/technical_architecture/engine_execution.md`

### `phids.engine.systems.lifecycle`

Primary responsibility:

* Phase-Staggered Cohort (`(entity_id % 168) == (tick % 168)`) plant photosynthetic growth, $O(1)$ stochastic raycasting seed dispersal, mycorrhizal network establishment, and threshold culling.

Key symbol:

* `run_lifecycle`

Narrative docs:

* `docs/scientific_model/flora_and_symbiosis.md`

### `phids.engine.systems.interaction`

Primary responsibility:

* swarm movement, feeding, starvation, reproduction, mitosis, and toxin casualties.

Key symbol:

* `run_interaction`

Narrative docs:

* `docs/scientific_model/herbivore_behavior.md`

### `phids.engine.systems.signaling`

Primary responsibility:

* trigger evaluation, substance lifecycle, emission, relay, and diffusion delegation.

Key symbol:

* `run_signaling`

Narrative docs:

* `docs/scientific_model/chemotaxis.md`

## `phids.io`

This package owns scenario and replay persistence helpers.

### `phids.io.scenario`

Primary responsibility:

* load and serialize `SimulationConfig` values.

Key symbols:

* `load_scenario_from_dict`
* `load_scenario_from_json`
* `scenario_to_json`

Narrative docs:

* `docs/scenario_guide/curated_examples.md`
* `docs/scenario_guide/scenario_authoring.md`

### `phids.io.zarr_replay`

Primary responsibility:

* Zarr-based replay serialization and replay-file framing.

Key symbols:

* `ReplayBuffer`
* `NoOpReplayBuffer`
* `ReplaySlice`

Narrative docs:

* `docs/technical_architecture/telemetry.md`

## `phids.shared`

This package owns cross-cutting constants and logging helpers.

### `phids.shared.constants`

Primary responsibility:

* shared numerical and architectural constants.

Key constants:

* `MAX_FLORA_SPECIES`
* `MAX_HERBIVORE_SPECIES`
* `MAX_SUBSTANCE_TYPES`
* `GRID_W_MAX` (bounded to 10,000)
* `GRID_H_MAX` (bounded to 10,000)
* `SIGNAL_EPSILON`
* `SUBSTANCE_EMIT_RATE`
* `TOXIN_CASUALTY_FACTOR`
* `M_STRUCTURAL_SEED_VALUE` (dual-proxy: initial structural mass for new seeds; `0.0`)
* `M_STRUCTURAL_GROWTH_RATE` (dual-proxy: placeholder per-slow-tick growth fraction; replaced by DB values in Plan 2)

Narrative docs:

* `docs/scientific_model/`
* `docs/technical_architecture/engine_execution.md`

### `phids.shared.logging_config`

Primary responsibility:

* logging configuration and recent-log support used by the diagnostics UI.

Narrative docs:

* `docs/technical_architecture/interfaces_and_ui.md`

## `phids.telemetry`

This package owns summary metrics, termination logic, and export helpers.

### `phids.telemetry.analytics`

Primary responsibility:

* per-tick metric accumulation.

Key symbol:

* `TelemetryRecorder`

Narrative docs:

* `docs/technical_architecture/telemetry.md`

### `phids.telemetry.conditions`

Primary responsibility:

* `Z1`-`Z7` termination checks.

Key symbols:

* `TerminationResult`
* `check_termination`

Narrative docs:

* `docs/technical_architecture/telemetry.md`

### `phids.telemetry.export`

Primary responsibility:

* CSV and NDJSON export helpers.

Key symbols:

* `export_csv`
* `export_json`
* `export_bytes_csv`
* `export_bytes_json`

Narrative docs:

* `docs/technical_architecture/telemetry.md`

## Fastest Symbol-to-Page Guide

If you know the symbol but not the page, start here:

* `SimulationLoop` → `docs/technical_architecture/engine_execution.md`
* `DraftState` → `docs/technical_architecture/interfaces_and_ui.md`
If the symbol is known but the corresponding page is not, start here:

* `module-map.md` (this file) - to find which module the symbol belongs to.

### 2. Narrative vs. API Reference

Use the narrative chapters for resolving:

* System-wide integration of a component.
* The scientific or biological reasoning behind a module (e.g. why `SubnormalClamp` exists).
* Execution order constraints (e.g. why `InteractionSystem` runs before `GrowthSystem`).

Use the API reference for resolving:

* Function signatures and arguments.
* Returned shapes of NumPy arrays.
* Field descriptions of dataclasses.

## Where to Read Next

* For rendered symbol-level API docs: [`api.md`](api.md)
* For contributor-facing documentation rules: [`../development_guide/contribution_workflow.md`](../development_guide/contribution_workflow.md)
* For the repository-facing summary:
