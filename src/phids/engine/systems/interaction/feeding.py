# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Herbivory logic for swarms feeding on flora in the interaction system."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from phids.engine.components.plant import PlantComponent
from phids.engine.systems.interaction.population import _accumulate_tile_population

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt

    from phids.api.schemas.species import (
        FloraSpeciesParams,
        HerbivoreSpeciesParams,
    )
    from phids.engine.components.swarm import SwarmComponent
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld


@dataclass(slots=True, frozen=True)
class CachedFloraForagingParams:
    """Pre-extracted O(1) slot parameters for flora foraging interactions."""

    digestibility_modifier: float
    mechanical_damage_per_bite: float


@dataclass(slots=True, frozen=True)
class CachedHerbivoreForagingParams:
    """Pre-extracted O(1) slot parameters for herbivore foraging interactions."""

    handling_time: float
    digestive_efficiency: float
    morphological_adaptation: float


def cache_flora_foraging_params(
    flora_species_params: list[FloraSpeciesParams],
) -> list[CachedFloraForagingParams]:
    """Pre-extract flora foraging parameters to bypass dynamic descriptor lookups."""
    return [
        CachedFloraForagingParams(
            digestibility_modifier=p.passive_defenses.digestibility_modifier,
            mechanical_damage_per_bite=p.passive_defenses.mechanical_damage_per_bite,
        )
        for p in flora_species_params
    ]


def cache_herbivore_foraging_params(
    herbivore_species_params: list[HerbivoreSpeciesParams],
) -> list[CachedHerbivoreForagingParams]:
    """Pre-extract herbivore foraging parameters to bypass dynamic descriptor lookups."""
    return [
        CachedHerbivoreForagingParams(
            handling_time=p.handling_time,
            digestive_efficiency=p.resistances.digestive_efficiency,
            morphological_adaptation=p.resistances.morphological_adaptation,
        )
        for p in herbivore_species_params
    ]


def _feed_on_single_plant(
    swarm: SwarmComponent,
    target_plant: PlantComponent,
    flora_species_params: list[FloraSpeciesParams] | list[CachedFloraForagingParams],
    herbivore_species_params: list[HerbivoreSpeciesParams] | list[CachedHerbivoreForagingParams],
    env: GridEnvironment,
    tile_populations: npt.NDArray[np.int32] | list[int],
    plant_death_causes: dict[str, int] | None,
    stride_multiplier: float = 1.0,
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
        env: The grid environment.
        tile_populations: The tile populations.
        plant_death_causes: The plant death causes.
        stride_multiplier: The scaling factor for consumption rate over the stride interval.

    Returns:
        A tuple containing the metabolized energy and whether the plant was killed.
    """
    effective_velocity = max(1, swarm.velocity)
    swarm_p = herbivore_species_params[swarm.species_id]
    if isinstance(swarm_p, CachedHerbivoreForagingParams):
        handling_time = swarm_p.handling_time
        digestive_efficiency = swarm_p.digestive_efficiency
        morphological_adaptation = swarm_p.morphological_adaptation
    else:
        handling_time = swarm_p.handling_time
        digestive_efficiency = swarm_p.resistances.digestive_efficiency
        morphological_adaptation = swarm_p.resistances.morphological_adaptation

    # Consumption rate is scaled by stride_multiplier (e.g. 24 hours on daily medium-tick steps).
    raw_per_ind = (swarm.consumption_rate * stride_multiplier) / effective_velocity
    if handling_time > 0.0:
        potential_per_ind = (raw_per_ind * target_plant.energy) / (
            1.0 + raw_per_ind * handling_time * target_plant.energy
        )
    else:
        potential_per_ind = raw_per_ind

    potential_consumption = potential_per_ind * swarm.population
    consumed = min(potential_consumption, target_plant.energy)

    plant_p = flora_species_params[target_plant.species_id]
    if isinstance(plant_p, CachedFloraForagingParams):
        digestibility_modifier = plant_p.digestibility_modifier
        mechanical_damage_per_bite = plant_p.mechanical_damage_per_bite
    else:
        digestibility_modifier = plant_p.passive_defenses.digestibility_modifier
        mechanical_damage_per_bite = plant_p.passive_defenses.mechanical_damage_per_bite

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
        plant_killed = True

    return metabolized_energy, plant_killed


def _get_target_plant(world: ECSWorld, co_eid: int) -> PlantComponent | None:
    if not world.has_entity(co_eid):
        return None
    co_entity = world.get_entity(co_eid)
    if not co_entity.has_component(PlantComponent):
        return None
    return co_entity.get_component(PlantComponent)


def _is_diet_compatible(herbivore_species_id: int, plant_species_id: int, diet_matrix: npt.NDArray[np.bool_]) -> bool:
    if herbivore_species_id >= diet_matrix.shape[0]:
        return False
    return plant_species_id < diet_matrix.shape[1] and bool(diet_matrix[herbivore_species_id, plant_species_id])


def _resolve_swarm_feeding(
    swarm: SwarmComponent,
    world: ECSWorld,
    env: GridEnvironment,
    diet_matrix: npt.NDArray[np.bool_],
    flora_species_params: list[FloraSpeciesParams] | list[CachedFloraForagingParams],
    herbivore_species_params: list[HerbivoreSpeciesParams] | list[CachedHerbivoreForagingParams],
    tile_populations: npt.NDArray[np.int32] | list[int],
    plant_death_causes: dict[str, int] | None = None,
    stride_multiplier: float = 1.0,
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
        stride_multiplier: The scaling factor for consumption rate over the stride interval.
    """
    ate_anything = False
    on_incompatible_plant = False
    dead_plants: list[int] = []
    total_metabolized = 0.0

    for co_eid in world.entities_at(swarm.x, swarm.y):
        target_plant = _get_target_plant(world, co_eid)
        if target_plant is None:
            continue

        if not diet_matrix[swarm.species_id][target_plant.species_id]:
            on_incompatible_plant = True
            continue

        if target_plant.energy <= 0:
            continue

        metabolized, plant_killed = _feed_on_single_plant(
            swarm=swarm,
            target_plant=target_plant,
            flora_species_params=flora_species_params,
            herbivore_species_params=herbivore_species_params,
            env=env,
            tile_populations=tile_populations,
            plant_death_causes=plant_death_causes,
            stride_multiplier=stride_multiplier,
        )
        total_metabolized += metabolized
        swarm.energy += metabolized
        if metabolized > 0:
            ate_anything = True
        if plant_killed:
            dead_plants.append(co_eid)

    swarm.last_caloric_intake = total_metabolized / max(1e-9, stride_multiplier)

    # Write back the updated swarm component to ECS
    world.add_component(swarm.entity_id, swarm)

    for eid in dead_plants:
        world.unregister_position(eid, swarm.x, swarm.y)
    if dead_plants:
        world.collect_garbage(dead_plants)

    # Behavioral overrides based on feeding success
    if ate_anything:
        swarm.repelled = False
        swarm.repelled_ticks_remaining = 0
    elif on_incompatible_plant:
        swarm.repelled = True
        swarm.repelled_ticks_remaining = 2
