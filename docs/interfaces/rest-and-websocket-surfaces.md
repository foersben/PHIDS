# REST and WebSocket Surfaces

PHIDS exposes its runtime through two network styles with intentionally different semantics:

- **REST endpoints** for validated control, configuration transfer, and HTML partial rendering,
- **WebSocket streams** for continuously changing simulation state.

This chapter documents the current interface surface as implemented in `src/phids/api/main.py`.
It should be read together with the architectural distinction between `DraftState` and the live
`SimulationLoop`.

## Interface Taxonomy

The current route surface falls into six families:

1. **Scenario ingress and loading**
2. **Simulation lifecycle control**
3. **Telemetry export and polling**
4. **UI polling and inspection helpers**
5. **UI builder and partial-render endpoints**
6. **WebSocket streaming**

Each family serves a different boundary in the overall system.

## 1. Scenario Ingress and Loading

| Route | Primary response | Role |
| --- | --- | --- |
| `POST /api/scenario/load` | JSON | Load a provided `SimulationConfig` directly into a live `SimulationLoop`. |
| `POST /api/scenario/load-draft` | HTML status badge | Compile the current `DraftState` and commit it to the engine. |
| `GET /api/scenario/export` | Downloaded JSON file | Export the current draft through the schema boundary. |
| `POST /api/scenario/import` | JSON | Validate uploaded JSON as `SimulationConfig` and reconstruct draft state. |

### `POST /api/scenario/load`

This route accepts a validated `SimulationConfig` payload and constructs a live
`SimulationLoop`. It is the direct machine-oriented path from external JSON into the engine.

### `POST /api/scenario/load-draft`

This route does **not** accept a configuration body. Instead, it calls `DraftState.build_sim_config()`
on the current server-side draft and uses that result to instantiate a live `SimulationLoop`.

Unlike `POST /api/scenario/load`, the current implementation returns an HTML status fragment because
this route is primarily driven by the HTMX control center.

This route is one of the most important interface boundaries in PHIDS because it formalizes the
transition from:

- **editable draft state**, to
- **validated live runtime state**.

### `GET /api/scenario/export`

This route serializes the current draft to JSON by first building a validated `SimulationConfig`.
It therefore exports the draft through the same schema boundary used for live execution.

### `POST /api/scenario/import`

This route ingests uploaded JSON, validates it as `SimulationConfig`, then reconstructs a new
`DraftState` from the imported data. In other words, import does not directly start a simulation;
it repopulates the server-side builder state.

## 2. Simulation Lifecycle Control

The live simulation can be controlled through explicit lifecycle endpoints:

| Route | Primary response | Current semantics |
| --- | --- | --- |
| `POST /api/simulation/start` | JSON or HTML badge | Start background execution, or resume from pause. |
| `POST /api/simulation/pause` | JSON or HTML badge | Toggle pause/resume on the active loop. |
| `POST /api/simulation/step` | JSON or HTML badge | Advance exactly one deterministic tick when not actively running. |
| `POST /api/simulation/reset` | JSON or HTML badge | Recreate the live loop from the currently loaded baseline config. |
| `GET /api/simulation/status` | JSON | Report tick, running, paused, terminated, and termination reason. |
| `PUT /api/simulation/wind` | JSON | Mutate the live environment wind vector. |

These routes operate on the currently loaded `SimulationLoop`.

## Lifecycle Semantics

### Start and pause

`start` marks the loop as running, while `pause` toggles the paused flag. The runtime remains
single-loop oriented: PHIDS is not currently a multi-simulation orchestration service.

### Step

`step` advances the simulation by exactly one deterministic tick. This route is especially useful
for controlled observation, debugging, and interface-driven inspection workflows.

### Reset

`reset` rebuilds the simulation from the loaded scenario baseline. It is a runtime control action,
not a draft mutation.

### Status

`status` reports live runtime state such as tick, running, paused, terminated, and termination
reason.

### Wind update

`PUT /api/simulation/wind` updates the wind field of the current live environment. This is a direct
runtime mutation rather than a draft mutation.

## 3. Telemetry Export and Polling Surfaces

PHIDS exposes telemetry through two distinct interaction styles.

For the analytics and replay semantics behind these routes, see:

- [`../telemetry/analytics-and-export-formats.md`](../telemetry/analytics-and-export-formats.md)
- [`../telemetry/replay-and-termination-semantics.md`](../telemetry/replay-and-termination-semantics.md)

### Download/export routes

| Route | Response | Role |
| --- | --- | --- |
| `GET /api/telemetry/export/csv` | Downloaded CSV | Export telemetry for external analysis. |
| `GET /api/telemetry/export/json` | Downloaded NDJSON | Export telemetry rows as line-delimited JSON. |

These routes export the current loop’s telemetry dataframe in external analysis formats.

Current implementation note: heavy export serialization paths are executed via
`run_in_threadpool` in `src/phids/api/main.py` so CPU-bound pandas/matplotlib/TikZ generation
does not block the asyncio event loop that also drives control endpoints and WebSocket streams.

## 4. UI Polling and Inspection Helpers

The UI uses lighter-weight polling endpoints such as:

| Route | Response | Role |
| --- | --- | --- |
| `GET /api/ui/tick` | Plain text | Supply the current tick for HTMX updates. |
| `GET /api/ui/status-badge` | HTML fragment | Render the current simulation status badge. |
| `GET /api/telemetry` | HTML fragment | Render the inline telemetry chart partial. |
| `GET /api/ui/cell-details` | JSON | Provide live or draft-preview tooltip details for one grid cell. |
| `GET /api/config/placements/data` | JSON | Provide placement-editor canvas data and inferred root links. |

These are not bulk export routes. They exist to drive incremental interface updates and localized
inspection inside the control center.

Telemetry chart polling is intentionally bounded on the browser side. The dashboard telemetry
script keeps Chart.js instances alive and performs in-place dataset updates with a strict rolling
window cap, avoiding full chart teardown/recreation loops and preventing unbounded client-memory
growth during long runs.

## `GET /api/ui/cell-details`

This route is especially revealing of PHIDS’s interface philosophy.

- When a live simulation exists, it reports **live ECS/environment state**.
- When no live simulation exists, it reports a **draft preview** built from the current builder
  configuration.
- It also supports an `expected_tick` parameter and can return `409 Conflict` if the live
  simulation advanced before the caller retrieved tooltip details.
- In live mode, the payload now mirrors the dashboard's visible-substance semantics: it includes
  both plant-owned runtime substances and local signal/toxin layer fallbacks when a concentration is
  visible in the rendered snapshot.

This design makes temporal mismatch explicit rather than silently returning stale detail data.

## 5. UI Builder and Partial-Render Endpoints

The PHIDS control center is server-rendered and HTMX-driven. Consequently, many routes do not
return JSON at all; they return HTML fragments that replace portions of the page.

Representative route groups include:

### View partials

| Route family | Purpose |
| --- | --- |
| `/` | Render the full control-center shell. |
| `/ui/dashboard` | Render the live dashboard partial. |
| `/ui/biotope` | Render biotope configuration controls. |
| `/ui/flora` | Render flora editing table. |
| `/ui/predators` | Render predator editing table. |
| `/ui/substances` | Render substance-definition editor. |
| `/ui/diet-matrix` | Render predator/flora edibility matrix. |
| `/ui/trigger-rules` and `/ui/trigger-matrix` | Render trigger-rule editing views. |
| `/ui/placements` | Render placement editor and placement list. |
| `/ui/diagnostics/*` | Render model, frontend, and backend diagnostics tabs. |

### Draft mutation routes

Representative examples include:

| Route family | Current behavior |
| --- | --- |
| `POST /api/config/biotope` | Clamp and persist biotope parameters into `DraftState`. |
| `/api/config/flora` | Add, update, and delete flora species while compacting dependent ids. |
| `/api/config/predators` | Add, update, and delete predator species while compacting dependent ids. |
| `/api/config/substances` | Add, update, and delete named signal/toxin definitions. |
| `POST /api/matrices/diet` | Update the predator-to-flora diet compatibility matrix. |
| `/api/config/trigger-rules` | Add, update, and delete trigger rules. |
| `/api/config/trigger-rules/{index}/condition/*` | Create, patch, replace, or delete activation-condition tree nodes. |
| `/api/config/placements/*` | Add, remove, and clear draft plant/swarm placements. |

These endpoints mutate `DraftState` and then return a fresh HTML partial rendered from canonical
server-side state.

## 6. WebSocket Streams

PHIDS currently exposes two intentionally different WebSocket protocols.

### `WS /ws/simulation/stream`

This stream sends full state snapshots as:

- msgpack-serialized payloads,
- compressed with zlib,
- transmitted as binary frames.

Its role is to expose the simulation as a compact machine-readable state stream.

Important current behavior:

- if no scenario is loaded, the socket is closed with code `1008`,
- frames are emitted whenever the loop tick changes,
- when the simulation terminates, a final state frame is sent before closure.

### `WS /ws/ui/stream`

This stream sends lightweight JSON intended for browser rendering. It is not a duplicate of the
binary simulation stream.

According to the current route docstring and implementation, messages include data such as:

- plant-energy information,
- swarm positions and populations,
- tick state,
- max-energy context for visualization.

The implementation also only emits when the rendered state signature changes, so pause/resume and
termination state changes are visible even when the tick count itself is unchanged.

Its role is to support the canvas-based control-center view, not to serve as a full archival or
analysis transport.

## Why Two Streams Exist

The difference between these streams is architectural, not accidental:

- the binary stream is optimized for compact runtime transport,
- the UI stream is optimized for low-friction browser rendering.

This keeps the operator-facing canvas workflow lightweight while preserving a richer machine-facing
stream for other consumers.

## Error and State Semantics

PHIDS favors explicit stateful responses over hidden fallback behavior.

Examples in the current implementation include:

- policy close on `/ws/simulation/stream` when no scenario is loaded,
- `400` errors when draft export/load cannot build a valid config,
- `422` on invalid imported JSON,
- `409` on stale `expected_tick` reads for cell-detail inspection.

This is consistent with the project’s general design philosophy: validation and state boundaries
should be made visible to the operator rather than absorbed silently.

## Verified Current-State Evidence

The following sources confirm the behavior described in this chapter:

- `src/phids/api/main.py`
- `tests/test_api_routes.py`
- `tests/test_ui_routes.py`

## Where to Read Next

- For the conceptual overview of interface ownership: `docs/interfaces/index.md`
- For the draft-to-live transition: `docs/ui/draft-state-and-load-workflow.md`
- For the HTMX builder structure: `docs/ui/htmx-partials-and-builder-routes.md`
