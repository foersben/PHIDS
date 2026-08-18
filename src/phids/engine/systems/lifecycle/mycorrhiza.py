# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Mycorrhizal root-network formation logic."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from phids.engine.components.plant import PlantComponent
from phids.engine.systems.lifecycle.culling import _cull_plant_if_dead
from phids.engine.systems.lifecycle.growth import SLOW_TICK_STRIDE

if TYPE_CHECKING:
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld


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
