# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit test suite for spatial hash toroidal seam wrapping and mycorrhizal target filtering."""

from __future__ import annotations

from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.ecs import ECSWorld
from phids.engine.systems.signaling.spatial import (
    _co_located_swarm_population,
    _collect_mycorrhizal_targets,
    toroidal_distance,
)


def test_toroidal_distance_seam_wrapping() -> None:
    """Verify toroidal_distance shortest distance calculation across grid seams."""
    width, height = 40, 40
    # 1. Straight distance
    d1 = toroidal_distance(5, 5, 10, 5, width, height)
    assert d1 == 5.0

    # 2. Seam wrapping (x=39 to x=1)
    d2 = toroidal_distance(39, 10, 1, 10, width, height)
    assert d2 == 2.0


def test_co_located_swarm_population_filtering() -> None:
    """Verify _co_located_swarm_population species filtering at spatial coordinates."""
    world = ECSWorld()

    e1 = world.create_entity()
    sw1 = SwarmComponent(
        entity_id=e1.entity_id,
        species_id=0,
        x=0,
        y=0,
        population=50,
        initial_population=50,
        energy=10.0,
        energy_min=1.0,
        velocity=1,
        consumption_rate=1.0,
    )
    world.add_component(e1.entity_id, sw1)
    world.register_position(e1.entity_id, 0, 0)

    e2 = world.create_entity()
    sw2 = SwarmComponent(
        entity_id=e2.entity_id,
        species_id=1,
        x=0,
        y=0,
        population=30,
        initial_population=30,
        energy=10.0,
        energy_min=1.0,
        velocity=1,
        consumption_rate=1.0,
    )
    world.add_component(e2.entity_id, sw2)
    world.register_position(e2.entity_id, 0, 0)

    # Filter species 0
    pop0 = _co_located_swarm_population(world, 0, 0, herbivore_species_id=0)
    assert pop0 == 50

    # Filter species 1
    pop1 = _co_located_swarm_population(world, 0, 0, herbivore_species_id=1)
    assert pop1 == 30

    # Non-existent species
    pop_none = _co_located_swarm_population(world, 0, 0, herbivore_species_id=99)
    assert pop_none == 0


def test_collect_mycorrhizal_targets_dead_entities() -> None:
    """Verify _collect_mycorrhizal_targets filters out destroyed or dead neighbor entities."""
    world = ECSWorld()

    p1_entity = world.create_entity()
    p1 = PlantComponent(
        entity_id=p1_entity.entity_id,
        species_id=0,
        x=5,
        y=5,
        energy=20.0,
        max_energy=100.0,
        base_energy=10.0,
        growth_rate=1.0,
        survival_threshold=1.0,
        reproduction_interval=5,
        seed_min_dist=1.0,
        seed_max_dist=3.0,
        seed_energy_cost=5.0,
    )
    world.add_component(p1_entity.entity_id, p1)

    p2_entity = world.create_entity()
    p2 = PlantComponent(
        entity_id=p2_entity.entity_id,
        species_id=0,
        x=5,
        y=6,
        energy=20.0,
        max_energy=100.0,
        base_energy=10.0,
        growth_rate=1.0,
        survival_threshold=1.0,
        reproduction_interval=5,
        seed_min_dist=1.0,
        seed_max_dist=3.0,
        seed_energy_cost=5.0,
    )
    world.add_component(p2_entity.entity_id, p2)

    # Connect p1 to p2 and a non-existent entity 999
    p1.mycorrhizal_connections = [p2_entity.entity_id, 999]

    targets = _collect_mycorrhizal_targets(p1, world, mycorrhizal_inter_species=True)
    assert len(targets) == 1
    assert targets[0].entity_id == p2_entity.entity_id
