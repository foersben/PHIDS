# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for flora seed germination fallbacks and occupied cell guards."""

from __future__ import annotations

import pytest

from phids.engine.components.plant import PlantComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.engine.systems.lifecycle.reproduction import _attempt_reproduction


@pytest.mark.unit
def test_try_reproduce_flora_missing_species_params_returns_empty() -> None:
    """Verify that seed germination returns [] when target species params are missing from registry.

    Raises:
        AssertionError: If reproduction generates entities when species parameters are absent.
    """
    world = ECSWorld()
    env = GridEnvironment(16, 16)
    plant_entity = world.create_entity()

    plant = PlantComponent(
        entity_id=plant_entity.entity_id,
        species_id=999,  # Non-existent species ID
        x=5,
        y=5,
        energy=100.0,
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
    world.register_position(plant_entity.entity_id, 5, 5)

    result = _attempt_reproduction(
        plant=plant,
        tick=100,
        world=world,
        env=env,
        flora_species_params={},  # Empty dictionary -> missing species ID 999
    )

    assert result == []
