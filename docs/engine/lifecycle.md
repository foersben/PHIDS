# Lifecycle

The lifecycle system governs plant-centered ecological change in PHIDS. It is the phase in which
flora grow, attempt reproduction, prune stale root-network references, die when energy falls below
survival limits, and gradually extend mycorrhizal connectivity.

This chapter documents the current implementation in `src/phids/engine/systems/lifecycle.py`.

## Role in the Engine

`run_lifecycle()` executes after flow-field generation and camouflage attenuation but before swarm
interaction and signaling.

This ordering matters. The lifecycle phase updates plant state first so that:

- later feeding decisions observe current plant energy,
- later signaling decisions observe the plant population that survived the lifecycle pass,
- the aggregate plant-energy layer is rebuilt before subsequent phases depend on it.

## Runtime Inputs

The lifecycle system currently consumes:

- `ECSWorld` for plant entities and spatial occupancy,
- `GridEnvironment` for plant-energy writes and layer rebuilds,
- `tick` for growth and reproduction timing,
- flora species parameter lookups,
- mycorrhizal settings from the simulation config.

## Principal Responsibilities

In its current form, `run_lifecycle()` performs the following tasks:

1. apply growth to each plant,
2. attempt reproduction when interval and energy constraints permit,
3. write current plant energy into the environment,
4. prune dead mycorrhizal links,
5. identify and unregister dead plants,
6. optionally establish one new mycorrhizal link,
7. garbage-collect dead plants,
8. rebuild the aggregate plant-energy layer.

## Plant Runtime Model

The lifecycle system operates on `PlantComponent`, which currently stores:

- spatial coordinates,
- current energy,
- max energy,
- base energy,
- growth rate,
- survival threshold,
- reproduction interval,
- seed dispersal bounds,
- seed energy cost,
- camouflage settings,
- `last_reproduction_tick`,
- `mycorrhizal_connections`.

This means lifecycle is the phase that primarily updates the long-term state trajectory of plant
entities.

## Growth Model

The helper `_grow(plant, tick)` applies the current growth rule:

- `new_energy = plant.base_energy * (1.0 + plant.growth_rate / 100.0 * tick)`
- `plant.energy = min(new_energy, plant.max_energy)`

Important current-state implication:

- growth is tied to `base_energy` and the current tick,
- the result is clamped to the species-specific maximum.

This is a deterministic plant-energy update, not an incremental random drift.

## Reproduction Model

Reproduction is handled by `_attempt_reproduction(...)`.

A plant may attempt reproduction only if:

- enough ticks have elapsed since `last_reproduction_tick`, and
- the plant has at least `seed_energy_cost` energy.

Current behavior includes several important details.

### Energy is spent regardless of success

When a plant is eligible, the seed energy cost is deducted before the system knows whether
reproduction will succeed.

### Dispersal is stochastic but bounded

The target seed location is chosen using:

- a random angle,
- a random distance in `[seed_min_dist, seed_max_dist]`.

### Germination is occupancy-constrained

If the target cell is out of bounds or already contains a plant, the reproduction attempt fails and
no offspring is created.

### Offspring are spawned as new ECS entities

When reproduction succeeds, the lifecycle system creates a new `PlantComponent`, registers it in the
spatial hash, and writes its initial energy into the environment.

## Mycorrhizal Networking

The lifecycle phase is also responsible for establishing new mycorrhizal links.

### Growth cadence

The helper `_should_attempt_mycorrhizal_growth(tick, growth_interval_ticks)` determines whether the
current lifecycle pass is allowed to form a new root connection.

Current semantics:

- no new link is attempted on most ticks,
- the first attempt occurs only after the configured interval has elapsed,
- an interval of `1` permits an attempt every tick.

### Deterministic connection ordering

When root growth is attempted, `_establish_mycorrhizal_connections(...)`:

- collects current plants,
- excludes plants already marked dead in this pass,
- sorts plants deterministically by `(y, x, species_id, entity_id)`,
- only checks forward neighbors `(1, 0)` and `(0, 1)`.

This ensures gradual, deterministic network formation rather than uncontrolled saturation.

### At most one new link per allowed attempt

The current implementation establishes **at most one** new root link per invocation.

This is one of the most important current-state properties of the mycorrhizal model.

### Link costs

Both participating plants must be able to pay `connection_cost`. When the link is formed:

- each plant loses the configured energy amount,
- both plants receive the bidirectional connection,
- the updated energies are written into the environment.

### Species restrictions

When `inter_species` is false, mycorrhizal links are limited to plants of the same species.

## Death and Culling

After growth, reproduction, and energy update, lifecycle checks whether:

- `plant.energy < plant.survival_threshold`

If so, the current implementation:

- clears the plant’s energy contribution in the environment write buffer,
- unregisters the plant from the spatial hash,
- marks the plant for later garbage collection.

Actual destruction is deferred until after the full plant pass completes.

## Read/Write Boundary

Lifecycle mutates plant components in place, but it updates environmental plant energy through the
biotope write-side helpers:

- `env.set_plant_energy(...)`
- `env.clear_plant_energy(...)`
- `env.rebuild_energy_layer()`

This is another example of PHIDS’s current hybrid model:

- entity state is updated directly within the phase,
- field visibility is synchronized through buffered environmental rebuilds.

## Ordering Nuances

Several ordering details are important to document explicitly.

### Reproduction precedes root-growth attempt

In the current implementation, reproduction happens during the plant iteration before the optional
mycorrhizal growth attempt at the end of the phase.

### Dead plants are excluded from new root links

Plants marked dead during the pass are excluded from mycorrhizal link formation even before garbage
collection occurs.

### Layer rebuild occurs once per lifecycle pass

The environment’s aggregate plant-energy layer is rebuilt only after all lifecycle updates and dead
entity cleanup are complete.

## Evidence from Tests

The current test suite verifies several important lifecycle behaviors.

### Mycorrhizal connection cost and bidirectionality

Tests verify that adjacent plants can form links, pay energy cost, and receive reciprocal
connections.

### Inter-species connection restrictions

Tests verify that the inter-species switch blocks cross-species links when disabled.

### One-link-per-interval growth

Tests verify that no links form before the configured interval and that only one new link is added
per permitted growth opportunity.

### Environmental energy rebuild behavior

Invariant tests verify that plant-energy writes become visible only after `rebuild_energy_layer()`
and that clearing plant energy is reflected after rebuild.

### Reproduction and scenario helpers

Additional coverage tests exercise reproduction and scenario helpers that feed lifecycle behavior.

## Methodological Limits of the Current Lifecycle Model

The lifecycle system should be described precisely rather than idealized.

- reproduction uses randomness for seed direction and distance,
- the current growth formula depends on `base_energy` and global tick rather than on a purely local
  incremental energy differential,
- mycorrhizal growth is deterministic in order and cadence but intentionally very conservative,
- lifecycle mutates components in place while synchronizing field state through biotope rebuilds.

These are part of the current engine model.

## Verified Current-State Evidence

- `src/phids/engine/systems/lifecycle.py`
- `src/phids/engine/components/plant.py`
- `src/phids/engine/loop.py`
- `tests/test_systems_behavior.py`
- `tests/test_schemas_and_invariants.py`
- `tests/test_additional_coverage.py`

## Where to Read Next

- For the swarm-centered phase that follows lifecycle: [`interaction.md`](interaction.md)
- For root-network signal transfer after lifecycle: [`signaling.md`](signaling.md)
- For buffered plant-energy visibility: [`biotope-and-double-buffering.md`](biotope-and-double-buffering.md)
