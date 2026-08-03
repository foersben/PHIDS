# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Lifecycle system: plant growth, mycorrhizal network formation, reproduction, and death.

This module implements the first of three ordered per-tick simulation phases executed by the
PHIDS ``SimulationLoop``. The lifecycle phase applies deterministic physiological dynamics to all
registered plant entities before any herbivore interactions are resolved, ensuring that the energy
state observed by the interaction and signaling phases reflects the current-tick growth outcome.

Per-tick growth increments the energy reserve of each plant by ``base_energy * (growth_rate / 100)``,
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
from typing import TYPE_CHECKING

from phids.engine.components.plant import PlantComponent

if TYPE_CHECKING:
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld


# Stride constants for modulo-gated biological timescales.
# All per-tick parameter values are multiplied by the appropriate stride
# when executed inside the corresponding sub-loop block.
SLOW_TICK_STRIDE: int = 168  # hours per weekly slow-loop gate


def _grow(plant: PlantComponent, tick: int) -> None:
    """Apply one accumulated weekly growth step and clamp to max energy.

    Called exclusively inside the Slow Loop (every 168 ticks). The growth
    amount is scaled by SLOW_TICK_STRIDE so that per-tick rate values defined
    in FloraSpeciesParams remain the authoritative unit. This avoids IEEE 754
    subnormal float truncation that occurs when per-tick increments (e.g.
    0.00005) fall below the epsilon threshold.

    Args:
        plant: PlantComponent to update.
        tick: Current simulation tick (unused; kept for call-site parity).
    """
    del tick
    growth_amount = plant.base_energy * (plant.growth_rate / 100.0) * SLOW_TICK_STRIDE
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
    )
    world.add_component(new_entity.entity_id, new_plant)
    world.register_position(new_entity.entity_id, tx, ty)
    env.set_plant_energy(tx, ty, plant.species_id, params.base_energy)
    env.set_apparent_nutrition(tx, ty, plant.apparent_nutrition_factor)
    return [new_plant]


def _is_mycorrhizal_neighbour_eligible(
    neighbour: PlantComponent,
    plant: PlantComponent,
    formed_this_tick: set[int],
    dead_entity_ids: set[int],
    connection_cost: float,
    inter_species: bool,
) -> bool:
    """Return whether a single neighbour is eligible for connection.

    Args:
        neighbour: The neighbour plant component to check.
        plant: The plant component.
        formed_this_tick: Set of entity ids that have already formed connections this tick.
        dead_entity_ids: Set of entity ids that are dead.
        connection_cost: The cost of forming a connection.
        inter_species: Whether to allow inter-species connections.

    Returns:
        True if the neighbour is eligible for connection, False otherwise.
    """
    if neighbour.entity_id in dead_entity_ids:
        return False
    if neighbour.entity_id == plant.entity_id:
        return False
    if neighbour.entity_id in formed_this_tick:
        return False
    if neighbour.entity_id in plant.mycorrhizal_connections:
        return False
    if not inter_species and neighbour.species_id != plant.species_id:
        return False
    if (neighbour.energy - connection_cost) < neighbour.survival_threshold:
        return False
    return True


def _find_valid_mycorrhizal_neighbours(
    plant: PlantComponent,
    env: GridEnvironment,
    pos_index: dict[tuple[int, int], list[PlantComponent]],
    formed_this_tick: set[int],
    dead_entity_ids: set[int],
    connection_cost: float,
    inter_species: bool,
) -> list[PlantComponent]:
    """Scan cardinal neighbours and return those eligible for connection.

    Args:
        plant: The plant component to check.
        env: The grid environment.
        pos_index: Dictionary mapping grid positions to plant components.
        formed_this_tick: Set of entity ids that have already formed connections this tick.
        dead_entity_ids: Set of entity ids that are dead.
        connection_cost: The cost of forming a connection.
        inter_species: Whether to allow inter-species connections.

    Returns:
        List of eligible neighbours.
    """
    neighbours: list[PlantComponent] = []
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        nx, ny = (plant.x + dx) % env.width, (plant.y + dy) % env.height
        for neighbour in pos_index.get((nx, ny), []):
            if _is_mycorrhizal_neighbour_eligible(
                neighbour=neighbour,
                plant=plant,
                formed_this_tick=formed_this_tick,
                dead_entity_ids=dead_entity_ids,
                connection_cost=connection_cost,
                inter_species=inter_species,
            ):
                neighbours.append(neighbour)
    return neighbours


def _cull_plant_if_dead(
    plant: PlantComponent,
    world: ECSWorld,
    env: GridEnvironment,
    dead_entity_ids: set[int],
    dead_entities: list[int],
    plant_death_causes: dict[str, int] | None = None,
) -> None:
    """Check plant survival, update cause registry, and clear from spatial grids.

    Args:
        plant: The plant component to check.
        world: The ECS world.
        env: The grid environment.
        dead_entity_ids: Set of dead entity ids.
        dead_entities: List of dead entities.
        plant_death_causes: Dictionary to store death causes.
    """
    if plant.entity_id in dead_entity_ids:
        return
    if plant.energy >= plant.survival_threshold:
        return

    cause_key = plant.last_energy_loss_cause or "death_background_deficit"
    if plant_death_causes is not None:
        plant_death_causes[cause_key] = plant_death_causes.get(cause_key, 0) + 1
    env.clear_plant_energy(plant.x, plant.y, plant.species_id)
    world.unregister_position(plant.entity_id, plant.x, plant.y)
    dead_entity_ids.add(plant.entity_id)
    dead_entities.append(plant.entity_id)


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
    upkeep evaluates connection feasibility. Each plant can establish at most
    one new connection so disjoint pairs can grow in parallel without a single
    global bottleneck.

    Args:
        world: The central ECSWorld instance containing all entity component mappings and active systems.
        env: GridEnvironment (used to update plant energy buffers).
        connection_cost: Energy cost per connection establishment.
        inter_species: Allow connections between different species.
        excluded_entity_ids: Plants to ignore (for example, plants already
            marked for removal in the current lifecycle pass).
        plant_death_causes: Optional dictionary tracking causes of plant death.

    Returns:
        ``(made_connection, dead_entity_ids)`` where
        ``dead_entity_ids`` contains plants that crossed the survival threshold
        due to connection costs and were removed from spatial registration and
        energy layers in this same lifecycle pass.
    """
    excluded = excluded_entity_ids or set()
    plants: list[PlantComponent] = [
        e.get_component(PlantComponent) for e in world.query(PlantComponent) if e.entity_id not in excluded
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

        neighbours = _find_valid_mycorrhizal_neighbours(
            plant=plant,
            env=env,
            pos_index=pos_index,
            formed_this_tick=formed_this_tick,
            dead_entity_ids=dead_entity_ids,
            connection_cost=connection_cost,
            inter_species=inter_species,
        )

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
        env.set_apparent_nutrition(plant.x, plant.y, plant.apparent_nutrition_factor)
        env.set_apparent_nutrition(neighbour.x, neighbour.y, neighbour.apparent_nutrition_factor)
        made_connection = True

        for participant in (plant, neighbour):
            _cull_plant_if_dead(
                plant=participant,
                world=world,
                env=env,
                dead_entity_ids=dead_entity_ids,
                dead_entities=dead_entities,
                plant_death_causes=plant_death_causes,
            )

    return made_connection, dead_entities


def _should_attempt_mycorrhizal_growth(tick: int, growth_interval_ticks: int) -> bool:
    """Return whether this lifecycle tick may grow new root links.

    Supports both continuous per-tick interval gating (for direct unit calls)
    and weekly slow-loop stride gating (for full simulation runs).

    Args:
        tick: The current tick.
        growth_interval_ticks: The interval between growth attempts.

    Returns:
        True if this lifecycle tick may grow new root links, False otherwise.
    """
    if growth_interval_ticks <= 1:
        return True
    if (tick + 1) % growth_interval_ticks == 0:
        return True
    if tick > 0 and tick % SLOW_TICK_STRIDE == 0:
        slow_step = tick // SLOW_TICK_STRIDE
        return slow_step % max(1, growth_interval_ticks) == 0 or growth_interval_ticks <= SLOW_TICK_STRIDE
    return False


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

    for entity in world.query(PlantComponent):
        plant: PlantComponent = entity.get_component(PlantComponent)
        plant.last_energy_loss_cause = None

        # Growth
        _grow(plant, tick)

        # Apply continuous mycorrhizal carbon tax
        if plant.mycorrhizal_tax_per_link > 0.0 and plant.mycorrhizal_connections:
            plant.energy -= plant.mycorrhizal_tax_per_link * len(plant.mycorrhizal_connections)

        # Reproduction
        _attempt_reproduction(plant, tick, world, env, flora_species_params)

        # Update biotope energy
        env.set_plant_energy(plant.x, plant.y, plant.species_id, plant.energy)
        env.set_apparent_nutrition(plant.x, plant.y, plant.apparent_nutrition_factor)

        # Prune dead mycorrhizal links
        plant.mycorrhizal_connections = {eid for eid in plant.mycorrhizal_connections if world.has_entity(eid)}

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
