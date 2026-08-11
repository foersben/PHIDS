# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for defense upkeep energy processing and emission failure branches."""

from __future__ import annotations

import pytest

from phids.engine.components.plant import PlantComponent
from phids.engine.components.substances import SubstanceComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.engine.systems.signaling.emission import _process_substance_energy_maintenance


@pytest.mark.unit
def test_process_defense_upkeep_deactivates_when_unaffordable() -> None:
    """Verify defense deactivates when upkeep would drop plant energy below survival threshold."""
    world = ECSWorld()
    env = GridEnvironment(16, 16)

    plant_entity = world.create_entity()
    plant = PlantComponent(
        entity_id=plant_entity.entity_id,
        species_id=0,
        x=5,
        y=5,
        energy=10.0,
        max_energy=100.0,
        base_energy=20.0,
        growth_rate=0.05,
        survival_threshold=8.0,  # 10 - 5 = 5 < 8 survival threshold
        reproduction_interval=50,
        seed_min_dist=1.0,
        seed_max_dist=5.0,
        seed_energy_cost=10.0,
    )
    world.add_component(plant_entity.entity_id, plant)

    sub_entity = world.create_entity()
    sub = SubstanceComponent(
        entity_id=sub_entity.entity_id,
        substance_id=0,
        owner_plant_id=plant_entity.entity_id,
        active=True,
        energy_cost_per_tick=5.0,
        triggered_this_tick=False,
        irreversible=False,
    )

    active_by_owner = {plant_entity.entity_id: {0}}
    dead_plants: list[int] = []
    dead_plant_ids: set[int] = set()
    dead_substances: list[int] = []

    res = _process_substance_energy_maintenance(
        sub,
        plant,
        env,
        world,
        active_by_owner,
        dead_plant_ids,
        dead_substances,
        dead_plants,
        None,
        sub_entity.entity_id,
    )

    assert res is False
    assert sub.active is False
    assert sub.aftereffect_remaining_ticks == 0
    assert 0 not in active_by_owner[plant_entity.entity_id]


@pytest.mark.unit
def test_process_defense_upkeep_plant_death_attribution() -> None:
    """Verify plant death caused by defense upkeep records death_defense_maintenance cause."""
    world = ECSWorld()
    env = GridEnvironment(16, 16)

    plant_entity = world.create_entity()
    plant = PlantComponent(
        entity_id=plant_entity.entity_id,
        species_id=0,
        x=5,
        y=5,
        energy=10.0,
        max_energy=100.0,
        base_energy=20.0,
        growth_rate=0.05,
        survival_threshold=8.0,
        reproduction_interval=50,
        seed_min_dist=1.0,
        seed_max_dist=5.0,
        seed_energy_cost=10.0,
    )
    world.add_component(plant_entity.entity_id, plant)
    world.register_position(plant_entity.entity_id, 5, 5)

    sub_entity = world.create_entity()
    sub = SubstanceComponent(
        entity_id=sub_entity.entity_id,
        substance_id=0,
        owner_plant_id=plant_entity.entity_id,
        active=True,
        energy_cost_per_tick=5.0,
        triggered_this_tick=True,  # Bypass early unaffordable guard to execute energy deduction
        irreversible=True,
    )

    active_by_owner = {plant_entity.entity_id: {0}}
    death_causes: dict[str, int] = {}
    dead_plants: list[int] = []
    dead_plant_ids: set[int] = set()
    dead_substances: list[int] = []

    res = _process_substance_energy_maintenance(
        sub,
        plant,
        env,
        world,
        active_by_owner,
        dead_plant_ids,
        dead_substances,
        dead_plants,
        death_causes,
        sub_entity.entity_id,
    )

    assert res is False
    assert plant.last_energy_loss_cause == "death_defense_maintenance"
    assert death_causes["death_defense_maintenance"] == 1
    assert plant_entity.entity_id in dead_plants
    assert sub_entity.entity_id in dead_substances
