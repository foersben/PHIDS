# ECS and Spatial Hash

`ECSWorld` is the discrete-state backbone of PHIDS. It stores entities, indexes components, and
maintains the spatial hash that lets the engine ask local ecological questions without resorting to
global pairwise scans.

This chapter documents the current implementation in `src/phids/engine/core/ecs.py`.

## Role in the Engine

PHIDS does not model organisms as behavior-rich object hierarchies. Instead, it uses a lightweight
Entity-Component-System structure in which:

- an `Entity` is primarily an ID plus attached components,
- components hold state,
- systems operate over sets of entities possessing particular component types.

`ECSWorld` is the registry that makes this architecture operational.

## Core Responsibilities

In current implementation, `ECSWorld` owns:

- entity allocation through `_next_id`,
- entity storage through `_entities`,
- per-component indexing through `_component_index`,
- spatial occupancy through `_spatial_hash`.

These responsibilities make it the canonical owner of discrete ecological state.

## Entity Model

The current `Entity` type is intentionally minimal:

- `entity_id`
- `_components: dict[type[Any], Any]`

This reflects the project’s data-oriented philosophy. An entity is not a simulation object with its
own complex methods; it is an identity to which typed state bundles are attached.

## Component Indexing

When components are added via `add_component()`, `ECSWorld` updates `_component_index` so that
queries by component type remain efficient.

This allows the runtime to express system passes like:

- `world.query(PlantComponent)`
- `world.query(SwarmComponent)`
- `world.query(SubstanceComponent)`

without scanning arbitrary Python data structures.

## Query Semantics

The method `query(*component_types)` yields entities possessing all requested component types.

Its current implementation:

- starts from the smallest indexed component set,
- checks membership of the remaining component types,
- yields matching entities.

This is an important current-state detail because it gives PHIDS a simple but meaningful query
optimization while remaining easy to reason about.

## Spatial Hash Model

The spatial hash is implemented as:

- `_spatial_hash: dict[tuple[int, int], set[int]]`

mapping grid coordinates to the set of entity IDs occupying that cell.

This provides the locality structure used by multiple systems.

## Current Spatial Operations

### `register_position(entity_id, x, y)`

Adds the entity to the occupancy set for the given cell.

### `unregister_position(entity_id, x, y)`

Removes the entity from the occupancy set for the given cell.

### `move_entity(entity_id, old_x, old_y, new_x, new_y)`

Performs an atomic-looking update by unregistering the old position and registering the new one.

### `entities_at(x, y)`

Returns the set of entity IDs occupying the requested cell.

## Why the Spatial Hash Matters

The spatial hash is not a micro-optimization. It is one of PHIDS’s architectural invariants.

It enables local ecological reasoning such as:

- whether swarms and plants co-occupy a cell for feeding,
- whether predator presence at a plant cell should trigger a substance,
- how many entities occupy a single cell,
- where movement and death updates must adjust occupancy.

Without this structure, the engine would drift toward the prohibited pattern of broad pairwise
search.

## Consumers in Current Systems

### Interaction system

`run_interaction()` uses `world.entities_at(swarm.x, swarm.y)` to find co-located plants for
feeding. This is a direct example of locality-preserving ecology logic.

### Signaling system

`run_signaling()` aggregates predator population at a plant cell by traversing `world.entities_at`
for that coordinate. This allows trigger thresholds to be evaluated by co-location rather than by
searching the whole world.

### Lifecycle and garbage collection

Lifecycle and interaction phases unregister dead entities from the spatial hash before garbage
collection so the locality structure remains consistent with the active world.

## Multiple Occupancy Is Allowed

The spatial hash stores a set of IDs per cell, not a single occupant. This is important because the
PHIDS model explicitly allows multiple entities to occupy the same coordinate when ecologically
relevant.

For example, multiple swarms can co-occupy a cell, and swarms can share a cell with a plant.

## Destruction and Cleanup

When `destroy_entity()` is called, `ECSWorld` currently:

- removes the entity from `_entities`,
- removes the entity from all indexed component sets,
- removes the entity ID from all spatial-hash cell sets.

The current implementation notes that this spatial cleanup searches all cells, which is acceptable
for the project’s bounded and sparse grids.

## Garbage Collection

`collect_garbage(dead_entity_ids)` simply calls `destroy_entity()` for each listed entity.

This keeps destruction explicit at the system layer while consolidating cleanup behavior in one
world-owned operation.

## Evidence from Tests

The current tests verify several important ECS and spatial-hash properties.

### Movement and garbage collection

`tests/test_ecs_world.py` verifies that registration, movement, and garbage collection correctly
update occupancy.

### Query intersection and component removal

`tests/test_schemas_and_invariants.py` verifies that intersection queries return only entities with
all requested components and that removing a component updates the query result.

### Multiple occupancy

`tests/test_schemas_and_invariants.py` also verifies that multiple entity IDs may occupy the same
cell.

### Benchmark expectation

`tests/test_spatial_hash_benchmark.py` treats hot-cell queries as benchmark-sensitive behavior,
reinforcing that locality lookups are part of the project’s performance contract.

## Methodological Limits of the Current ECS

The current ECS should be described precisely:

- entities are lightweight but still stored in Python dictionaries,
- component cleanup is centralized and explicit,
- spatial cleanup on entity destruction searches all cells rather than maintaining a reverse index,
- the architecture is optimized for clarity, bounded state, and locality rather than for maximal
  generic ECS abstraction.

These traits are part of the current PHIDS design, not deviations from it.

## Verified Current-State Evidence

- `src/phids/engine/core/ecs.py`
- `src/phids/engine/systems/interaction.py`
- `src/phids/engine/systems/signaling.py`
- `tests/test_ecs_world.py`
- `tests/test_schemas_and_invariants.py`
- `tests/test_spatial_hash_benchmark.py`

## Where to Read Next

- For field-side environmental state: [`biotope-and-double-buffering.md`](biotope-and-double-buffering.md)
- For how movement consumes a global field instead of pairwise search: [`flow-field.md`](flow-field.md)
- For the engine-wide orchestration context: [`index.md`](index.md)
