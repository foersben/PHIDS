"""Lifecycle system: plant growth, reproduction, and death.

Executed once per simulation tick before interaction and signaling.
"""

from __future__ import annotations

import math
import random

from phytodynamics.engine.components.plant import PlantComponent
from phytodynamics.engine.core.biotope import GridEnvironment
from phytodynamics.engine.core.ecs import ECSWorld


def _grow(plant: PlantComponent, tick: int) -> None:
    """Apply the growth formula E_i,j(t+1) = E_i,j(0) * (1 + r/100 * t).

    Energy is clamped to max_energy.
    """
    new_energy = plant.base_energy * (1.0 + plant.growth_rate / 100.0 * tick)
    plant.energy = min(new_energy, plant.max_energy)


def _attempt_reproduction(
    plant: PlantComponent,
    tick: int,
    world: ECSWorld,
    env: GridEnvironment,
    flora_species_params: dict[int, object],
) -> list[PlantComponent]:
    """Try to reproduce at interval T_i.  Returns list of new PlantComponents."""
    from phytodynamics.api.schemas import FloraSpeciesParams  # local import avoids circulars

    if (tick - plant.last_reproduction_tick) < plant.reproduction_interval:
        return []
    if plant.energy < plant.seed_energy_cost:
        return []

    # Deduct energy regardless of success
    plant.energy -= plant.seed_energy_cost
    plant.last_reproduction_tick = tick

    # Choose a random seed location within [d_min, d_max]
    angle = random.uniform(0, 2 * math.pi)
    distance = random.uniform(plant.seed_min_dist, plant.seed_max_dist)
    tx = int(round(plant.x + distance * math.cos(angle)))
    ty = int(round(plant.y + distance * math.sin(angle)))

    # Boundary check
    if not (0 <= tx < env.width and 0 <= ty < env.height):
        return []

    # Germination condition: target cell must be unoccupied by any plant
    occupants = world.entities_at(tx, ty)
    for eid in occupants:
        if world.get_entity(eid).has_component(PlantComponent):
            return []  # cell occupied – energy spent, no offspring

    # Spawn new plant
    params_raw = flora_species_params.get(plant.species_id)
    if not isinstance(params_raw, FloraSpeciesParams):
        return []
    params: FloraSpeciesParams = params_raw

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
        camouflage=params.camouflage,
        camouflage_factor=params.camouflage_factor,
    )
    world.add_component(new_entity.entity_id, new_plant)
    world.register_position(new_entity.entity_id, tx, ty)
    env.set_plant_energy(tx, ty, plant.species_id, params.base_energy)
    return [new_plant]


def run_lifecycle(
    world: ECSWorld,
    env: GridEnvironment,
    tick: int,
    flora_species_params: dict[int, object],
) -> None:
    """Execute one lifecycle tick: grow all plants, reproduce, and cull dead ones.

    Parameters
    ----------
    world:
        The ECS world registry.
    env:
        The grid environment.
    tick:
        Current simulation tick index.
    flora_species_params:
        Mapping of species_id -> FloraSpeciesParams (from SimulationConfig).
    """
    dead: list[int] = []

    for entity in list(world.query(PlantComponent)):
        plant: PlantComponent = entity.get_component(PlantComponent)

        # Growth
        _grow(plant, tick)

        # Reproduction
        _attempt_reproduction(plant, tick, world, env, flora_species_params)

        # Update biotope energy
        env.set_plant_energy(plant.x, plant.y, plant.species_id, plant.energy)

        # Survival check
        if plant.energy < plant.survival_threshold:
            env.clear_plant_energy(plant.x, plant.y, plant.species_id)
            world.unregister_position(entity.entity_id, plant.x, plant.y)
            dead.append(entity.entity_id)

    world.collect_garbage(dead)
    env.rebuild_energy_layer()
