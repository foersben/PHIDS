# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Plant reproduction logic."""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from phids.engine.components.plant import PlantComponent
from phids.shared.constants import M_STRUCTURAL_SEED_VALUE

if TYPE_CHECKING:
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld


def _attempt_reproduction(
    plant: PlantComponent,
    tick: int,
    world: ECSWorld,
    env: GridEnvironment,
    flora_species_params: dict[int, object],
) -> list[PlantComponent]:
    """Attempt reproduction for a plant when interval and energy permit.

    Args:
        plant: Parent plant component.
        tick: Current simulation tick.
        world: ECSWorld to allocate new entities.
        env: GridEnvironment to update plant energy layers.
        flora_species_params: Mapping of species_id to species parameters.

    Returns:
        Newly created plant components (empty if none).
    """
    from phids.api.schemas.species import FloraSpeciesParams

    if (tick - plant.last_reproduction_tick) < plant.reproduction_interval:
        return []
    if (plant.energy - plant.seed_energy_cost) < plant.survival_threshold:
        return []

    local_wind_x = float(env.wind_vector_x[plant.x, plant.y])
    local_wind_y = float(env.wind_vector_y[plant.x, plant.y])
    wind_speed = math.hypot(local_wind_x, local_wind_y)

    # --- O(1) Stochastic Raycasting ---
    # Abandon continuous ballistic Gaussian kernels (drop height, terminal
    # velocity, parallel/perpendicular sigma sampling). Instead, project a
    # single absolute trajectory vector onto the normalized wind axis and
    # add a single Gaussian offset for turbulent spread.
    # This reduces seed dispersal from O(N x r^2) matrix convolution to a
    # single targeted O(1) discrete write, regardless of grid size.
    distance = random.uniform(plant.seed_min_dist, plant.seed_max_dist)
    if wind_speed > 1e-9:
        ux = local_wind_x / wind_speed
        uy = local_wind_y / wind_speed
        # Scale wind drift by distance; add a single Gaussian spread in
        # the perpendicular axis to capture turbulent lateral scatter.
        sigma_perp = max(0.15, 0.35 * distance)
        perp_offset = random.gauss(0.0, sigma_perp)
        tx = round(plant.x + distance * ux - perp_offset * uy)
        ty = round(plant.y + distance * uy + perp_offset * ux)
    else:
        angle = random.uniform(0, 2 * math.pi)
        tx = round(plant.x + distance * math.cos(angle))
        ty = round(plant.y + distance * math.sin(angle))

    # Toroidal coordinate wrap
    tx = tx % env.width
    ty = ty % env.height

    # Germination condition: target cell must be unoccupied by any plant
    occupants = world.entities_at(tx, ty)
    for eid in occupants:
        if world.get_entity(eid).has_component(PlantComponent):
            return []  # cell occupied - energy spent, no offspring

    # Spawn new plant
    params_raw = flora_species_params.get(plant.species_id)
    if not isinstance(params_raw, FloraSpeciesParams):
        return []
    params: FloraSpeciesParams = params_raw

    plant.energy -= plant.seed_energy_cost
    plant.last_reproduction_tick = tick
    plant.last_energy_loss_cause = "death_reproduction"

    new_entity = world.create_entity()
    new_plant = PlantComponent(
        entity_id=new_entity.entity_id,
        species_id=plant.species_id,
        x=tx,
        y=ty,
        energy=params.base_energy,
        max_energy=params.max_energy,
        base_energy=params.base_energy,
        growth_rate=params.growth_rate,
        survival_threshold=params.survival_threshold,
        reproduction_interval=params.reproduction_interval,
        seed_min_dist=params.seed_min_dist,
        seed_max_dist=params.seed_max_dist,
        seed_energy_cost=params.seed_energy_cost,
        seed_drop_height=params.seed_drop_height,
        seed_terminal_velocity=params.seed_terminal_velocity,
        camouflage=params.camouflage,
        camouflage_factor=params.camouflage_factor,
        last_reproduction_tick=tick,
        translocation_rate=params.translocation_rate,
        mycorrhizal_tax_per_link=params.mycorrhizal_tax_per_link,
        # M_structural: seeds start with zero lignin/woodiness (fully vulnerable to trampling).
        # structural_mass_max is sourced directly from FloraSpeciesParams (Plan 2+).
        # Falls back to max_energy if 0.0 (Plan 1 compatibility for scenarios without the field).
        structural_mass=M_STRUCTURAL_SEED_VALUE,
        max_structural_mass=params.structural_mass_max if params.structural_mass_max > 0.0 else params.max_energy,
        growth_rate_structural=params.structural_growth_rate,
    )
    world.add_component(new_entity.entity_id, new_plant)
    world.register_position(new_entity.entity_id, tx, ty)
    env.set_plant_energy(tx, ty, plant.species_id, params.base_energy)
    env.set_structural_mass(tx, ty, plant.species_id, M_STRUCTURAL_SEED_VALUE)
    env.set_apparent_nutrition(tx, ty, plant.apparent_nutrition_factor)
    return [new_plant]
