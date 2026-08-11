# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for spatial signaling queries, mycorrhizal connection guards, and non-plant entity filtering."""

from __future__ import annotations

import pytest

from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.ecs import ECSWorld
from phids.engine.systems.signaling.spatial import (
    _co_located_swarm_population,
    _collect_mycorrhizal_targets,
)


@pytest.mark.unit
def test_get_cell_herbivore_population_filters_non_swarms() -> None:
    """Verify _co_located_swarm_population ignores destroyed or non-swarm co-located entities.

    Raises:
        AssertionError: If population query counts non-swarm entities or wrong species.
    """
    world = ECSWorld()
    plant_e = world.create_entity()
    world.add_component(
        plant_e.entity_id,
        PlantComponent(
            entity_id=plant_e.entity_id,
            species_id=0,
            x=3,
            y=3,
            energy=50.0,
            max_energy=100.0,
            base_energy=20.0,
            growth_rate=0.05,
            survival_threshold=5.0,
            reproduction_interval=50,
            seed_min_dist=1.0,
            seed_max_dist=5.0,
            seed_energy_cost=10.0,
        ),
    )
    world.register_position(plant_e.entity_id, 3, 3)

    swarm_e = world.create_entity()
    world.add_component(
        swarm_e.entity_id,
        SwarmComponent(
            entity_id=swarm_e.entity_id,
            species_id=1,
            x=3,
            y=3,
            population=25,
            initial_population=25,
            energy=50.0,
            energy_min=5.0,
            velocity=1,
            consumption_rate=5.0,
        ),
    )
    world.register_position(swarm_e.entity_id, 3, 3)

    # Query species 1 -> returns 25
    assert _co_located_swarm_population(world, 3, 3, 1) == 25
    # Query species 0 -> returns 0 (plant entity ignored)
    assert _co_located_swarm_population(world, 3, 3, 0) == 0


@pytest.mark.unit
def test_collect_mycorrhizal_targets_filtering() -> None:
    """Verify mycorrhizal target collection handles missing entities, non-plant entities, and same-species filters.

    Raises:
        AssertionError: If mycorrhizal collection returns stale IDs or incompatible species targets.
    """
    world = ECSWorld()

    # Plant 1 (Species 0)
    p1_e = world.create_entity()
    p1 = PlantComponent(
        entity_id=p1_e.entity_id,
        species_id=0,
        x=2,
        y=2,
        energy=50.0,
        max_energy=100.0,
        base_energy=20.0,
        growth_rate=0.05,
        survival_threshold=5.0,
        reproduction_interval=50,
        seed_min_dist=1.0,
        seed_max_dist=5.0,
        seed_energy_cost=10.0,
    )
    world.add_component(p1_e.entity_id, p1)

    # Non-plant entity ID (99999) and swarm entity connected
    swarm_e = world.create_entity()
    p1.mycorrhizal_connections = [99999, swarm_e.entity_id]

    # Plant 2 (Species 1) - cross species
    p2_e = world.create_entity()
    p2 = PlantComponent(
        entity_id=p2_e.entity_id,
        species_id=1,
        x=2,
        y=3,
        energy=50.0,
        max_energy=100.0,
        base_energy=20.0,
        growth_rate=0.05,
        survival_threshold=5.0,
        reproduction_interval=50,
        seed_min_dist=1.0,
        seed_max_dist=5.0,
        seed_energy_cost=10.0,
    )
    world.add_component(p2_e.entity_id, p2)
    p1.mycorrhizal_connections.append(p2_e.entity_id)

    # When inter-species is False, Plant 2 is filtered out -> []
    res_same = _collect_mycorrhizal_targets(p1, world, mycorrhizal_inter_species=False)
    assert res_same == []

    # When inter-species is True, Plant 2 is included -> [p2]
    res_inter = _collect_mycorrhizal_targets(p1, world, mycorrhizal_inter_species=True)
    assert res_inter == [p2]
