"""Lifecycle system: plant growth, reproduction, mycorrhizal networking and death.

This module implements per-tick plant updates including growth according
to species parameters, reproduction attempts, establishment of symbiotic
root connections, and culling of dead plants.  It should run before
interaction and signaling phases.
"""

from __future__ import annotations

import math
import random

from phids.engine.components.plant import PlantComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld


def _grow(plant: PlantComponent, tick: int) -> None:
    """Apply the growth formula and clamp to max energy.

    Args:
        plant: PlantComponent to update.
        tick: Current simulation tick used in the growth formula.
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
    """Attempt reproduction for a plant when interval and energy permit.

    Args:
        plant: Parent plant component.
        tick: Current simulation tick.
        world: ECSWorld to allocate new entities.
        env: GridEnvironment to update plant energy layers.
        flora_species_params: Mapping of species_id to species parameters.

    Returns:
        list[PlantComponent]: Newly created plant components (empty if none).
    """
    from phids.api.schemas import FloraSpeciesParams  # local import avoids circulars

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


def _establish_mycorrhizal_connections(
    world: ECSWorld,
    env: GridEnvironment,
    connection_cost: float,
    inter_species: bool,
    excluded_entity_ids: set[int] | None = None,
) -> bool:
    """Establish bidirectional root connections between adjacent plants.

    Plants located at Manhattan distance 1 may form symbiotic root
    connections.  Each new connection costs ``connection_cost`` energy
    deducted from both participants.  Inter-species links are only created
    when ``inter_species`` is True.  To keep growth gradual and deterministic,
    the function establishes at most one new connection per invocation.

    Args:
        world: ECSWorld registry.
        env: GridEnvironment (used to update plant energy buffers).
        connection_cost: Energy cost per connection establishment.
        inter_species: Allow connections between different species.
        excluded_entity_ids: Plants to ignore (for example, plants already
            marked for removal in the current lifecycle pass).

    Returns:
        bool: ``True`` when a new connection was created.
    """
    excluded = excluded_entity_ids or set()
    plants: list[PlantComponent] = [
        e.get_component(PlantComponent)
        for e in world.query(PlantComponent)
        if e.entity_id not in excluded
    ]
    plants.sort(key=lambda plant: (plant.y, plant.x, plant.species_id, plant.entity_id))

    # Index plants by position for fast neighbour lookup
    pos_index: dict[tuple[int, int], list[PlantComponent]] = {}
    for p in plants:
        pos_index.setdefault((p.x, p.y), []).append(p)

    for plant in plants:
        for dx, dy in ((1, 0), (0, 1)):
            nx, ny = plant.x + dx, plant.y + dy
            if not (0 <= nx < env.width and 0 <= ny < env.height):
                continue
            for neighbour in pos_index.get((nx, ny), []):
                if neighbour.entity_id == plant.entity_id:
                    continue
                # Already connected
                if neighbour.entity_id in plant.mycorrhizal_connections:
                    continue
                # Species restriction
                if not inter_species and neighbour.species_id != plant.species_id:
                    continue
                # Both plants must afford the connection cost
                if plant.energy < connection_cost or neighbour.energy < connection_cost:
                    continue
                # Establish bidirectional link and pay cost
                plant.mycorrhizal_connections.add(neighbour.entity_id)
                neighbour.mycorrhizal_connections.add(plant.entity_id)
                plant.energy -= connection_cost
                neighbour.energy -= connection_cost
                env.set_plant_energy(plant.x, plant.y, plant.species_id, plant.energy)
                env.set_plant_energy(
                    neighbour.x, neighbour.y, neighbour.species_id, neighbour.energy
                )
                return True

    return False


def _should_attempt_mycorrhizal_growth(tick: int, growth_interval_ticks: int) -> bool:
    """Return whether this lifecycle tick may grow one new root link.

    The first growth attempt happens only after ``growth_interval_ticks``
    lifecycle passes have elapsed, which keeps root-network expansion slow
    by default while remaining deterministic.
    """
    return growth_interval_ticks <= 1 or (tick + 1) % growth_interval_ticks == 0


def run_lifecycle(
    world: ECSWorld,
    env: GridEnvironment,
    tick: int,
    flora_species_params: dict[int, object],
    mycorrhizal_connection_cost: float = 1.0,
    mycorrhizal_growth_interval_ticks: int = 8,
    mycorrhizal_inter_species: bool = False,
) -> None:
    """Execute one lifecycle tick: grow, connect, reproduce, and cull.

    Args:
        world: The ECS world registry.
        env: The GridEnvironment instance.
        tick: Current simulation tick index.
        flora_species_params: Mapping of species_id to species parameters.
        mycorrhizal_connection_cost: Energy cost per new root connection.
        mycorrhizal_growth_interval_ticks: Ticks between new root-growth
            attempts. At most one new link is created per attempt.
        mycorrhizal_inter_species: Allow inter-species root connections.
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

        # Prune dead mycorrhizal links
        plant.mycorrhizal_connections = {
            eid for eid in plant.mycorrhizal_connections if world.has_entity(eid)
        }

        # Survival check
        if plant.energy < plant.survival_threshold:
            env.clear_plant_energy(plant.x, plant.y, plant.species_id)
            world.unregister_position(entity.entity_id, plant.x, plant.y)
            dead.append(entity.entity_id)

    # Establish new mycorrhizal root connections between adjacent plants
    if _should_attempt_mycorrhizal_growth(tick, mycorrhizal_growth_interval_ticks):
        _establish_mycorrhizal_connections(
            world,
            env,
            mycorrhizal_connection_cost,
            mycorrhizal_inter_species,
            excluded_entity_ids=set(dead),
        )

    world.collect_garbage(dead)
    env.rebuild_energy_layer()
