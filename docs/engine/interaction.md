# Interaction

The interaction system governs swarm-centered ecological behavior in PHIDS. It is the phase in
which herbivore swarms move, feed, suffer starvation or toxin losses, convert stored energy into new
individuals, and split by mitosis when they exceed their current reproduction threshold.

This chapter documents the current implementation in `src/phids/engine/systems/interaction.py`.

## Role in the Engine

`run_interaction()` executes after lifecycle and before signaling.

This ordering means that interaction currently consumes:

- the flow field generated at the beginning of the tick,
- the post-lifecycle plant distribution and plant-energy field,
- the current toxin layers already present at that point in the tick.

It also means that signaling observes the post-interaction world, including any feeding damage,
movement, starvation, or swarm growth that happened during interaction.

## Swarm Runtime Model

The interaction system operates on `SwarmComponent`, which currently stores:

- spatial coordinates,
- population,
- `initial_population`,
- energy reserve,
- `energy_min`,
- movement `velocity`,
- `consumption_rate`,
- `starvation_ticks`,
- repelled-state flags,
- `target_plant_id`,
- `move_cooldown`.

This is the phase in which most of those fields change over time.

## Principal Responsibilities

In its current implementation, `run_interaction()` performs the following tasks:

1. update movement cooldowns,
2. move swarms via the global flow field or repelled random walk,
3. resolve plant feeding through the spatial hash and diet matrix,
4. apply toxin casualties from toxin layers,
5. apply starvation attrition,
6. cull dead swarms,
7. convert stored energy into new individuals,
8. trigger mitosis when the population threshold is met,
9. garbage-collect dead swarms,
10. rebuild the plant-energy layer.

## Movement Model

### Cooldown-based motion

Movement is not evaluated on every tick for every swarm. Instead, the current implementation uses
`move_cooldown` and `velocity`.

- if `move_cooldown > 0`, the swarm does not navigate and the cooldown is decremented,
- otherwise, the swarm selects a new destination and the cooldown is reset to `velocity - 1`.

This means velocity is represented as a movement period in ticks rather than as a continuous speed.

### Flow-field pursuit

Normal movement uses `_choose_neighbour_by_flow_probability(...)`, which now deterministically
compares the current cell with its 4-connected neighbors and chooses the highest flow-field value,
retaining the current cell on ties.

This is the interaction phase’s principal dependence on the global flow field.

### Repelled random walk

When a swarm is repelled and still has `repelled_ticks_remaining > 0`, movement switches to
`_random_walk_step(...)`.

Current behavior:

- a random valid adjacent cell is chosen,
- the repelled timer decreases,
- once the timer expires, `repelled` is cleared and `target_plant_id` is reset.

This gives PHIDS a local fleeing behavior without requiring a separate pathfinding subsystem.

## Feeding Model

After movement, the interaction phase attempts feeding by examining all entities at the swarm’s
current cell.

### Spatial-hash locality

Feeding uses:

- `world.entities_at(swarm.x, swarm.y)`

This is a direct expression of the project’s locality invariant: feeding is resolved by co-location,
not by global search.

### Diet-matrix gating

A swarm may only feed on a co-located plant if the diet matrix allows the predator species to
consume the plant species.

### Consumption rule

Current consumption is:

- `min(swarm.consumption_rate * swarm.population, plant.energy)`

The consumed energy is removed from the plant and added to the swarm.

### Starvation reset

If feeding occurs:

- `swarm.starvation_ticks` is reset to `0`.

### Plant death during feeding

If feeding reduces the plant below its survival threshold, the plant is:

- cleared from the plant-energy layer,
- unregistered from the spatial hash,
- garbage-collected immediately.

This means the interaction phase can directly remove plants from the world.

## Starvation Model

If no compatible food source is found at the swarm’s cell, the swarm’s `starvation_ticks`
increase.

Later in the pass, if starvation has lasted more than one tick, the swarm suffers attrition:

- `max(1, int(swarm.population * 0.05 * swarm.starvation_ticks))`

This makes starvation cumulative rather than a simple binary alive/dead condition.

## Toxin Damage Model

The current interaction system also applies toxin casualties directly from `env.toxin_layers`.

For each toxin layer at the swarm’s current position:

- toxin concentration is read,
- casualties are computed as `int(toxin_val * swarm.population * TOXIN_CASUALTY_FACTOR)`,
- population is reduced accordingly.

This is an important current-state coupling: toxin effects are not confined entirely to the
signaling module. Interaction also applies concentration-based toxin damage.

## Death and Garbage Collection

If a swarm’s population falls to zero or below, the interaction system:

- unregisters it from the spatial hash,
- marks it for removal,
- skips the remainder of the pass for that swarm.

Actual destruction is deferred until after the loop over swarms completes.

## Reproduction by Energy Conversion

If the swarm survives, the interaction phase next converts stored energy into new individuals.

Current rule:

- `new_individuals = int(swarm.energy // swarm.energy_min)`

When positive:

- population is incremented,
- the corresponding energy is subtracted.

This means PHIDS currently models one form of reproduction as energy-to-individual conversion within
a single swarm.

## Mitosis

After energy-based reproduction, interaction may trigger `_perform_mitosis(...)` if:

- `swarm.population >= 2 * swarm.initial_population`

Current mitosis behavior:

- the swarm population is split into retained and offspring halves,
- the parent’s `initial_population` is reset to its retained population,
- energy is divided equally,
- a new swarm entity is spawned at the same cell.

This means `initial_population` is not merely historical metadata; it directly shapes future mitosis
thresholds.

## Read/Write Boundary

The interaction phase follows the current hybrid PHIDS model.

It mutates swarm and plant components in place, but it synchronizes plant-energy field visibility
through `GridEnvironment` helpers such as:

- `env.set_plant_energy(...)`
- `env.clear_plant_energy(...)`
- `env.rebuild_energy_layer()`

Thus interaction is not purely entity-local; it is a coordinated entity-plus-field phase.

## Ordering Nuances

Several ordering details matter.

### Movement precedes feeding

The swarm may change cell before feeding is attempted. Feeding therefore occurs at the post-move
location, not the pre-move location.

### Toxin damage follows feeding

The current implementation applies toxin-layer casualties after feeding and starvation bookkeeping.

### Reproduction precedes mitosis

Energy-based reproduction is applied before the mitosis threshold is checked. This means same-tick
reproduction can push a swarm over the mitosis threshold.

## Evidence from Tests

The current test suite verifies several important interaction behaviors.

### Diet incompatibility blocks feeding

Tests verify that incompatible diet-matrix entries prevent plant consumption and increase starvation.

### Same-tick reproduction and mitosis

Tests verify that energy-based growth can trigger mitosis in the same interaction pass.

### Odd-population mitosis conservation

Tests verify that population is conserved correctly when splitting an odd-sized swarm.

### Repelled random walk

Tests verify that a repelled swarm performs a random-walk step and decrements its repelled timer.

### Integration with lifecycle and signaling

Broader system tests confirm that interaction participates correctly in the overall tick pipeline.

## Methodological Limits of the Current Interaction Model

The interaction system should be documented precisely.

- movement uses 4-connected local comparison rather than long-range route planning,
- feeding is strictly co-location based,
- toxin effects are split across interaction and signaling,
- reproduction combines direct energy-to-individual conversion with a separate mitosis mechanism,
- component state is mutated in place while field visibility is synchronized through environmental
  rebuilds.

These are part of the current PHIDS runtime model.

## Verified Current-State Evidence

- `src/phids/engine/systems/interaction.py`
- `src/phids/engine/components/swarm.py`
- `src/phids/engine/core/ecs.py`
- `src/phids/engine/core/flow_field.py`
- `tests/test_systems_behavior.py`
- `tests/test_termination_and_loop.py`
- `tests/test_additional_coverage.py`

## Where to Read Next

- For the global guidance field consumed by movement: [`flow-field.md`](flow-field.md)
- For the plant-centered phase that precedes interaction: [`lifecycle.md`](lifecycle.md)
- For the signaling phase that follows interaction: [`signaling.md`](signaling.md)
