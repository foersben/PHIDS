"""Lifecycle system: plant growth, mycorrhizal network formation, reproduction, and death.

This module implements the first of three ordered per-tick simulation phases executed by the
PHIDS ``SimulationLoop``. The lifecycle phase applies deterministic physiological dynamics to all
registered plant entities before any predator interactions are resolved, ensuring that the energy
state observed by the interaction and signaling phases reflects the current-tick growth outcome.

Per-tick growth increments the energy reserve of each plant by ``base_energy × (growth_rate / 100)``,
clamped to ``max_energy``. Reproduction is attempted on each tick that satisfies the
``reproduction_interval`` constraint and leaves sufficient energy surplus above ``seed_energy_cost``;
the seed is dispersed to a randomly sampled polar coordinate within ``[seed_min_dist, seed_max_dist]``
from the parent, and germination is rejected if the target cell is already occupied by any plant
entity registered in the spatial hash, preventing overcrowding without requiring dense distance
scans. Mycorrhizal root-network formation occurs at configurable intervals (``mycorrhizal_growth_interval_ticks``),
pairing adjacent plants (Manhattan distance 1) that share sufficient energy surplus above their
respective survival thresholds; each connection costs both participants ``connection_cost`` energy
units and is bidirectionally recorded in their ``PlantComponent.mycorrhizal_connections`` sets.
Plants whose energy falls below ``survival_threshold`` are unregistered from the spatial hash,
removed from the energy layer write buffer, and queued for bulk entity destruction via
``ECSWorld.collect_garbage``. Per-cause death counts are accumulated in the ``plant_death_causes``
dict for telemetry attribution.
"""

from __future__ import annotations

import math
import random

from phids.engine.components.plant import PlantComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.shared.constants import SEED_DROP_HEIGHT_DEFAULT, SEED_TERMINAL_VELOCITY_DEFAULT


def _grow(plant: PlantComponent, tick: int) -> None:
    """Apply one incremental growth step and clamp to max energy.

    Args:
        plant: PlantComponent to update.
        tick: Current simulation tick (unused; kept for call-site parity).
    """
    del tick
    growth_amount = plant.base_energy * (plant.growth_rate / 100.0)
    plant.energy = min(plant.energy + growth_amount, plant.max_energy)


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
    if (plant.energy - plant.seed_energy_cost) < plant.survival_threshold:
        return []

    local_wind_x = float(env.wind_vector_x[plant.x, plant.y])
    local_wind_y = float(env.wind_vector_y[plant.x, plant.y])
    wind_speed = math.hypot(local_wind_x, local_wind_y)

    wind_dx = 0.0
    wind_dy = 0.0
    if wind_speed > 1e-9:
        distance = random.uniform(plant.seed_min_dist, plant.seed_max_dist)
        # Approximate downwind shift by flight time (drop-height / terminal velocity), then
        # apply anisotropic turbulent spread aligned with the local wind axis.
        drop_height = max(1e-3, float(getattr(plant, "seed_drop_height", SEED_DROP_HEIGHT_DEFAULT)))
        terminal_velocity = max(
            1e-3,
            float(getattr(plant, "seed_terminal_velocity", SEED_TERMINAL_VELOCITY_DEFAULT)),
        )
        flight_time = drop_height / terminal_velocity
        ux = local_wind_x / wind_speed
        uy = local_wind_y / wind_speed
        mean_parallel = wind_speed * flight_time
        sigma_parallel = max(0.2, 0.35 * distance + 0.25 * mean_parallel)
        sigma_perpendicular = max(0.15, 0.45 * sigma_parallel)
        sampled_parallel = random.gauss(mean_parallel, sigma_parallel)
        sampled_perpendicular = random.gauss(0.0, sigma_perpendicular)
        wind_dx = sampled_parallel * ux - sampled_perpendicular * uy
        wind_dy = sampled_parallel * uy + sampled_perpendicular * ux

    if wind_speed > 1e-9:
        # Wind-active mode uses a single anisotropic Gaussian kernel centered
        # downwind from the parent, avoiding annulus-plus-Gaussian double shifts.
        tx = int(round(plant.x + wind_dx))
        ty = int(round(plant.y + wind_dy))
    else:
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
    plant_death_causes: dict[str, int] | None = None,
) -> tuple[bool, list[int]]:
    """Establish bidirectional root connections between adjacent plants.

    Plants located at Manhattan distance 1 may form symbiotic root
    connections. Each new connection costs ``connection_cost`` energy
    deducted from both participants. Inter-species links are only created
    when ``inter_species`` is True. During one growth invocation, each plant
    can establish at most one new connection so disjoint pairs can grow in
    parallel without a single global bottleneck.

    Args:
        world: ECSWorld registry.
        env: GridEnvironment (used to update plant energy buffers).
        connection_cost: Energy cost per connection establishment.
        inter_species: Allow connections between different species.
        excluded_entity_ids: Plants to ignore (for example, plants already
            marked for removal in the current lifecycle pass).

    Returns:
        tuple[bool, list[int]]: ``(made_connection, dead_entity_ids)`` where
        ``dead_entity_ids`` contains plants that crossed the survival threshold
        due to connection costs and were removed from spatial registration and
        energy layers in this same lifecycle pass.
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

    formed_this_tick: set[int] = set()
    dead_entities: list[int] = []
    dead_entity_ids: set[int] = set()
    made_connection = False

    for plant in plants:
        if plant.entity_id in dead_entity_ids:
            continue
        if plant.entity_id in formed_this_tick:
            continue
        if (plant.energy - connection_cost) < plant.survival_threshold:
            continue

        neighbours: list[PlantComponent] = []
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = plant.x + dx, plant.y + dy
            if not (0 <= nx < env.width and 0 <= ny < env.height):
                continue
            for neighbour in pos_index.get((nx, ny), []):
                if neighbour.entity_id in dead_entity_ids:
                    continue
                if neighbour.entity_id == plant.entity_id:
                    continue
                if neighbour.entity_id in formed_this_tick:
                    continue
                if neighbour.entity_id in plant.mycorrhizal_connections:
                    continue
                if not inter_species and neighbour.species_id != plant.species_id:
                    continue
                if (neighbour.energy - connection_cost) < neighbour.survival_threshold:
                    continue
                neighbours.append(neighbour)

        if not neighbours:
            continue

        neighbour = random.choice(neighbours)
        plant.mycorrhizal_connections.add(neighbour.entity_id)
        neighbour.mycorrhizal_connections.add(plant.entity_id)
        plant.energy -= connection_cost
        neighbour.energy -= connection_cost
        plant.last_energy_loss_cause = "death_mycorrhiza"
        neighbour.last_energy_loss_cause = "death_mycorrhiza"
        formed_this_tick.add(plant.entity_id)
        formed_this_tick.add(neighbour.entity_id)
        env.set_plant_energy(plant.x, plant.y, plant.species_id, plant.energy)
        env.set_plant_energy(neighbour.x, neighbour.y, neighbour.species_id, neighbour.energy)
        made_connection = True

        for participant in (plant, neighbour):
            if participant.entity_id in dead_entity_ids:
                continue
            if participant.energy >= participant.survival_threshold:
                continue

            cause_key = participant.last_energy_loss_cause or "death_background_deficit"
            if plant_death_causes is not None:
                plant_death_causes[cause_key] = plant_death_causes.get(cause_key, 0) + 1
            env.clear_plant_energy(participant.x, participant.y, participant.species_id)
            world.unregister_position(participant.entity_id, participant.x, participant.y)
            dead_entity_ids.add(participant.entity_id)
            dead_entities.append(participant.entity_id)

    return made_connection, dead_entities


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
    plant_death_causes: dict[str, int] | None = None,
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
        plant_death_causes: Mapping of death causes to their respective counts.
    """
    dead: list[int] = []

    for entity in list(world.query(PlantComponent)):
        plant: PlantComponent = entity.get_component(PlantComponent)
        plant.last_energy_loss_cause = None

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
            cause_key = plant.last_energy_loss_cause or "death_background_deficit"
            if plant_death_causes is not None:
                plant_death_causes[cause_key] = plant_death_causes.get(cause_key, 0) + 1
            env.clear_plant_energy(plant.x, plant.y, plant.species_id)
            world.unregister_position(entity.entity_id, plant.x, plant.y)
            dead.append(entity.entity_id)

    # Establish new mycorrhizal root connections between adjacent plants
    if _should_attempt_mycorrhizal_growth(tick, mycorrhizal_growth_interval_ticks):
        _, mycorrhiza_dead = _establish_mycorrhizal_connections(
            world,
            env,
            mycorrhizal_connection_cost,
            mycorrhizal_inter_species,
            excluded_entity_ids=set(dead),
            plant_death_causes=plant_death_causes,
        )
        dead.extend(mycorrhiza_dead)

    world.collect_garbage(dead)
