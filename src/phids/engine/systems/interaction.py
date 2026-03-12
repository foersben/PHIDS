"""Interaction system: swarm movement, feeding, mitosis and toxin effects.

This module implements swarm behaviour including movement (gradient
navigation or random walk), feeding using the diet compatibility matrix,
starvation attrition, mitosis and application of toxin effects. Spatial
hash lookups provide O(1) co-occupancy checks.
"""

from __future__ import annotations

import random

import numpy as np
import numpy.typing as npt

from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.shared.constants import TOXIN_CASUALTY_FACTOR


def _choose_neighbour_by_flow_probability(
    x: int,
    y: int,
    flow_field: npt.NDArray[np.float64],
    width: int,
    height: int,
    invert: bool = False,
) -> tuple[int, int]:
    """Choose the best 4-connected neighbour (or current cell) from the flow field.

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

    best_candidate = candidates[0]
    best_score = float(flow_field[x, y])
    for candidate_x, candidate_y in candidates[1:]:
        candidate_score = float(flow_field[candidate_x, candidate_y])
        if invert:
            if candidate_score < best_score:
                best_candidate = (candidate_x, candidate_y)
                best_score = candidate_score
            continue
        if candidate_score > best_score:
            best_candidate = (candidate_x, candidate_y)
            best_score = candidate_score
    return best_candidate


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


def _perform_mitosis(
    swarm: SwarmComponent,
    world: ECSWorld,
) -> SwarmComponent:
    """Split an oversized swarm into two equal halves and spawn offspring.

    The original swarm retains ``floor(n/2)`` individuals; a new entity is
    created with the same attributes and the other half is assigned to it.

    Args:
        swarm: Parent swarm component to split.
        world: ECSWorld used to allocate the new entity.

    Returns:
        SwarmComponent: The newly spawned offspring swarm component.
    """
    offspring_population = swarm.population // 2
    retained_population = swarm.population - offspring_population
    swarm.population = retained_population
    swarm.initial_population = retained_population

    new_entity = world.create_entity()
    offspring = SwarmComponent(
        entity_id=new_entity.entity_id,
        species_id=swarm.species_id,
        x=swarm.x,
        y=swarm.y,
        population=offspring_population,
        initial_population=offspring_population,
        energy=swarm.energy / 2.0,
        energy_min=swarm.energy_min,
        velocity=swarm.velocity,
        consumption_rate=swarm.consumption_rate,
        reproduction_energy_divisor=swarm.reproduction_energy_divisor,
    )
    swarm.energy /= 2.0
    world.add_component(new_entity.entity_id, offspring)
    world.register_position(new_entity.entity_id, swarm.x, swarm.y)
    return offspring


def run_interaction(
    world: ECSWorld,
    env: GridEnvironment,
    diet_matrix: list[list[bool]],
    tick: int,
) -> None:
    """Execute one interaction tick for all swarm entities.

    The routine performs movement, feeding using the diet matrix, toxin
    damage, starvation attrition, and mitosis, then collects dead swarms
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

        # ----------------------------------------------------------------
        # 1. Movement cooldown
        # ----------------------------------------------------------------
        if swarm.move_cooldown > 0:
            swarm.move_cooldown -= 1
        else:
            # ----------------------------------------------------------------
            # 2. Navigate
            # ----------------------------------------------------------------
            old_x, old_y = swarm.x, swarm.y

            if swarm.repelled and swarm.repelled_ticks_remaining > 0:
                nx, ny = _random_walk_step(swarm.x, swarm.y, env.width, env.height)
                swarm.repelled_ticks_remaining -= 1
                if swarm.repelled_ticks_remaining <= 0:
                    swarm.repelled = False
                    swarm.target_plant_id = -1
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

            swarm.move_cooldown = swarm.velocity - 1

        # ----------------------------------------------------------------
        # 3. Feeding – check co-located plants via spatial hash
        # ----------------------------------------------------------------
        fed = False
        for co_eid in list(world.entities_at(swarm.x, swarm.y)):
            co_entity = world.get_entity(co_eid)
            if not co_entity.has_component(PlantComponent):
                continue
            plant: PlantComponent = co_entity.get_component(PlantComponent)

            # Diet compatibility check
            pred_row = diet_matrix[swarm.species_id] if swarm.species_id < len(diet_matrix) else []
            if not (plant.species_id < len(pred_row) and pred_row[plant.species_id]):
                continue

            consumed = min(swarm.consumption_rate * swarm.population, plant.energy)
            plant.energy -= consumed
            env.set_plant_energy(plant.x, plant.y, plant.species_id, plant.energy)
            swarm.energy += consumed
            swarm.starvation_ticks = 0
            fed = True

            # Kill plant if energy below threshold
            if plant.energy < plant.survival_threshold:
                env.clear_plant_energy(plant.x, plant.y, plant.species_id)
                world.unregister_position(co_eid, plant.x, plant.y)
                world.collect_garbage([co_eid])

        if not fed:
            swarm.starvation_ticks += 1

        # ----------------------------------------------------------------
        # 4. Lethal toxin damage at current cell (from toxin_layers)
        # ----------------------------------------------------------------
        for t_idx in range(env.num_toxins):
            toxin_val = float(env.toxin_layers[t_idx, swarm.x, swarm.y])
            if toxin_val > 0.0:
                # Each toxin layer can cause casualties; handled by signaling system
                # which writes the lethality_rate into toxin_layers scaled values.
                # Here we apply a generic casualty proportional to concentration.
                casualties = int(toxin_val * swarm.population * TOXIN_CASUALTY_FACTOR)
                swarm.population = max(0, swarm.population - casualties)

        # ----------------------------------------------------------------
        # 5. Starvation attrition
        # ----------------------------------------------------------------
        if swarm.starvation_ticks > 1:
            attrition = max(1, int(swarm.population * 0.05 * swarm.starvation_ticks))
            swarm.population = max(0, swarm.population - attrition)

        # ----------------------------------------------------------------
        # 6. Death check
        # ----------------------------------------------------------------
        if swarm.population <= 0:
            world.unregister_position(entity.entity_id, swarm.x, swarm.y)
            dead_swarms.append(entity.entity_id)
            continue

        # ----------------------------------------------------------------
        # 7. Reproduction: convert only swarm-scale surplus energy into growth
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
        # 8. Mitosis
        # ----------------------------------------------------------------
        if swarm.population >= 2 * swarm.initial_population:
            _perform_mitosis(swarm, world)

    world.collect_garbage(dead_swarms)
    env.rebuild_energy_layer()
