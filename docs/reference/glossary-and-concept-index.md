# Glossary and Concept Index

This page provides concise, current-state definitions for the scientific and engineering vocabulary
used throughout the PHIDS documentation corpus. Each entry is defined in the language of the active
`phids.*` runtime under `src/phids/`. Cross-links to the owning narrative chapters are provided for
deeper reading.

---

## A

### Activation Condition

A JSON-structured predicate tree evaluated during the signaling phase to determine whether a
`SubstanceComponent` that has completed synthesis may transition to the active state. Supported node
kinds are `herbivore_presence`, `substance_active`, `environmental_signal`, `all_of`, and `any_of`.
Activation conditions allow composite, multi-factor trigger logic beyond a simple herbivore-count
threshold.

See: [`engine/signaling.md`](../engine/signaling.md)

### Aftereffect

A configurable timer (`aftereffect_ticks` / `aftereffect_remaining_ticks`) that keeps a substance
active for a bounded number of ticks after its trigger condition ceases to be satisfied. A substance
with zero aftereffect deactivates on the first non-triggered tick; one configured as `irreversible`
is pinned in the active state permanently after first activation.

See: [`engine/signaling.md`](../engine/signaling.md)

### Airborne Diffusion

The spatial spreading of volatile signal concentrations across the grid, modeled as Gaussian
diffusion via `scipy.signal.convolve2d` acting on signal layers. Diffusion is delegated to
`GridEnvironment.diffuse_signals()` and executes once per tick at the end of the signaling phase.
Toxin layers are intentionally excluded from diffusion; toxins are point-emitter defenses
constrained to the emitting plant's cell.

See: [`engine/biotope-and-double-buffering.md`](../engine/biotope-and-double-buffering.md),
[`engine/signaling.md`](../engine/signaling.md)

---

## B

### Baseline Energy

The minimum aggregate energy a swarm requires to sustain its current population at the `energy_min`
floor: `baseline_energy = population × energy_min`. In the interaction system's reproduction step,
only energy above this baseline ("surplus energy") is eligible for conversion into new individuals.
This prevents large, energy-marginal swarms from reproducing.

See: [`engine/interaction.md`](../engine/interaction.md)

---

## C

### Camouflage

A plant-level trait that attenuates the global flow field at the plant's cell after initial field
computation. A plant with `camouflage=True` and `camouflage_factor < 1.0` reduces the local
attraction signal visible to herbivore swarms, providing partial concealment from gradient-following
movement.

See: [`engine/flow-field.md`](../engine/flow-field.md)

### Carrying Capacity (`TILE_CARRYING_CAPACITY`)

The module-level constant in `interaction.py` (`TILE_CARRYING_CAPACITY = 500`) that defines the
maximum aggregate biological population permitted on a single grid cell before crowding-induced
dispersal is triggered. The check aggregates the `population` attribute of all co-located swarms —
not the count of swarm entities — so that biologically dense tiles are correctly identified
regardless of swarm entity fragmentation.

See: [`engine/interaction.md`](../engine/interaction.md)

### Control Center

The server-rendered HTMX/Jinja UI surface exposed at `http://localhost:8000/`. It combines
scenario drafting, live simulation monitoring, telemetry inspection, and per-cell diagnostics in a
single browser workbench. State ownership remains on the server: the browser transmits incremental
mutations via HTMX, and the server-side `DraftState` is the canonical editable record.

See: [`ui/index.md`](../ui/index.md)

---

## D

### Data-Oriented Design

The architectural philosophy of PHIDS's engine: entities are component bags stored in flat
registry structures (`ECSWorld`), not behavioral Python objects. Grid state lives in NumPy arrays.
Hot-path math is Numba-compiled. This approach maximizes cache locality, enables vectorization, and
ensures that adding a new entity type does not require subclassing or inheritance hierarchies.

See: [`architecture/index.md`](../architecture/index.md), [`engine/ecs-and-spatial-hash.md`](../engine/ecs-and-spatial-hash.md)

### Diet Matrix

A two-dimensional boolean compatibility matrix indexed by `[herbivore_species_id][flora_species_id]`.
A `True` entry permits the corresponding herbivore species to feed on the corresponding flora species
during the interaction phase. The matrix is loaded from `SimulationConfig.diet_matrix` and cached
in `SimulationLoop._diet_matrix`.

See: [`engine/interaction.md`](../engine/interaction.md), [`scenarios/schema-and-curated-examples.md`](../scenarios/schema-and-curated-examples.md)

### Double Buffering

The technique of maintaining separate read and write copies of a mutable field layer so that updates
during one phase do not corrupt the state being consumed by the same phase. In PHIDS,
`GridEnvironment` double-buffers plant-energy-by-species layers and signal layers. Writes target the
`_..._write` backing arrays; a swap call (`rebuild_energy_layer()` or end-of-diffusion swap) makes
the new state read-visible.

See: [`engine/biotope-and-double-buffering.md`](../engine/biotope-and-double-buffering.md)

### Draft State (`DraftState`)

The mutable server-side model of the scenario currently being edited in the control center,
implemented in `phids.api.ui_state`. `DraftState` is entirely independent of any live
`SimulationLoop`. Only the explicit `POST /api/scenario/load-draft` action commits a validated
draft into a live simulation. This boundary prevents the browser from directly mutating runtime
state.

See: [`ui/draft-state-and-load-workflow.md`](../ui/draft-state-and-load-workflow.md)

---

## E

### ECS (Entity–Component–System)

The architectural pattern used for all discrete runtime entities in PHIDS. Entities are integer IDs;
components are dataclasses attached to entity IDs in `ECSWorld`; systems are free functions
(`run_lifecycle`, `run_interaction`, `run_signaling`) that query and mutate components. No
behavioral Python object hierarchy is used for plants, swarms, or substances.

See: [`engine/ecs-and-spatial-hash.md`](../engine/ecs-and-spatial-hash.md)

### `ECSWorld`

The central ECS registry in `phids.engine.core.ecs`. It stores entity IDs, per-component indexes
mapping entity IDs to component instances, and the spatial hash mapping grid cells to entity ID
sets. Key methods: `create_entity`, `add_component`, `get_entity`, `has_entity`,
`register_position`, `move_entity`, `unregister_position`, `entities_at`, `collect_garbage`.

See: [`engine/ecs-and-spatial-hash.md`](../engine/ecs-and-spatial-hash.md)

### `environmental_signal` (activation condition kind)

An activation-condition predicate that evaluates whether the concentration of a named signal layer
at the emitting plant's cell meets or exceeds a configured `min_concentration` threshold. This
enables a plant to activate a defense in response to ambient signal concentrations deposited by
mycorrhizal relay or airborne diffusion from neighbouring plants, providing a mechanistic basis for
primed systemic acquired resistance.

See: [`engine/signaling.md`](../engine/signaling.md)

---

## F

### Flow Field

A scalar guidance surface computed at the beginning of each tick by `compute_flow_field()` from the
aggregate plant-energy layer and toxin layers. Positive values are associated with high local plant
energy (attractive); toxin contribution is subtractive (repulsive). Swarms sample this field to
select their next movement cell via `_choose_neighbour_by_flow_probability(...)`.

See: [`engine/flow-field.md`](../engine/flow-field.md)

---

## G

### Garbage Collection (GC)

The deferred bulk destruction of entity IDs that have been marked for removal. In PHIDS, dead
plants and dead swarms are collected into a `dead_*` list during a system pass, then destroyed in a
single `world.collect_garbage(ids)` call after the iteration loop completes. Immediate in-pass
`unregister_position` calls are used to revoke spatial-hash entries before GC, preventing ghost
lookups within the same tick.

See: [`engine/ecs-and-spatial-hash.md`](../engine/ecs-and-spatial-hash.md)

### Ghost Entity

An entity ID that has been logically killed (population zero, energy zero, or marked for removal)
but has not yet been removed from the spatial hash or ECS registry. Ghost entities corrupt O(1)
spatial-hash lookups because `world.entities_at(x, y)` returns their IDs as if they were still
alive. PHIDS prevents ghost entities through immediate `unregister_position` calls and same-tick GC
in both the interaction and signaling phases.

See: [`engine/ecs-and-spatial-hash.md`](../engine/ecs-and-spatial-hash.md),
[`engine/signaling.md`](../engine/signaling.md)

### `GridEnvironment`

The central environmental state store in `phids.engine.core.biotope`. It owns: aggregate plant
energy (`plant_energy_layer`), per-species energy layers, signal layers, toxin layers, wind fields,
and the scalar flow field. It is the concrete implementation of PHIDS's double-buffering strategy
for field-level state.

See: [`engine/biotope-and-double-buffering.md`](../engine/biotope-and-double-buffering.md)

---

## I

### Irreversible Defense

A substance configured with `irreversible=True`. Once activated, such a substance is pinned in the
active state and does not deactivate due to trigger loss or aftereffect expiry. This models a
systemic acquired resistance (SAR)-like permanent induced defense response.

See: [`engine/signaling.md`](../engine/signaling.md)

---

## L

### Lethality Rate

A `SubstanceComponent` parameter (`lethality_rate`) that scales the per-tick population casualties
inflicted on a swarm co-located with a non-zero toxin concentration:
`casualties = int(lethality_rate × toxin_value × population)`. A lethality rate of 0.0 means the
toxin is non-lethal (potentially only repellent).

See: [`engine/signaling.md`](../engine/signaling.md)

---

## M

### Metabolic Attrition

The process by which a swarm whose energy reserve falls below zero loses individuals proportional to
the magnitude of the deficit. Each lost individual "refunds" `energy_min` units of energy, and the
reserve is clamped to `0.0`. This models starvation as a smooth population shrinkage rather than
an abrupt all-or-nothing event.

See: [`engine/interaction.md`](../engine/interaction.md)

### Mitosis

The splitting of a swarm entity into two halves when its population reaches a configurable
threshold. The parent swarm retains `floor(n/2)` individuals; a new swarm entity is spawned with
the complementary half and equal share of energy. The parent's `initial_population` is reset to the
retained value, which re-anchors the future mitosis threshold.

See: [`engine/interaction.md`](../engine/interaction.md)

### Mycorrhizal Network

A set of explicitly tracked plant-to-plant connections stored in `PlantComponent.mycorrhizal_connections`.
Links are formed by the lifecycle system at a configurable interval when two plants of the same (or
different, if enabled) species occupy cells within a maximum distance. The signaling system uses
these links to relay signal concentrations to connected cells, modelling root-mediated chemical
communication.

See: [`engine/lifecycle.md`](../engine/lifecycle.md), [`engine/signaling.md`](../engine/signaling.md)

---

## O

### O(1) Spatial Hash

The spatial hash embedded in `ECSWorld` that maps `(x, y)` grid cells to sets of entity IDs in
amortized O(1) time. It is the primary locality primitive in PHIDS: all cell-local interactions
(feeding, trigger evaluation, crowding checks) are dispatched via `world.entities_at(x, y)` rather
than through O(N²) global pairwise scans.

See: [`engine/ecs-and-spatial-hash.md`](../engine/ecs-and-spatial-hash.md)

---

## R

### Replay Buffer (`ReplayBuffer`)

A msgpack-backed per-tick snapshot store in `phids.io.replay`. Each tick's environmental state is
serialized and appended to the buffer after telemetry recording. The buffer supports offline
replay, diff analysis, and export to external tooling.

See: [`telemetry/replay-and-termination-semantics.md`](../telemetry/replay-and-termination-semantics.md)

### Repellence / Repelled State

A swarm state flag (`repelled`, `repelled_ticks_remaining`) set either by chemical toxin defense
(signaling phase) or by crowding-induced dispersal (interaction phase). While repelled, the swarm
performs a random-walk step rather than following the flow field, and the timer decrements each
tick until it reaches zero.

See: [`engine/interaction.md`](../engine/interaction.md), [`engine/signaling.md`](../engine/signaling.md)

### Rule of 16

The project-wide pre-allocation invariant: flora species, herbivore species, and substance types are
bounded to a maximum of 16 each, as defined in `phids.shared.constants`. NumPy arrays are
pre-allocated to these maximum dimensions at simulation start, eliminating dynamic array resizing
(`np.append`) during the simulation loop and ensuring memory stability at hot-path boundaries.

See: [`foundations/index.md`](../foundations/index.md)

---

## S

### SAR (Systemic Acquired Resistance)

The biological phenomenon modelled by irreversible `SubstanceComponent` activations and by the
`environmental_signal` activation condition. In PHIDS, a plant that has been triggered once and is
configured as irreversible will maintain its defense permanently. A neighbouring plant configured
with `environmental_signal` activation can prime its own defense in response to relay-deposited
signal concentrations, approximating primed SAR.

See: [`engine/signaling.md`](../engine/signaling.md)

### `SIGNAL_EPSILON`

The subnormal-float truncation threshold defined in `phids.shared.constants`. After each diffusion
step, any signal layer value below `SIGNAL_EPSILON` is zeroed to preserve sparsity and prevent
numerical instability from accumulating subnormal floating-point values in otherwise-inactive
cells.

See: [`engine/biotope-and-double-buffering.md`](../engine/biotope-and-double-buffering.md)

### `SimulationConfig`

The Pydantic v2 validated schema (`phids.api.schemas`) that encodes all parameters for a simulation
run: grid dimensions, species definitions, diet matrix, trigger rules, initial placements, wind
conditions, mycorrhizal settings, and termination constraints. It is the single validated ingress
point for scenario data, after which internal state is treated as trusted.

See: [`scenarios/schema-and-curated-examples.md`](../scenarios/schema-and-curated-examples.md)

### `SimulationLoop`

The deterministic tick orchestrator in `phids.engine.loop`. It advances the ecological state
through a fixed phase sequence (flow field → camouflage → lifecycle → interaction → signaling →
telemetry → termination) under an `asyncio.Lock`, accumulates telemetry, appends replay snapshots,
and evaluates Z1–Z7 termination conditions each tick.

See: [`engine/index.md`](../engine/index.md)

### Spatial Hash

See [O(1) Spatial Hash](#o1-spatial-hash).

### `SubstanceComponent`

The ECS component representing a runtime instance of a volatile organic compound (VOC) or defensive
toxin. It encodes the owning plant ID, the target signal or toxin layer index, synthesis state,
activation state, aftereffect timer, lethality/repellence parameters, activation-condition tree,
and energy cost. Substances are materialized as discrete entities by the signaling system when a
trigger rule fires.

See: [`engine/signaling.md`](../engine/signaling.md)

### Surplus Energy

The energy a swarm holds above its `baseline_energy` (`energy − population × energy_min`). Only
surplus energy is convertible into new individuals during the interaction phase's reproduction step.

See: [`engine/interaction.md`](../engine/interaction.md), [Baseline Energy](#baseline-energy)

### Synthesis

The delay phase of a substance's lifecycle between materialization (trigger fires, entity created)
and activation (defense becomes effective). `synthesis_remaining` is decremented each tick the
trigger is satisfied; once it reaches zero and the activation condition passes, the substance
transitions to the active state.

See: [`engine/signaling.md`](../engine/signaling.md)

---

## T

### Telemetry Recorder (`TelemetryRecorder`)

The per-tick metric accumulator in `phids.telemetry.analytics`. It records aggregate flora energy,
flora and herbivore population counts, active substance counts, and per-category plant death causes
after each tick. Metrics are exposed via REST (`GET /api/telemetry`) and polled by the UI
diagnostics rail.

See: [`telemetry/analytics-and-export-formats.md`](../telemetry/analytics-and-export-formats.md)

### Termination Condition

A Z-coded stopping criterion evaluated at the end of each tick by `check_termination()`. The
currently implemented conditions are:

| Code | Description |
|------|-------------|
| Z1   | Maximum tick count reached |
| Z2   | Extinction of a configured flora species |
| Z3   | Extinction of all flora |
| Z4   | Extinction of a configured herbivore species |
| Z5   | Extinction of all herbivores |
| Z6   | Total flora energy exceeds a maximum threshold |
| Z7   | Total herbivore population exceeds a maximum threshold |

See: [`telemetry/replay-and-termination-semantics.md`](../telemetry/replay-and-termination-semantics.md)

### TILE_CARRYING_CAPACITY

See [Carrying Capacity](#carrying-capacity-tile_carrying_capacity).

### Trigger Rule

A JSON-encoded rule attached to a flora species that specifies the predicate under which a given
`SubstanceComponent` is materialized and kept synthesizing. A trigger rule encodes a herbivore
species ID, a minimum population threshold, an optional nested activation condition, and the
substance parameters that should be instantiated. Multiple trigger rules per `(flora, substance)`
pair are supported.

See: [`scenarios/scenario-authoring-and-trigger-semantics.md`](../scenarios/scenario-authoring-and-trigger-semantics.md)

### Toxin

A `SubstanceComponent` with `is_toxin=True`. Unlike signal-type substances, toxins do not undergo
airborne Gaussian diffusion. They are point-emitter defenses that emit into and act on the local
toxin layer at the emitting plant's cell. Their effects on swarms (lethal casualties, repellence)
are enforced exclusively in the signaling phase by `_apply_toxin_to_swarms`.

See: [`engine/signaling.md`](../engine/signaling.md)

---

## V

### Velocity

A `SwarmComponent` parameter that encodes the movement period in ticks (not a spatial speed). A
velocity of `n` means the swarm navigates once every `n` ticks; between navigation events,
`move_cooldown` is decremented and no movement occurs. Velocity also scales feeding consumption
(`consumption_rate / velocity`) to prevent high-frequency movers from extracting disproportionate
energy per tick.

See: [`engine/interaction.md`](../engine/interaction.md)

### VOC (Volatile Organic Compound)

The biological archetype for non-toxin `SubstanceComponent` instances. VOC signals are emitted into
signal layers, diffuse through the environment via Gaussian convolution, and can be detected by the
`environmental_signal` activation condition. They model airborne alarm volatiles such as green leaf
volatiles and terpenes.

See: [`engine/signaling.md`](../engine/signaling.md)

---

## W

### WebSocket Streams

PHIDS exposes two intentionally distinct WebSocket endpoints:

- `/ws/simulation/stream` — emits full per-tick environment snapshots encoded as msgpack + zlib,
  suitable for programmatic replay or external analysis,
- `/ws/ui/stream` — emits lightweight JSON payloads optimized for canvas rendering in the browser
  control center.

See: [`interfaces/rest-and-websocket-surfaces.md`](../interfaces/rest-and-websocket-surfaces.md)

### Wind Field

A uniform 2D velocity vector (`wind_x`, `wind_y`) configured at scenario load and stored in
`GridEnvironment`. It biases the Gaussian diffusion kernel for airborne signal transport, modelling
directional atmospheric transport of volatile signals. The wind vector can be updated at runtime via
`PUT /api/wind`.

See: [`engine/flow-field.md`](../engine/flow-field.md),
[`interfaces/rest-and-websocket-surfaces.md`](../interfaces/rest-and-websocket-surfaces.md)
