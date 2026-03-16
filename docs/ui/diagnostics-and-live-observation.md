# Diagnostics and Live Observation

The PHIDS control center provides a multi-layered observation surface for understanding simulation state from several complementary vantage points at once. A user can watch the global biotope evolve through canvas overlays, inspect a single cell for detailed local state, and monitor model and infrastructure health through diagnostic panels. These capabilities are not ornamental interface features; they are the practical observability layer through which a deterministic simulation becomes interpretable during execution.

This chapter documents the live observation surfaces as an integrated operational system. It explains how browser-oriented WebSocket streaming differs from binary simulation transport, how cell-detail inspection guards against stale reads, how the diagnostics rail exposes model and backend status, and how draft-versus-live boundaries affect what each endpoint is allowed to report. The focus is practical clarity: an operator should be able to understand which surface answers which question, and a contributor should be able to trace those surfaces back to their governing modules and invariants.

## Observation Modes Overview

The control center distinguishes three operationally distinct observation modes:

1. **Canvas streaming** — high-frequency WebSocket-driven visualization of the grid, swarms, and
   chemical overlays, rendered frame-by-frame in the browser canvas,
2. **Cell-detail inspection** — on-demand, per-cell JSON payloads exposing the full local
   ecological state at a selected grid coordinate,
3. **Diagnostics rail** — HTMX-polled panels surfacing model health counters, backend telemetry,
   and frontend rendering state.

These modes are complementary. Canvas streaming answers *where* and *what is happening across the
grid*; cell-detail inspection answers *why* at a specific location; the diagnostics rail answers
*how healthy is the overall simulation*.

Live cadence can be adjusted directly from the dashboard toolbar via the tick-speed control (`PUT /api/simulation/tick-rate`), allowing operators to slow or accelerate observation without reloading the active scenario.

---

## Canvas Streaming via `/ws/ui/stream`

The primary live visualization surface is the `/ws/ui/stream` WebSocket endpoint. This stream
differs fundamentally from the binary simulation stream (`/ws/simulation/stream`): it is optimized
for browser rendering, not programmatic full-state transport.

### Message content

Each frame sent by `/ws/ui/stream` contains:

| Field | Type | Description |
|-------|------|-------------|
| `tick` | `int` | Current simulation tick |
| `max_energy` | `float` | Maximum plant energy for canvas normalization |
| `plant_energy` | `[[float]]` | 2-D list of aggregate plant energy values per cell |
| `species_energy` | `[{species_id, name, layer}]` | Per-species energy arrays for overlay selection |
| `signal_overlay` | `[[float]]` | Summed signal concentration layer (null if no signals) |
| `toxin_overlay` | `[[float]]` | Summed toxin concentration layer (null if no toxins) |
| `max_signal` | `float` | Maximum value in `signal_overlay` for normalization |
| `max_toxin` | `float` | Maximum value in `toxin_overlay` for normalization |
| `plants` | `[{entity_id, x, y, species_id, energy, camouflage, ...}]` | Live plant list |
| `swarms` | `[{entity_id, x, y, species_id, population, energy, ...}]` | Live swarm list |
| `mycorrhizal_links` | `[{x1, y1, x2, y2, inter_species}]` | Active root-network links |
| `running` | `bool` | Whether the simulation loop is currently running |
| `paused` | `bool` | Whether the loop is currently paused |
| `terminated` | `bool` | Whether a termination condition has been satisfied |
| `termination_reason` | `str\|null` | Human-readable Z-code reason if terminated |

### Transmission policy

A frame is transmitted whenever the composite state signature `(loop_id, tick, running, paused,
terminated)` changes. This means the stream also fires on pause/resume toggles without requiring a
tick advancement, allowing the UI to update control button states responsively.

The stream sleeps for `1 / tick_rate_hz` seconds between polls, matching the simulation's own
cadence.

### Disconnection handling

The server closes the WebSocket cleanly on `WebSocketDisconnect`. The browser client is expected
to reconnect with exponential back-off.

---

## Binary Simulation Stream via `/ws/simulation/stream`

For programmatic full-state consumption — replay analysis, external tooling, or research data
pipelines — PHIDS exposes a separate binary stream at `/ws/simulation/stream`.

Each frame is a `msgpack`-serialized, `zlib`-compressed snapshot of the full `SimulationLoop`
state, including all environment layers. This stream is not optimized for canvas rendering; its
frame size is significantly larger than the UI stream.

The connection is rejected with WebSocket close code 1008 (Policy Violation) if no scenario is
currently loaded.

See also: [`../telemetry/replay-and-termination-semantics.md`](../telemetry/replay-and-termination-semantics.md)

---

## Cell-Detail Inspection via `GET /api/ui/cell-details`

When a user clicks or hovers over a grid cell in the canvas, the control center fetches a rich
tooltip payload from:

```
GET /api/ui/cell-details?x={x}&y={y}&expected_tick={tick}
```

### Live mode vs draft preview mode

The endpoint operates in two modes depending on runtime state:

- **Live mode** (a `SimulationLoop` is loaded): the payload is assembled from the live ECS world
  and `GridEnvironment`, exposing current plant energies, swarm populations, active substance
  states, local signal and toxin concentrations, and touching mycorrhizal links.
- **Draft preview mode** (no live simulation): the payload is assembled from `DraftState`,
  exposing configured initial placements and draft mycorrhizal link previews.

### Stale-tooltip protection via `expected_tick`

In live mode, the optional `expected_tick` query parameter enables stale-tooltip protection. If
`expected_tick` is supplied and does not match `_sim_loop.tick`, the server responds with HTTP 409
and a body containing `expected_tick`, `tick`, and a human-readable detail message. This allows the
client to discard the tooltip rather than displaying outdated cell data from a tick that has already
advanced.

### Payload fields (live mode)

The live cell-detail payload includes:

- `tick` — tick number at which the payload was sampled,
- `x`, `y` — cell coordinates,
- `plants` — list of plants at the cell with full component state,
- `swarms` — list of swarms at the cell with energetics and repellence state,
- `substances` — list of active and synthesizing substances attached to plants at the cell,
- `mycorrhizal_links` — root-network links touching the cell,
- `signal_peak` — peak signal concentration across all signal layers at the cell,
- `toxin_peak` — peak toxin concentration across all toxin layers at the cell.

---

## Diagnostics Rail

The diagnostics rail provides three tabbed inspection panels, each populated by a dedicated HTMX
partial route polled at a configurable interval.

### Model tab: `GET /ui/diagnostics/model`

Renders `partials/diagnostics_model.html` with the following context:

| Context key | Source |
|-------------|--------|
| `draft` | `get_draft()` — current server-side draft state |
| `live_summary` | `_build_live_summary()` — coarse live-model counters |
| `latest_metrics` | `_sim_loop.telemetry.get_latest_metrics()` — per-tick telemetry row |
| `energy_deficit_swarms` | `_build_energy_deficit_swarms()` — top energy-stressed swarms |

#### Live summary counters

`_build_live_summary()` returns a compact record with:

- `tick`, `running`, `paused`, `terminated`, `termination_reason` — loop lifecycle state,
- `plants` — count of live `PlantComponent` entities,
- `swarms` — count of live `SwarmComponent` entities,
- `active_substances` — count of substances that are active, synthesizing, or in aftereffect.

This record is `None` when no simulation is loaded.

#### Energy-deficit swarm watch

`_build_energy_deficit_swarms()` returns the top 12 swarms ranked by energy deficit
(`population × energy_min − energy`), sorted descending. Swarms at or above their minimum energy
floor are excluded. Each entry exposes `entity_id`, species name, population, coordinates,
`energy_deficit`, and `repelled` state.

This panel surfaces potential starvation events and metabolic attrition hotspots before they
result in population collapses, enabling operators to inspect the distribution of deficit pressure
across swarm species.

### Backend tab: `GET /ui/diagnostics/backend`

Renders `partials/diagnostics_backend.html` with up to 120 recent structured log records
(sourced from the in-process `get_recent_logs(limit=120)` ring buffer). This surfaces engine
lifecycle events, signaling warnings, and error-level records without requiring a separate log
viewer or file access.

### Frontend tab: `GET /ui/diagnostics/frontend`

Renders `partials/diagnostics_frontend.html`, a client-side diagnostic shell. This tab
exposes JavaScript-level rendering performance counters and WebSocket connection state, providing
visibility into the canvas rendering pipeline and frame-rate behavior that is not accessible from
the server side.

---

## Telemetry Polling via `GET /api/telemetry`

In addition to the diagnostics rail, telemetry metrics for all recorded ticks can be retrieved in
bulk via:

```
GET /api/telemetry?fmt=csv
GET /api/telemetry?fmt=json
```

These endpoints export the full `TelemetryRecorder` history as CSV or NDJSON respectively.
Individual tick metrics are available from `TelemetryRecorder.get_latest_metrics()`.

See: [`../telemetry/analytics-and-export-formats.md`](../telemetry/analytics-and-export-formats.md)

---

## Draft vs Live Inspection Boundary

A critical architectural invariant governs all observation endpoints:

- **Draft endpoints** operate on `DraftState`, the server-side editable record. These return
  hypothetical or configured initial placements, not simulation outcomes.
- **Live endpoints** operate on the active `SimulationLoop`, querying the live ECS world and
  `GridEnvironment`. These return simulation-time ecological state.

Some endpoints, such as `GET /api/ui/cell-details`, automatically select between the two modes
based on whether a live simulation is currently loaded. Others, such as the WebSocket streams, are
exclusively live-mode surfaces that close immediately when no scenario is loaded.

Operators should not interpret draft-mode payloads as predictive of live simulation behavior;
they reflect configured initial conditions only.

---

## Scientific Interpretability Notes

The observation surfaces are designed to support scientific interpretation of simulation outcomes,
not merely operational monitoring:

- **Cell-detail inspection** exposes per-substance `synthesis_remaining` and `aftereffect_remaining_ticks`
  counters, enabling direct observation of the temporal phases of chemical defense induction.
- **Energy-deficit watch** exposes metabolic attrition as it develops, allowing tracking of
  population collapses before they register as termination events.
- **Backend logs** include tick-level phase summaries (when debug logging is enabled) that expose
  per-phase timing, flow-field statistics, and per-cause plant death counts.
- **Canvas overlays** for signal and toxin layers expose the spatial diffusion of airborne VOCs
  and the locality of chemical defense zones, providing direct visual evidence of the Gaussian
  diffusion and point-emitter toxin models described in the engine documentation.

---

## Relevant Source Modules

- `src/phids/api/main.py` — observation endpoints and runtime summaries
  (`_build_live_summary`, `_build_energy_deficit_swarms`, `ui_diagnostics_model`,
  `ui_diagnostics_backend`, `ui_diagnostics_frontend`, `ui_stream`, `simulation_stream`)
- `src/phids/api/presenters/dashboard.py` — dashboard/cell payload assemblers
  (`build_live_dashboard_payload`, `build_live_cell_details`, `build_preview_cell_details`)
- `src/phids/api/templates/partials/diagnostics_model.html`
- `src/phids/api/templates/partials/diagnostics_backend.html`
- `src/phids/api/templates/partials/diagnostics_frontend.html`
- `src/phids/telemetry/analytics.py`
- `src/phids/shared/logging_config.py`

---

## Where to Read Next

- For the draft-to-live workflow that determines which observation mode is active:
  [`draft-state-and-load-workflow.md`](draft-state-and-load-workflow.md)
- For REST endpoint summaries including simulation lifecycle control:
  [`../interfaces/rest-and-websocket-surfaces.md`](../interfaces/rest-and-websocket-surfaces.md)
- For telemetry recording and export internals:
  [`../telemetry/analytics-and-export-formats.md`](../telemetry/analytics-and-export-formats.md)
- For termination condition semantics referenced in `live_summary`:
  [`../telemetry/replay-and-termination-semantics.md`](../telemetry/replay-and-termination-semantics.md)
