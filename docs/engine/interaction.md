# Interaction

The interaction system governs swarm-centered ecological behavior in PHIDS. It is the phase in
which herbivore swarms move, feed, pay metabolic upkeep, convert stored energy into new
individuals, and split by mitosis when they exceed their configured population threshold.

This chapter documents the current implementation in `src/phids/engine/systems/interaction.py`.

## Role in the Engine

`run_interaction()` executes after lifecycle and before signaling.

This ordering means that interaction currently consumes:

- the flow field generated at the beginning of the tick,
- the post-lifecycle plant distribution and plant-energy field,
- any repelled state previously written onto swarms by signaling.

It also means that signaling observes the post-interaction world, including any feeding damage,
movement, metabolic losses, or swarm growth that happened during interaction.

## Swarm Runtime Model

The interaction system operates on `SwarmComponent`, which currently stores:

- spatial coordinates,
- population,
- `initial_population`,
- energy reserve,
- `energy_min`,
- movement `velocity`,
- `consumption_rate`,
- `energy_upkeep_per_individual`,
- `split_population_threshold`,
- repelled-state flags,
- `target_plant_id`,
- `move_cooldown`.

This is the phase in which most of those fields change over time.

## Principal Responsibilities

In its current implementation, `run_interaction()` performs the following tasks:

1. update movement cooldowns,
2. move swarms via the global flow field or repelled random walk,
3. resolve plant feeding through the spatial hash and diet matrix,
4. apply metabolic upkeep and deficit-driven attrition,
5. cull dead swarms,
6. convert stored energy into new individuals,
7. trigger mitosis when the population threshold is met,
8. garbage-collect dead swarms,
9. rebuild the plant-energy layer.

## Movement Model

### Cooldown-based motion

Movement is not evaluated on every tick for every swarm. Instead, the current implementation uses
`move_cooldown` and `velocity`.

- if `move_cooldown > 0`, the swarm does not navigate and the cooldown is decremented,
- otherwise, the swarm selects a new destination and the cooldown is reset to `velocity - 1`.

This means velocity is represented as a movement period in ticks rather than as a continuous speed.

### Crowding-induced dispersal

Before selecting a movement target, the interaction system evaluates aggregate population pressure
at the swarm's current cell via `_co_located_swarm_population(world, x, y)`.

This helper sums the `population` attribute of every `SwarmComponent` occupying a given cell,
performing an O(N)-over-occupants scan via the spatial hash rather than a global O(N²) scan over all
swarms. The result is compared against the module-level carrying-capacity constant:

- `TILE_CARRYING_CAPACITY = 500`

If the total biological population at the cell exceeds this threshold, the swarm is involuntarily
repelled and assigned `repelled_ticks_remaining = 1`, initiating one random-walk dispersal step.

Two details distinguish this model from the chemical repellence pathway:

1. the crowding check is evaluated against aggregate **individual count** across all co-located
   swarms, not against the number of swarm entities, thereby correctly reflecting biological
   density rather than entity-graph cardinality,
2. the threshold is a carrying-capacity constant, so the model remains meaningful as individual
   swarm populations grow through energy-based reproduction.

### Flow-field pursuit

Normal movement uses `_choose_neighbour_by_flow_probability(...)`, which builds a local
4-connected candidate set and samples the next cell using probability weights derived from
flow-field values.

Implementation details:

- candidate scores are shifted to positive weights so toxin-driven negative values remain valid,
- higher flow values are still preferred, but not selected as a strict greedy argmax,
- this allows co-located swarms to naturally de-phase over subsequent ticks instead of remaining
  permanently lockstepped.

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

After movement, the interaction phase attempts feeding by examining all entities at the swarm's
current cell.

### Spatial-hash locality

Feeding uses:

- `world.entities_at(swarm.x, swarm.y)`

This is a direct expression of the project's locality invariant: feeding is resolved by co-location,
not by global search.

### Stale-entity guard

Before inspecting each co-located entity, the feeding loop calls `world.has_entity(co_eid)` as a
defensive validity check. This guard defends against reference-invalidation errors that arise when
a plant entity was garbage-collected mid-iteration — either because another swarm killed it earlier
in the same tick's feeding pass, or because the lifecycle phase queued it for removal at a
different point in the same tick.

Without this guard, a stale entity ID returned by the spatial hash would cause a `KeyError` in
`world.get_entity(co_eid)`. With the guard, such entries are skipped atomically and the feeding
pass remains safe.

### Diet-matrix gating

A swarm may only feed on a co-located plant if the diet matrix allows the predator species to
consume the plant species.

### Consumption rule

Current consumption is velocity-adjusted to prevent high-frequency movers from extracting
disproportionate energy per tick:

- `consumed = min((consumption_rate / velocity) * population, plant.energy)`

The consumed energy is removed from the plant and added to the swarm's energy reserve.

### Plant death during feeding

If feeding reduces the plant below its survival threshold, the plant is:

- cleared from the plant-energy layer,
- unregistered from the spatial hash,
- garbage-collected immediately.

This means the interaction phase can directly remove plants from the world.

## Energy Economy Model

The interaction phase now uses a continuous reserve model instead of a starvation tick counter.

After movement/feeding, each swarm pays metabolic upkeep:

- `population * energy_min * energy_upkeep_per_individual`

If this drives `swarm.energy` below zero, the deficit is converted into casualties based on
`energy_min`, and energy is clamped back to `0.0`.

This creates a smooth depletion-and-recovery cycle where population and intake capacity naturally
co-evolve over time.

## Toxin Interaction Boundary

Direct toxin casualties are no longer resolved inside `run_interaction()`.

Instead, the signaling phase is the sole authority for toxin lethality and repellence because it has
access to the full `SubstanceComponent` configuration for each active defense. Interaction only
observes resulting swarm state such as reduced population or active repelled-walk timers.

## Death and Garbage Collection

If a swarm’s population falls to zero or below, the interaction system:

- unregisters it from the spatial hash,
- marks it for removal,
- skips the remainder of the pass for that swarm.

Actual destruction is deferred until after the loop over swarms completes.

## Reproduction by Energy Conversion

If the swarm survives metabolic upkeep and the death check, the interaction phase next converts
accumulated surplus energy into new individuals using a reserve-above-baseline rule.

The key invariant is that reproduction is only funded from energy **above** what the current
population strictly requires to remain at minimum viability:

1. `baseline_energy = population × energy_min`
2. `surplus = energy − baseline_energy`
3. `cost_per_offspring = energy_min × reproduction_energy_divisor`
4. `new_individuals = int(surplus // cost_per_offspring)`

When `new_individuals > 0`:

- the swarm's population is incremented by that count,
- the corresponding cost (`new_individuals × cost_per_offspring`) is subtracted from the energy
  reserve.

This model has two important ecological consequences that distinguish it from a naive
energy-divided-by-minimum rule:

- a large swarm requires proportionally more reserve energy before any growth occurs, preventing a
  "sterile mega-swarm" artifact where an enormous but barely-fed population would reproduce purely
  on the grounds that `energy > energy_min`,
- `reproduction_energy_divisor` acts as a species-level efficiency parameter: higher values make
  reproduction more expensive per offspring and therefore slow population growth relative to energy
  intake.

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

### Movement and feeding are mutually exclusive per tick

If a swarm moves during its interaction step, feeding is skipped for that swarm in the same tick.
Only swarms that remain in place are eligible to feed.

This enforces a strict per-tick action budget (`move` XOR `eat`) and removes same-tick
"move-then-consume" behavior.

### Toxin damage follows feeding

The current implementation applies toxin-layer casualties after feeding and before metabolic upkeep.

### Reproduction precedes mitosis

Energy-based reproduction is applied before the mitosis threshold is checked. This means same-tick
reproduction can push a swarm over the mitosis threshold.

### Split threshold behavior

Mitosis uses `split_population_threshold` when configured (`> 0`). Otherwise, interaction falls back
to the legacy `2 * initial_population` threshold.

## Evidence from Tests

The current test suite verifies several important interaction behaviors.

### Diet incompatibility blocks feeding

Tests verify that incompatible diet-matrix entries prevent plant consumption and can push swarms into
energy deficit and attrition.

### Reproduction divisor limits growth rate

Tests verify that `reproduction_energy_divisor` correctly modulates the number of offspring
produced per tick, with higher divisors yielding fewer new individuals for the same surplus energy.

### Crowding triggers dispersal above carrying capacity

Tests verify that co-located swarms whose aggregate biological population exceeds
`TILE_CARRYING_CAPACITY` are moved via random walk rather than following the flow field, and that
swarms below the threshold continue gradient-following navigation.

### Stale-entity guard prevents crash on mid-tick plant death

Tests verify that the feeding loop safely skips entity IDs that have been garbage-collected
mid-iteration due to another swarm feeding on the same plant in the same tick.

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
