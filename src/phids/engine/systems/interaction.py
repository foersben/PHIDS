"""Interaction system: swarm gradient navigation, herbivory, metabolic attrition, and mitosis.

This module implements the second of three ordered per-tick simulation phases in the PHIDS engine.
The interaction phase resolves all predator-flora encounters after plant lifecycle dynamics have
been committed to the energy layers, but before chemical-defense substances are emitted and
diffused. This ordering ensures that herbivory is computed against the most recent plant energy
state and that toxin effects on the interaction phase's movement decisions are propagated via the
flow-field gradient rather than through direct component access.

Swarm movement is governed by probabilistic sampling over 4-connected neighbourhood candidates
weighted by the scalar flow-field gradient. When the field is locally flat (gradient range below
1e-6), movement inertia encoded in ``SwarmComponent.last_dx / last_dy`` is used to maintain a
directional bias, preventing erratic Brownian behaviour in field-free zones. Tile carrying
capacity (``TILE_CARRYING_CAPACITY``) imposes a local crowding pressure: swarms exceeding the
tile limit enter a transient random-walk dispersal phase analogous to habitat saturation-driven
emigration. Herbivory is applied only to stationary swarms (those that did not relocate during
the current tick) via O(1) spatial hash lookups; the diet-compatibility matrix gates energy
transfer between each predator–flora species pair. Metabolic attrition deducts per-individual
upkeep energy each tick; deficits result in population casualties computed as
``ceil(deficit / energy_min)``. Reproduction converts surplus energy above the swarm-baseline
threshold into new individuals at cost ``energy_min × reproduction_energy_divisor``. Mitosis
splits an oversized swarm into two equal halves and registers the offspring entity in the ECS
world and spatial hash via ``_perform_mitosis``.
"""

from __future__ import annotations

import random

import numpy as np
import numpy.typing as npt

from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld


TILE_CARRYING_CAPACITY = 500


def _accumulate_tile_population(
    tile_populations: dict[tuple[int, int], int],
    x: int,
    y: int,
    delta: int,
) -> None:
    """Apply a signed population delta to one tile-population cache entry."""
    pos = (x, y)
    next_population = tile_populations.get(pos, 0) + delta
    if next_population > 0:
        tile_populations[pos] = next_population
    else:
        tile_populations.pop(pos, None)


def _choose_neighbour_by_flow_probability(
    swarm: SwarmComponent,
    flow_field: npt.NDArray[np.float64],
    width: int,
    height: int,
    invert: bool = False,
) -> tuple[int, int]:
    """Choose a 4-connected neighbour (or current cell) from flow-weighted probabilities.

    Args:
        swarm: Swarm component containing current coordinates and movement inertia.
        flow_field: Scalar attraction field.
        width: Grid width.
        height: Grid height.
        invert: When True, prefer lower gradients (flee behaviour).

    Returns:
        tuple[int, int]: Selected (nx, ny) cell to move to.
    """
    x, y = swarm.x, swarm.y
    candidates: list[tuple[int, int]] = [(x, y)]
    if x > 0:
        candidates.append((x - 1, y))
    if x < width - 1:
        candidates.append((x + 1, y))
    if y > 0:
        candidates.append((x, y - 1))
    if y < height - 1:
        candidates.append((x, y + 1))

    scores = [
        float(flow_field[candidate_x, candidate_y]) for candidate_x, candidate_y in candidates
    ]
    max_score = max(scores)
    min_score = min(scores)

    # Flat fields provide no directional signal; preserve prior heading as inertia.
    if max_score - min_score < 1e-6:
        if swarm.last_dx == 0 and swarm.last_dy == 0:
            return random.choice(candidates)

        target_x = x + swarm.last_dx
        target_y = y + swarm.last_dy
        weights: list[float] = []
        for candidate_x, candidate_y in candidates:
            if candidate_x == target_x and candidate_y == target_y:
                weights.append(10.0)
            else:
                weights.append(1.0)
        return random.choices(candidates, weights=weights, k=1)[0]

    adjusted_scores = [-score for score in scores] if invert else scores
    min_score = min(adjusted_scores)
    weights = [(score - min_score) + 1e-6 for score in adjusted_scores]
    return random.choices(candidates, weights=weights, k=1)[0]


def _random_walk_step(
    x: int,
    y: int,
    width: int,
    height: int,
) -> tuple[int, int]:
    """Return a random valid adjacent cell.

    Args:
        x: Current X coordinate.
        y: Current Y coordinate.
        width: Grid width.
        height: Grid height.

    Returns:
        tuple[int, int]: Randomly chosen adjacent cell (or same cell).
    """
    candidates: list[tuple[int, int]] = [(x, y)]
    if x > 0:
        candidates.append((x - 1, y))
    if x < width - 1:
        candidates.append((x + 1, y))
    if y > 0:
        candidates.append((x, y - 1))
    if y < height - 1:
        candidates.append((x, y + 1))
    return random.choice(candidates)


def _co_located_swarm_population(world: ECSWorld, x: int, y: int) -> int:
    """Return the total individual population of all swarms currently occupying one grid cell."""
    total_population = 0
    for entity_id in world.entities_at(x, y):
        if not world.has_entity(entity_id):
            continue
        entity = world.get_entity(entity_id)
        if entity.has_component(SwarmComponent):
            swarm = entity.get_component(SwarmComponent)
            total_population += swarm.population
    return total_population


def _perform_mitosis(
    swarm: SwarmComponent,
    world: ECSWorld,
    env: GridEnvironment,
) -> SwarmComponent:
    """Split an oversized swarm into two equal halves and spawn offspring.

    The original swarm retains ``floor(n/2)`` individuals; a new entity is
    created with the same attributes and the other half is assigned to it.

    Args:
        swarm: Parent swarm component to split.
        world: ECSWorld used to allocate the new entity.
        env: GridEnvironment used to sample a local dispersal cell.

    Returns:
        SwarmComponent: The newly spawned offspring swarm component.
    """
    offspring_population = swarm.population // 2
    retained_population = swarm.population - offspring_population
    swarm.population = retained_population
    swarm.initial_population = retained_population
    offspring_x, offspring_y = _random_walk_step(swarm.x, swarm.y, env.width, env.height)

    new_entity = world.create_entity()
    offspring = SwarmComponent(
        entity_id=new_entity.entity_id,
        species_id=swarm.species_id,
        x=offspring_x,
        y=offspring_y,
        population=offspring_population,
        initial_population=offspring_population,
        energy=swarm.energy / 2.0,
        energy_min=swarm.energy_min,
        velocity=swarm.velocity,
        consumption_rate=swarm.consumption_rate,
        reproduction_energy_divisor=swarm.reproduction_energy_divisor,
        energy_upkeep_per_individual=swarm.energy_upkeep_per_individual,
        split_population_threshold=swarm.split_population_threshold,
    )
    swarm.energy /= 2.0
    world.add_component(new_entity.entity_id, offspring)
    world.register_position(new_entity.entity_id, offspring_x, offspring_y)
    return offspring


def run_interaction(
    world: ECSWorld,
    env: GridEnvironment,
    diet_matrix: list[list[bool]],
    tick: int,
    plant_death_causes: dict[str, int] | None = None,
) -> None:
    """Execute one interaction tick for all swarm entities.

    The routine performs movement, feeding using the diet matrix, toxin
    damage, metabolic attrition, and mitosis, then collects dead swarms
    and rebuilds the plant energy layer.

    Args:
        world: ECSWorld registry.
        env: GridEnvironment instance (provides flow_field and toxin layers).
        diet_matrix: Compatibility matrix indexed by predator_id then flora_id.
        tick: Current simulation tick (reserved for future use).
        plant_death_causes: Mapping of death causes to their respective counts.
    """
    dead_swarms: list[int] = []
    tile_populations: dict[tuple[int, int], int] = {}
    for entity in world.query(SwarmComponent):
        indexed_swarm = entity.get_component(SwarmComponent)
        _accumulate_tile_population(
            tile_populations,
            indexed_swarm.x,
            indexed_swarm.y,
            indexed_swarm.population,
        )

    for entity in list(world.query(SwarmComponent)):
        swarm: SwarmComponent = entity.get_component(SwarmComponent)
        has_moved = False

        # ----------------------------------------------------------------
        # 1. Movement cooldown
        # ----------------------------------------------------------------
        if swarm.move_cooldown > 0:
            swarm.move_cooldown -= 1
        else:
            # ----------------------------------------------------------------
            # 2. Navigate with local crowding pressure
            # ----------------------------------------------------------------
            old_x, old_y = swarm.x, swarm.y

            if (
                not swarm.repelled
                and tile_populations.get((swarm.x, swarm.y), 0) > TILE_CARRYING_CAPACITY
            ):
                swarm.repelled = True
                swarm.repelled_ticks_remaining = 1

            if swarm.repelled and swarm.repelled_ticks_remaining > 0:
                nx, ny = _random_walk_step(swarm.x, swarm.y, env.width, env.height)
                swarm.repelled_ticks_remaining -= 1
                if swarm.repelled_ticks_remaining <= 0:
                    swarm.repelled = False
            else:
                nx, ny = _choose_neighbour_by_flow_probability(
                    swarm,
                    env.flow_field,
                    env.width,
                    env.height,
                )

            if (nx, ny) != (old_x, old_y):
                world.move_entity(entity.entity_id, old_x, old_y, nx, ny)
                _accumulate_tile_population(tile_populations, old_x, old_y, -swarm.population)
                _accumulate_tile_population(tile_populations, nx, ny, swarm.population)
                swarm.x, swarm.y = nx, ny
                swarm.last_dx = nx - old_x
                swarm.last_dy = ny - old_y
                has_moved = True

            swarm.move_cooldown = swarm.velocity - 1

        # ----------------------------------------------------------------
        # 3. Feeding – check co-located plants via spatial hash
        # ----------------------------------------------------------------
        if not has_moved:
            for co_eid in list(world.entities_at(swarm.x, swarm.y)):
                if not world.has_entity(co_eid):
                    continue
                co_entity = world.get_entity(co_eid)
                if not co_entity.has_component(PlantComponent):
                    continue
                plant: PlantComponent = co_entity.get_component(PlantComponent)

                # Diet compatibility check
                pred_row = (
                    diet_matrix[swarm.species_id] if swarm.species_id < len(diet_matrix) else []
                )
                if not (plant.species_id < len(pred_row) and pred_row[plant.species_id]):
                    continue

                effective_velocity = max(1, swarm.velocity)
                consumed = min(
                    (swarm.consumption_rate / effective_velocity) * swarm.population,
                    plant.energy,
                )
                plant.energy -= consumed
                env.set_plant_energy(plant.x, plant.y, plant.species_id, plant.energy)
                swarm.energy += consumed

                # Kill plant if energy below threshold
                if plant.energy < plant.survival_threshold:
                    if plant_death_causes is not None:
                        plant_death_causes["death_herbivore_feeding"] = (
                            plant_death_causes.get("death_herbivore_feeding", 0) + 1
                        )
                    env.clear_plant_energy(plant.x, plant.y, plant.species_id)
                    world.unregister_position(co_eid, plant.x, plant.y)
                    world.collect_garbage([co_eid])

        # ----------------------------------------------------------------
        # 4. Metabolic upkeep and deficit attrition
        # ----------------------------------------------------------------
        metabolic_cost = swarm.population * swarm.energy_min * swarm.energy_upkeep_per_individual
        swarm.energy -= metabolic_cost

        if swarm.energy < 0.0 and swarm.population > 0:
            previous_population = swarm.population
            deficit = -swarm.energy
            casualties = int(deficit // swarm.energy_min)
            if casualties * swarm.energy_min < deficit:
                casualties += 1
            swarm.population = max(0, swarm.population - casualties)
            _accumulate_tile_population(
                tile_populations,
                swarm.x,
                swarm.y,
                swarm.population - previous_population,
            )
            total_casualty_energy = casualties * swarm.energy_min
            leftover_energy = total_casualty_energy - deficit
            swarm.energy = max(0.0, leftover_energy)

        # ----------------------------------------------------------------
        # 5. Death check
        # ----------------------------------------------------------------
        if swarm.population <= 0:
            world.unregister_position(entity.entity_id, swarm.x, swarm.y)
            dead_swarms.append(entity.entity_id)
            continue

        # ----------------------------------------------------------------
        # 6. Reproduction: convert only swarm-scale surplus energy into growth
        # ----------------------------------------------------------------
        baseline_energy = swarm.population * swarm.energy_min
        if swarm.energy > baseline_energy:
            surplus = swarm.energy - baseline_energy
            cost_per_offspring = max(
                swarm.energy_min,
                swarm.energy_min * swarm.reproduction_energy_divisor,
            )

            new_individuals = int(surplus // cost_per_offspring)
            if new_individuals > 0:
                previous_population = swarm.population
                swarm.population += new_individuals
                _accumulate_tile_population(
                    tile_populations,
                    swarm.x,
                    swarm.y,
                    swarm.population - previous_population,
                )
                swarm.energy -= new_individuals * cost_per_offspring

        # ----------------------------------------------------------------
        # 7. Mitosis
        # ----------------------------------------------------------------
        split_threshold = (
            swarm.split_population_threshold
            if swarm.split_population_threshold > 0
            else 2 * swarm.initial_population
        )
        if swarm.population >= split_threshold:
            pre_split_population = swarm.population
            offspring = _perform_mitosis(swarm, world, env)
            _accumulate_tile_population(
                tile_populations,
                swarm.x,
                swarm.y,
                swarm.population - pre_split_population,
            )
            _accumulate_tile_population(
                tile_populations,
                offspring.x,
                offspring.y,
                offspring.population,
            )

    world.collect_garbage(dead_swarms)
