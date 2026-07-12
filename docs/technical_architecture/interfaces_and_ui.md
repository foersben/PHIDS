---
type: technical_architecture
title: "Interfaces & UI"
status: active
version: 0.1
description: "Documentation for Interfaces & UI in the PHIDS framework."
---

# Interfaces & UI

PHIDS operates as a headless FastAPI backend, equipped with RESTful configuration surfaces, high-throughput WebSockets for live state streaming, and an embedded server-rendered dashboard powered by HTMX and Jinja.

## API Boundary

The simulator exposes operational boundaries required to drive experiments programmatically without relying on the browser UI. The primary simulation controls include:

- `POST /api/scenario/load`: Ingests a validated `SimulationConfig`, destroying any running execution loops and staging the system for initialization.
- `POST /api/simulation/start|pause`: Toggles execution state of the live simulation.
- `PUT /api/simulation/wind`: Injects meteorological forcing dynamics into the environment layers while the simulation runs.

## Draft vs Live State

PHIDS establishes a strict barrier between the simulation currently under construction and the simulation actively executing. This prevents configuration adjustments from inadvertently modifying active scientific experiments mid-run.

- **`DraftState`**: An ephemeral, mutable configuration stored on the server. This is heavily edited via the UI endpoints (e.g., toggling diet matrix compatibility, modifying reproduction bounds, adding species). Modifying the Draft State has absolutely zero ecological impact on the live model.
- **`SimulationLoop` (Live Runtime)**: Created only when the operator explicitly "loads" the draft configuration into the engine. Once initialized, the runtime strictly divorces from the Draft State.

## UI Control Center (HTMX + Jinja)

The administrative control center intentionally avoids the complexity of a Single Page Application (SPA) like React or Vue. By leveraging HTMX, server-side Jinja templates directly replace DOM fragments in response to user events.

When a user clicks a checkbox to update the Diet Compatibility Matrix, the backend modifies the `DraftState` and responds immediately with a re-rendered partial HTML table. This architectural choice establishes the server as the absolute, single source of truth for the experimental schema, ensuring UI state cannot desynchronize from backend limits.

## WebSocket Streaming

For live visualizations and diagnostics, PHIDS emits binary simulation state matrices asynchronously.

- `/ws/simulation/stream`: This high-performance socket pushes `msgpack`-encoded, zlib-compressed buffers containing the biotope grid arrays at fixed intervals. It is designed to be consumed by Canvas or WebGL renderers for immediate, 60fps front-end rendering of the continuous cellular automata fields.
- `/ws/ui/stream`: Operates alongside HTMX. It pushes low-payload JSON diagnostic updates, such as the live tick counter, aggregated dashboard metadata, and specific cell inspection tooltips.

### `WS /ws/ui/stream` Diagnostics Payload

For real-time UI diagnostics, the secondary websocket transmits a JSON payload structured with a `contract_version` field to ensure backward compatibility as the data schema evolves.

The top-level fields include generic simulation flags (`tick`, `running`, `paused`, `terminated`, `termination_reason`), grid bounds (`grid_width`, `grid_height`), global maxima for canvas color scaling (`max_energy`, `max_signal`, `max_toxin`), and overlay structures (`species_energy`, `all_flora_species`, `signal_overlay`, `toxin_overlay`, `mycorrhizal_links`, `plants`, `swarms`).

Furthermore, it streams two columnar tables for entity diagnostics:

- **Plants Columnar Table**: Transmits a list of plant objects containing the fields: `entity_id`, `species_id`, `name`, `x`, `y`, `energy`, `root_link_count`, `active_signal_ids`, and `active_toxin_ids`.
- **Swarms Columnar Table**: Transmits a list of swarm objects containing the fields: `species_id`, `name`, `x`, `y`, `population`, `energy`, `energy_deficit`, `repelled`, `repelled_ticks_remaining`, `toxin_level`, and `intoxicated`.

## Metric Translation & UI Relativization

To balance raw computational throughput with human cognitive design-space exploration (DSE), PHIDS intentionally separates the representation of metrics in the core engine from their presentation in the user interface.

### The Engine Absolute (ECS)

At the lowest level, the engine core and Zarr telemetry buffers operate strictly on **absolute numerical primitives** (e.g., `population = 450`, `energy = 5.2`, `signal_layer_peak = 0.85`). These unboxed arrays avoid the massive overhead of context-switching, relative percentage calculations, and bounds-checking inside the tight Numba JIT simulation loop. The physics simulation simply does not care what `100%` is–it solely computes mass/energy transfers based on absolute local concentrations.

### The Presenter Relative (API Layer)

While absolute metrics are computationally optimal, they are cognitively opaque for human operators tuning a scenario. An energy value of `45.0` is meaningless unless the operator knows the specific species' genetic carrying capacity is `50.0`.

To solve this, the backend API presenter layer (e.g., `cell_details.py`) acts as a normalization boundary. Before JSON payloads are dispatched to the browser, the presenter injects **relative and synthesized metrics** alongside the raw data:

- `energy_ratio` and `energy_label` (e.g. `45.0 / 50.0 (90%)`).
- `mitosis_progress` (population evaluated against its genetic splitting threshold).
- `value_pct` for chemical concentrations relative to local saturation caps.

This architectural pattern guarantees that the heavy-lifting of percentage calculations, floating-point formatting, and tooltip string generation never pollutes the core simulation loop, while ensuring the UI is highly readable and "normalized" for scientists exploring the data.
