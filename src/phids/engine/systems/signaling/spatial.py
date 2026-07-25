# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Spatial lookup utilities for the signaling system."""

from __future__ import annotations

from typing import TYPE_CHECKING

from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent

if TYPE_CHECKING:
    from phids.engine.core.ecs import ECSWorld


def _build_swarm_population_index(world: ECSWorld) -> dict[tuple[int, int, int], int]:
    """Return a per-cell, per-species swarm-population index for one signaling tick."""
    populations: dict[tuple[int, int, int], int] = {}
    for entity in world.query(SwarmComponent):
        swarm: SwarmComponent = entity.get_component(SwarmComponent)
        key = (swarm.x, swarm.y, swarm.species_id)
        populations[key] = populations.get(key, 0) + swarm.population
    return populations


def _co_located_swarm_population(
    world: ECSWorld,
    x: int,
    y: int,
    herbivore_species_id: int,
) -> int:
    """Return total population of a herbivore species at one grid cell.

    Args:
        world: ECSWorld used for spatial hash lookup.
        x: The X-axis spatial grid coordinate.
        y: The Y-axis spatial grid coordinate.
        herbivore_species_id: Herbivore species to aggregate.

    Returns:
        int: Sum of populations for matching swarms at ``(x, y)``.

    """
    total_population = 0
    for co_eid in world.entities_at(x, y):
        if not world.has_entity(co_eid):
            continue
        co_entity = world.get_entity(co_eid)
        if not co_entity.has_component(SwarmComponent):
            continue
        swarm: SwarmComponent = co_entity.get_component(SwarmComponent)
        if swarm.species_id == herbivore_species_id:
            total_population += swarm.population
    return total_population


def _collect_mycorrhizal_targets(
    source_plant: PlantComponent,
    world: ECSWorld,
    mycorrhizal_inter_species: bool,
) -> list[PlantComponent]:
    """Return relay-eligible neighbouring plants connected via mycorrhiza.

    Args:
        source_plant: Originating plant component.
        world: ECSWorld for neighbour lookup.
        mycorrhizal_inter_species: Whether cross-species relay is allowed.

    Returns:
        list[PlantComponent]: Relay targets that are alive and species-compatible.

    """
    targets: list[PlantComponent] = []
    for neighbour_id in source_plant.mycorrhizal_connections:
        if not world.has_entity(neighbour_id):
            continue
        neighbour_entity = world.get_entity(neighbour_id)
        if not neighbour_entity.has_component(PlantComponent):
            continue
        neighbour = neighbour_entity.get_component(PlantComponent)
        if not mycorrhizal_inter_species and neighbour.species_id != source_plant.species_id:
            continue
        targets.append(neighbour)
    return targets
