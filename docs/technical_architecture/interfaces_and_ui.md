# Interfaces & UI

PHIDS operates as a headless FastAPI backend, equipped with RESTful configuration surfaces, high-throughput WebSockets for live state streaming, and an embedded server-rendered dashboard powered by HTMX and Jinja.

## API Boundary

The simulator exposes operational boundaries required to drive experiments programmatically without relying on the browser UI. The primary simulation controls include:

-   `POST /api/scenario/load`: Ingests a validated `SimulationConfig`, destroying any running execution loops and staging the system for initialization.
-   `POST /api/simulation/start|pause`: Toggles execution state of the live simulation.
-   `PUT /api/simulation/wind`: Injects meteorological forcing dynamics into the environment layers while the simulation runs.

## Draft vs Live State

PHIDS establishes a strict barrier between the simulation currently under construction and the simulation actively executing. This prevents configuration adjustments from inadvertently modifying active scientific experiments mid-run.

-   **`DraftState`**: An ephemeral, mutable configuration stored on the server. This is heavily edited via the UI endpoints (e.g., toggling diet matrix compatibility, modifying reproduction bounds, adding species). Modifying the Draft State has absolutely zero ecological impact on the live model.
-   **`SimulationLoop` (Live Runtime)**: Created only when the operator explicitly "loads" the draft configuration into the engine. Once initialized, the runtime strictly divorces from the Draft State.

## UI Control Center (HTMX + Jinja)

The administrative control center intentionally avoids the complexity of a Single Page Application (SPA) like React or Vue. By leveraging HTMX, server-side Jinja templates directly replace DOM fragments in response to user events.

When a user clicks a checkbox to update the Diet Compatibility Matrix, the backend modifies the `DraftState` and responds immediately with a re-rendered partial HTML table. This architectural choice establishes the server as the absolute, single source of truth for the experimental schema, ensuring UI state cannot desynchronize from backend limits.

## WebSocket Streaming

For live visualizations and diagnostics, PHIDS emits binary simulation state matrices asynchronously.

-   `/ws/simulation/stream`: This high-performance socket pushes `msgpack`-encoded, zlib-compressed buffers containing the biotope grid arrays at fixed intervals. It is designed to be consumed by Canvas or WebGL renderers for immediate, 60fps front-end rendering of the continuous cellular automata fields.
-   `/ws/ui/stream`: Operates alongside HTMX. It pushes low-payload JSON diagnostic updates, such as the live tick counter, aggregated dashboard metadata, and specific cell inspection tooltips.

### `WS /ws/ui/stream` Diagnostics Payload

For real-time UI diagnostics, the secondary websocket transmits a JSON payload structured with a `contract_version` field to ensure backward compatibility as the data schema evolves.

The top-level fields include generic simulation flags (`tick`, `running`, `paused`, `terminated`, `termination_reason`), grid bounds (`grid_width`, `grid_height`), global maxima for canvas color scaling (`max_energy`, `max_signal`, `max_toxin`), and overlay structures (`species_energy`, `all_flora_species`, `signal_overlay`, `toxin_overlay`, `mycorrhizal_links`).

Furthermore, it streams two columnar tables for entity diagnostics:

-   **Plants Columnar Table**: Transmits a list of plant objects containing the fields: `entity_id`, `species_id`, `name`, `x`, `y`, `energy`, `root_link_count`, `active_signal_ids`, and `active_toxin_ids`.
-   **Swarms Columnar Table**: Transmits a list of swarm objects containing the fields: `species_id`, `name`, `x`, `y`, `population`, `energy`, `energy_deficit`, `repelled`, `repelled_ticks_remaining`, `toxin_level`, and `intoxicated`.
