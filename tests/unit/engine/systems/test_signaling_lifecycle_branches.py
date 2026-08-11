# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for signaling substance lifecycle, orphan cleanup, and aftereffect countdown branches."""

from __future__ import annotations

import pytest

from phids.engine.components.plant import PlantComponent
from phids.engine.components.substances import SubstanceComponent
from phids.engine.core.ecs import ECSWorld
from phids.engine.systems.signaling.lifecycle import _process_single_aftereffect


@pytest.mark.unit
def test_signaling_lifecycle_orphan_substance_cleanup() -> None:
    """Verify that orphan substances whose owner plant entity was destroyed are appended to dead_substances.

    Raises:
        AssertionError: If orphan substance entity is not marked for garbage collection.
    """
    world = ECSWorld()
    sub_entity = world.create_entity()

    sub = SubstanceComponent(
        entity_id=sub_entity.entity_id,
        substance_id=1,
        owner_plant_id=99999,  # Non-existent owner plant
        active=True,
    )
    world.add_component(sub_entity.entity_id, sub)

    active_map = {99999: {1}}
    dead_substances: list[int] = []

    _process_single_aftereffect(
        sub=sub,
        entity_id=sub_entity.entity_id,
        world=world,
        active_substance_ids_by_owner=active_map,
        dead_plant_ids=set(),
        dead_substances=dead_substances,
    )

    assert sub_entity.entity_id in dead_substances


@pytest.mark.unit
def test_signaling_lifecycle_dead_plant_owner_deactivation() -> None:
    """Verify substance deactivation when owner plant is in dead_plant_ids set.

    Raises:
        AssertionError: If substance is not deactivated when owner plant dies.
    """
    world = ECSWorld()
    plant_entity = world.create_entity()
    plant = PlantComponent(
        entity_id=plant_entity.entity_id,
        species_id=0,
        x=2,
        y=2,
        energy=10.0,
        max_energy=100.0,
        base_energy=20.0,
        growth_rate=0.05,
        survival_threshold=5.0,
        reproduction_interval=50,
        seed_min_dist=1.0,
        seed_max_dist=5.0,
        seed_energy_cost=10.0,
    )
    world.add_component(plant_entity.entity_id, plant)

    sub_entity = world.create_entity()
    sub = SubstanceComponent(
        entity_id=sub_entity.entity_id,
        substance_id=1,
        owner_plant_id=plant_entity.entity_id,
        active=True,
    )
    world.add_component(sub_entity.entity_id, sub)

    active_map = {plant_entity.entity_id: {1}}
    dead_substances: list[int] = []

    _process_single_aftereffect(
        sub=sub,
        entity_id=sub_entity.entity_id,
        world=world,
        active_substance_ids_by_owner=active_map,
        dead_plant_ids={plant_entity.entity_id},
        dead_substances=dead_substances,
    )

    assert sub.active is False
    assert sub_entity.entity_id in dead_substances
    assert 1 not in active_map.get(plant_entity.entity_id, set())


@pytest.mark.unit
def test_signaling_lifecycle_aftereffect_countdown_expiration() -> None:
    """Verify aftereffect tick countdown and final deactivation upon reaching 0 ticks.

    Raises:
        AssertionError: If aftereffect ticks fail to countdown or deactivate.
    """
    world = ECSWorld()
    plant_entity = world.create_entity()
    plant = PlantComponent(
        entity_id=plant_entity.entity_id,
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
    world.add_component(plant_entity.entity_id, plant)

    sub_entity = world.create_entity()
    sub = SubstanceComponent(
        entity_id=sub_entity.entity_id,
        substance_id=1,
        owner_plant_id=plant_entity.entity_id,
        active=True,
        triggered_this_tick=False,
        irreversible=False,
        aftereffect_remaining_ticks=2,
    )
    world.add_component(sub_entity.entity_id, sub)

    active_map = {plant_entity.entity_id: {1}}
    dead_substances: list[int] = []

    # First tick -> countdown from 2 to 1, still active
    _process_single_aftereffect(
        sub=sub,
        entity_id=sub_entity.entity_id,
        world=world,
        active_substance_ids_by_owner=active_map,
        dead_plant_ids=set(),
        dead_substances=dead_substances,
    )
    assert sub.aftereffect_remaining_ticks == 1
    assert sub.active is True

    # Second tick -> countdown from 1 to 0 -> deactivated
    _process_single_aftereffect(
        sub=sub,
        entity_id=sub_entity.entity_id,
        world=world,
        active_substance_ids_by_owner=active_map,
        dead_plant_ids=set(),
        dead_substances=dead_substances,
    )
    assert sub.aftereffect_remaining_ticks == 0
    assert sub.active is False
