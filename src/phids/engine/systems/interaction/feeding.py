# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Herbivory logic for swarms feeding on flora in the interaction system."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from phids.engine.components.plant import PlantComponent
from phids.engine.systems.interaction.population import _accumulate_tile_population

if TYPE_CHECKING:
    from phids.api.schemas.species import (
        FloraSpeciesParams,
        HerbivoreSpeciesParams,
    )
    from phids.engine.components.swarm import SwarmComponent
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld


def _feed_on_single_plant(
    swarm: SwarmComponent,
    target_plant: PlantComponent,
    flora_species_params: list[FloraSpeciesParams],
    herbivore_species_params: list[HerbivoreSpeciesParams],
    world: ECSWorld,
    env: GridEnvironment,
    tile_populations: list[int],
    plant_death_causes: dict[str, int] | None,
    co_eid: int,
) -> tuple[float, bool]:
    """Feed on a single co-located plant, returning (metabolized_energy, plant_killed).

    This function implements the core feeding logic for a herbivore swarm, handling
    the transfer of energy from a plant to the swarm. It calculates the potential
    consumption based on the swarm's parameters and the plant's energy, then applies
    digestibility and efficiency modifiers to determine the actual amount of consumed
    energy.

    Args:
        swarm: The swarm component.
        target_plant: The plant component to feed on.
        flora_species_params: The flora species parameters.
        herbivore_species_params: The herbivore species parameters.
        world: The ECS world.
        env: The grid environment.
        tile_populations: The tile populations.
        plant_death_causes: The plant death causes.
        co_eid: The co-eid.

    Returns:
        A tuple containing the metabolized energy and whether the plant was killed.
    """
    effective_velocity = max(1, swarm.velocity)
    potential_consumption = (swarm.consumption_rate / effective_velocity) * swarm.population
    consumed = min(potential_consumption, target_plant.energy)

    plant_params = flora_species_params[target_plant.species_id]
    swarm_params = herbivore_species_params[swarm.species_id]

    digestibility_modifier = plant_params.passive_defenses.digestibility_modifier
    digestive_efficiency = swarm_params.resistances.digestive_efficiency
    mechanical_damage_per_bite = plant_params.passive_defenses.mechanical_damage_per_bite
    morphological_adaptation = swarm_params.resistances.morphological_adaptation

    # Calculate metabolized energy
    net_digestibility = min(1.0, max(0.0, digestibility_modifier * digestive_efficiency))
    metabolized_energy = consumed * net_digestibility

    # Apply mechanical damage
    if mechanical_damage_per_bite > 0.0 and consumed > 0:
        damage = mechanical_damage_per_bite * (1.0 - morphological_adaptation)
        casualties = math.floor(damage)
        swarm.population = max(0, swarm.population - casualties)
        _accumulate_tile_population(tile_populations, swarm.x, swarm.y, env.width, -casualties)

    target_plant.energy -= consumed
    env.set_plant_energy(
        target_plant.x,
        target_plant.y,
        target_plant.species_id,
        target_plant.energy,
    )

    plant_killed = False
    if target_plant.energy < target_plant.survival_threshold:
        if plant_death_causes is not None:
            plant_death_causes["death_herbivore_feeding"] = plant_death_causes.get("death_herbivore_feeding", 0) + 1
        env.clear_plant_energy(
            target_plant.x,
            target_plant.y,
            target_plant.species_id,
        )
        world.unregister_position(co_eid, target_plant.x, target_plant.y)
        world.collect_garbage([co_eid])
        plant_killed = True

    return metabolized_energy, plant_killed


def _resolve_swarm_feeding(
    swarm: SwarmComponent,
    world: ECSWorld,
    env: GridEnvironment,
    diet_matrix: list[list[bool]],
    flora_species_params: list[FloraSpeciesParams],
    herbivore_species_params: list[HerbivoreSpeciesParams],
    tile_populations: list[int],
    plant_death_causes: dict[str, int] | None = None,
) -> None:
    """Execute feeding phase on target plants at current position.

    Iterates through all co-located entities, identifies compatible plants, and consumes them.
    Updates the swarm's energy, triggers plant removal if exhausted, and adjusts swarm behavior
    (stopping repulsion, becoming repelled) based on the feeding outcome.

    Args:
        swarm: The swarm component.
        world: The ECS world.
        env: The grid environment.
        diet_matrix: The diet matrix.
        flora_species_params: The flora species parameters.
        herbivore_species_params: The herbivore species parameters.
        tile_populations: The tile populations.
        plant_death_causes: The plant death causes.
    """
    ate_anything = False
    on_incompatible_plant = False

    for co_eid in list(world.entities_at(swarm.x, swarm.y)):
        if not world.has_entity(co_eid):
            continue
        co_entity = world.get_entity(co_eid)
        if not co_entity.has_component(PlantComponent):
            continue
        target_plant: PlantComponent = co_entity.get_component(PlantComponent)

        # Diet compatibility check
        herbivore_row = diet_matrix[swarm.species_id] if swarm.species_id < len(diet_matrix) else []
        if not (target_plant.species_id < len(herbivore_row) and herbivore_row[target_plant.species_id]):
            on_incompatible_plant = True
            continue

        metabolized, _ = _feed_on_single_plant(
            swarm,
            target_plant,
            flora_species_params,
            herbivore_species_params,
            world,
            env,
            tile_populations,
            plant_death_causes,
            co_eid,
        )
        swarm.energy += metabolized
        if metabolized > 0:
            ate_anything = True

    # Behavioral overrides based on feeding success
    if ate_anything:
        swarm.repelled = False
        swarm.repelled_ticks_remaining = 0
    elif on_incompatible_plant:
        swarm.repelled = True
        swarm.repelled_ticks_remaining = 2
