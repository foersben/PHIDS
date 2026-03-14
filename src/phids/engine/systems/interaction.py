"""Interaction system: swarm movement, feeding and continuous energy economy.

This module implements swarm behaviour including movement (gradient
navigation or random walk), feeding using the diet compatibility matrix,
metabolic attrition and mitosis. Spatial hash lookups provide O(1)
co-occupancy checks.
"""

from __future__ import annotations

import random

import numpy as np
import numpy.typing as npt

from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld


SWARM_TILE_CROWDING_THRESHOLD = 2


def _choose_neighbour_by_flow_probability(
    x: int,
    y: int,
    flow_field: npt.NDArray[np.float64],
    width: int,
    height: int,
    invert: bool = False,
) -> tuple[int, int]:
    """Choose a 4-connected neighbour (or current cell) from flow-weighted probabilities.

    Args:
        x: Current X coordinate.
        y: Current Y coordinate.
        flow_field: Scalar attraction field.
        width: Grid width.
        height: Grid height.
        invert: When True, prefer lower gradients (flee behaviour).

    Returns:
        tuple[int, int]: Selected (nx, ny) cell to move to.
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

    scores = [
        float(flow_field[candidate_x, candidate_y]) for candidate_x, candidate_y in candidates
    ]
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


def _co_located_swarm_count(world: ECSWorld, x: int, y: int) -> int:
    """Return the number of swarms currently occupying one grid cell."""
    count = 0
    for entity_id in world.entities_at(x, y):
        if not world.has_entity(entity_id):
            continue
        entity = world.get_entity(entity_id)
        if entity.has_component(SwarmComponent):
            count += 1
    return count


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
    """
    dead_swarms: list[int] = []
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
                and _co_located_swarm_count(world, swarm.x, swarm.y) > SWARM_TILE_CROWDING_THRESHOLD
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
                    swarm.x,
                    swarm.y,
                    env.flow_field,
                    env.width,
                    env.height,
                )

            if (nx, ny) != (old_x, old_y):
                world.move_entity(entity.entity_id, old_x, old_y, nx, ny)
                swarm.x, swarm.y = nx, ny
                has_moved = True

            swarm.move_cooldown = swarm.velocity - 1

        # ----------------------------------------------------------------
        # 3. Feeding – check co-located plants via spatial hash
        # ----------------------------------------------------------------
        if not has_moved:
            for co_eid in list(world.entities_at(swarm.x, swarm.y)):
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
            deficit = -swarm.energy
            casualties = int(deficit // swarm.energy_min)
            if casualties * swarm.energy_min < deficit:
                casualties += 1
            swarm.population = max(0, swarm.population - casualties)
            swarm.energy = 0.0

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
        reproduction_threshold = max(
            swarm.energy_min,
            swarm.population * swarm.energy_min * swarm.reproduction_energy_divisor,
        )
        new_individuals = int(swarm.energy // reproduction_threshold)
        if new_individuals > 0:
            swarm.population += new_individuals
            swarm.energy -= new_individuals * reproduction_threshold

        # ----------------------------------------------------------------
        # 7. Mitosis
        # ----------------------------------------------------------------
        split_threshold = (
            swarm.split_population_threshold
            if swarm.split_population_threshold > 0
            else 2 * swarm.initial_population
        )
        if swarm.population >= split_threshold:
            _perform_mitosis(swarm, world, env)

    world.collect_garbage(dead_swarms)
    env.rebuild_energy_layer()
