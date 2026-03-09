"""Interaction system: swarm movement, feeding, starvation, mitosis, toxin effects.

Implements O(1) spatial-hash lookups for predator/flora co-occupancy,
flow-field navigation, diet matrix enforcement, and ECS garbage collection.
"""

from __future__ import annotations

import random

import numpy as np
import numpy.typing as npt

from phytodynamics.engine.components.plant import PlantComponent
from phytodynamics.engine.components.swarm import SwarmComponent
from phytodynamics.engine.core.biotope import GridEnvironment
from phytodynamics.engine.core.ecs import ECSWorld


def _best_neighbour(
    x: int,
    y: int,
    flow_field: npt.NDArray[np.float64],
    width: int,
    height: int,
    invert: bool = False,
) -> tuple[int, int]:
    """Return the 4-connected neighbour (or current cell) with the highest gradient.

    Parameters
    ----------
    x, y:
        Current cell.
    flow_field:
        Scalar attraction field.
    width, height:
        Grid dimensions.
    invert:
        When True (repelled state), choose the *lowest* gradient (flee).

    Returns
    -------
    tuple[int, int]
        Best (nx, ny) to move to.
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

    if invert:
        return min(candidates, key=lambda c: flow_field[c[0], c[1]])
    return max(candidates, key=lambda c: flow_field[c[0], c[1]])


def _random_walk_step(
    x: int,
    y: int,
    width: int,
    height: int,
) -> tuple[int, int]:
    """Return a random valid adjacent cell."""
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
    """Split an oversized swarm into two equal halves.

    The original swarm retains floor(n/2) individuals.  A new entity is
    created with the same attributes and floor(n/2) individuals, placed
    on the same cell.

    Returns
    -------
    SwarmComponent
        The newly spawned offspring swarm component.
    """
    half = swarm.population // 2
    swarm.population = half

    new_entity = world.create_entity()
    offspring = SwarmComponent(
        entity_id=new_entity.entity_id,
        species_id=swarm.species_id,
        x=swarm.x,
        y=swarm.y,
        population=half,
        initial_population=half,
        energy=swarm.energy / 2.0,
        energy_min=swarm.energy_min,
        velocity=swarm.velocity,
        consumption_rate=swarm.consumption_rate,
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

    Steps per swarm
    ---------------
    1. Decrement move_cooldown; skip movement if > 0.
    2. Navigate via flow-field (or random walk if repelled).
    3. Feed on co-located plants that pass the diet matrix.
    4. Apply lethal toxin casualties.
    5. Starvation attrition.
    6. Mitosis check.
    7. Mark starved-to-zero or otherwise dead swarms for GC.

    Parameters
    ----------
    world:
        ECS world registry.
    env:
        Grid environment (flow_field, toxin_layers).
    diet_matrix:
        Boolean list[predator_id][flora_species_id] = edible.
    tick:
        Current simulation tick (unused directly but reserved for future use).
    """
    dead_swarms: list[int] = []
    new_swarms: list[SwarmComponent] = []

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
                nx, ny = _best_neighbour(
                    swarm.x, swarm.y, env.flow_field, env.width, env.height
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
                casualties = int(toxin_val * swarm.population * 0.1)
                swarm.population = max(0, swarm.population - casualties)

        # ----------------------------------------------------------------
        # 5. Starvation attrition
        # ----------------------------------------------------------------
        if swarm.starvation_ticks > 0:
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
        # 7. Mitosis
        # ----------------------------------------------------------------
        if swarm.population >= 2 * swarm.initial_population:
            offspring = _perform_mitosis(swarm, world)
            new_swarms.append(offspring)

        # ----------------------------------------------------------------
        # 8. Reproduction: generate floor(energy / energy_min) new individuals
        # ----------------------------------------------------------------
        new_individuals = int(swarm.energy // swarm.energy_min)
        if new_individuals > 0:
            swarm.population += new_individuals
            swarm.energy -= new_individuals * swarm.energy_min

    world.collect_garbage(dead_swarms)
    env.rebuild_energy_layer()
