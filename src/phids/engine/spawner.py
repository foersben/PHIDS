# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Initial entity placement and biotope allocation for the simulation engine.

Spawns initial botanical specimens and herbivore swarms based on scenario
configuration specifications and registers spatial positions in the ECS world.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.herbivore_params import (
    get_herbivore_consumption_rate,
    get_herbivore_energy_min,
    get_herbivore_energy_upkeep,
    get_herbivore_reproduction_divisor,
    get_herbivore_split_threshold,
    get_herbivore_velocity,
)

if TYPE_CHECKING:
    from phids.api.schemas.simulation import SimulationConfig
    from phids.api.schemas.species import FloraSpeciesParams, HerbivoreSpeciesParams
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld

logger = logging.getLogger(__name__)


def spawn_initial_entities(
    config: SimulationConfig,
    world: ECSWorld,
    env: GridEnvironment,
    flora_params: dict[int, FloraSpeciesParams],
    herbivore_params: dict[int, HerbivoreSpeciesParams],
) -> tuple[int, int]:
    """Place initial plants and swarms from scenario configuration into the ECS world.

    Instantiates PlantComponent and SwarmComponent entities, registers spatial
    indices in the ECS world, sets initial energy layers in GridEnvironment,
    and rebuilds aggregate energy matrices.

    Args:
        config: Validated SimulationConfig instance.
        world: Active ECSWorld instance.
        env: Active GridEnvironment instance.
        flora_params: Mapping of species_id to FloraSpeciesParams.
        herbivore_params: Mapping of species_id to HerbivoreSpeciesParams.

    Returns:
        tuple[int, int]: Count of spawned plants and swarms (spawned_plants, spawned_swarms).
    """
    spawned_plants = 0
    spawned_swarms = 0

    for plant_placement in config.initial_plants:
        params = flora_params.get(plant_placement.species_id)
        if params is None:
            logger.warning(
                "Skipping initial plant placement with unknown flora species_id=%d at (%d, %d)",
                plant_placement.species_id,
                plant_placement.x,
                plant_placement.y,
            )
            continue

        entity = world.create_entity()
        effective_max_struct = params.structural_mass_max if params.structural_mass_max > 0.0 else params.max_energy
        initial_energy_ratio = min(1.0, max(0.0, plant_placement.energy / max(1.0, params.max_energy)))
        initial_struct_mass = effective_max_struct * initial_energy_ratio

        plant = PlantComponent.from_params(
            entity_id=entity.entity_id,
            species_id=plant_placement.species_id,
            x=plant_placement.x,
            y=plant_placement.y,
            params=params,
            energy=plant_placement.energy,
            structural_mass=initial_struct_mass,
            last_reproduction_tick=0,
        )
        world.add_component(entity.entity_id, plant)
        world.register_position(entity.entity_id, plant_placement.x, plant_placement.y)
        env.set_plant_energy(
            plant_placement.x,
            plant_placement.y,
            plant_placement.species_id,
            plant_placement.energy,
        )
        env.set_structural_mass(
            plant_placement.x,
            plant_placement.y,
            plant_placement.species_id,
            initial_struct_mass,
        )
        spawned_plants += 1

    for swarm_placement in config.initial_swarms:
        entity = world.create_entity()
        energy_min = get_herbivore_energy_min(herbivore_params, swarm_placement.species_id)
        energy_upkeep_per_individual = get_herbivore_energy_upkeep(herbivore_params, swarm_placement.species_id)
        initial_upkeep = swarm_placement.population * energy_min * energy_upkeep_per_individual

        swarm = SwarmComponent(
            entity_id=entity.entity_id,
            species_id=swarm_placement.species_id,
            x=swarm_placement.x,
            y=swarm_placement.y,
            population=swarm_placement.population,
            initial_population=swarm_placement.population,
            energy=swarm_placement.energy,
            energy_min=energy_min,
            velocity=get_herbivore_velocity(herbivore_params, swarm_placement.species_id),
            consumption_rate=get_herbivore_consumption_rate(herbivore_params, swarm_placement.species_id),
            reproduction_energy_divisor=get_herbivore_reproduction_divisor(
                herbivore_params, swarm_placement.species_id
            ),
            energy_upkeep_per_individual=energy_upkeep_per_individual,
            split_population_threshold=get_herbivore_split_threshold(herbivore_params, swarm_placement.species_id),
            last_caloric_intake=initial_upkeep,
            metabolism_upkeep=initial_upkeep,
        )
        world.add_component(entity.entity_id, swarm)
        world.register_position(entity.entity_id, swarm_placement.x, swarm_placement.y)
        spawned_swarms += 1

    env.rebuild_energy_layer()
    logger.info(
        "Initial entities spawned (plants=%d, swarms=%d)",
        spawned_plants,
        spawned_swarms,
    )
    return spawned_plants, spawned_swarms
