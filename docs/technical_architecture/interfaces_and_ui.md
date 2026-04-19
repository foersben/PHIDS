# Interfaces & UI

PHIDS operates as a headless FastAPI backend, equipped with RESTful configuration surfaces, high-throughput WebSockets, and an embedded server-rendered dashboard powered by HTMX and Jinja.

## API Boundary

The simulator exposes operational boundaries required to drive experiments programmatically:
- `POST /api/scenario/load`: Ingests a validated `SimulationConfig`.
- `POST /api/simulation/start|pause`: Toggles execution state.
- `PUT /api/simulation/wind`: Injects meteorological forcing dynamics.

## Draft vs Live State

PHIDS distinguishes between the simulation currently under construction and the simulation actively running:
- **`DraftState`**: An ephemeral, mutable configuration stored on the server, heavily edited via the UI endpoints (e.g., matrix toggles, species addition). It has no ecological behavior.
- **`SimulationLoop` (Live Runtime)**: Created only when the operator actively "loads" the draft. Once initialized, the runtime strictly divorces from the Draft State.

## UI Control Center (HTMX + Jinja)

The administrative control center avoids the complexity of an SPA (Single Page Application). By leveraging HTMX, server-side Jinja templates directly replace DOM fragments in response to user events.
When a user updates the Diet Compatibility Matrix, the backend modifies the `DraftState` and responds immediately with a re-rendered partial HTML table. This establishes the server as the sole source of truth for the experimental schema.

## WebSocket Streaming

For live visualizations, PHIDS emits binary simulation state matrices asynchronously.
- `/ws/simulation/stream`: Pushes high-performance, `msgpack`-encoded buffers containing the biotope grid arrays at fixed intervals for immediate front-end rendering.
- `/ws/ui/stream`: Used to drive HTMX-adjacent, low-payload DOM updates, such as updating the live tick counter and dashboard metadata widgets.

## `WS /ws/ui/stream` Diagnostics Payload

For real-time UI diagnostics, the websocket transmits a JSON payload structured with a `contract_version` field. The top-level fields include `contract_version`, `tick`, `running`, `paused`, `terminated`, `termination_reason`, `grid_width`, `grid_height`, `max_energy`, `max_signal`, `max_toxin`, `species_energy`, `all_flora_species`, `signal_overlay`, `toxin_overlay`, `mycorrhizal_links`, `plants`, and `swarms`.

### Plants Columnar Table
The `plants` property transmits a list of plant objects containing the fields: `entity_id`, `species_id`, `name`, `x`, `y`, `energy`, `root_link_count`, `active_signal_ids`, and `active_toxin_ids`.

### Swarms Columnar Table
The `swarms` property transmits a list of swarm objects containing the fields: `species_id`, `name`, `x`, `y`, `population`, `energy`, `energy_deficit`, `repelled`, `repelled_ticks_remaining`, `toxin_level`, and `intoxicated`.
