# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Focused mutation pilot tests for Phase 1 interaction, lifecycle, and signaling systems."""

from __future__ import annotations

import math

import pytest

from phids.api.schemas.species import (
    FloraSpeciesParams,
    HerbivoreResistancesSchema,
    HerbivoreSpeciesParams,
    PassiveDefensesSchema,
)
from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.engine.systems.interaction.feeding import _feed_on_single_plant
from phids.engine.systems.signaling.lifecycle import _phase_manage_nutrition_recovery

pytestmark = pytest.mark.mutation_pilot


def test_holling_type_ii_saturating_feeding_and_mechanical_damage() -> None:
    """Verify exact Holling Type II saturation formula and mechanical mouthpart damage casualties."""
    env = GridEnvironment(width=10, height=10, num_signals=1, num_toxins=1)
    tile_populations = [0] * 100

    swarm = SwarmComponent(
        entity_id=0,
        species_id=0,
        x=2,
        y=2,
        population=100,
        initial_population=100,
        energy=50.0,
        energy_min=1.0,
        velocity=1,
        consumption_rate=2.0,
    )

    plant = PlantComponent(
        entity_id=1,
        species_id=0,
        x=2,
        y=2,
        energy=100.0,
        max_energy=100.0,
        base_energy=10.0,
        growth_rate=0.1,
        survival_threshold=1.0,
        reproduction_interval=5,
        seed_min_dist=1.0,
        seed_max_dist=3.0,
        seed_energy_cost=5.0,
    )

    flora_params = [
        FloraSpeciesParams(
            species_id=0,
            name="Defended Flora",
            base_energy=10.0,
            max_energy=100.0,
            growth_rate=0.1,
            survival_threshold=1.0,
            reproduction_interval=5,
            passive_defenses=PassiveDefensesSchema(
                mechanical_damage_per_bite=5.7,  # Damage after adaptation: 5.7 * (1 - 0.5) = 2.85 -> floor = 2
                digestibility_modifier=0.8,
            ),
        )
    ]

    herbivore_params = [
        HerbivoreSpeciesParams(
            species_id=0,
            name="Grazer",
            energy_min=1.0,
            velocity=1,
            consumption_rate=2.0,
            handling_time=0.1,  # Non-zero handling time for Holling Type II
            resistances=HerbivoreResistancesSchema(
                digestive_efficiency=0.5,  # net_digestibility = min(1.0, max(0.0, 0.8 * 0.5)) = 0.4
                morphological_adaptation=0.5,
            ),
        )
    ]

    metabolized, killed = _feed_on_single_plant(
        swarm=swarm,
        target_plant=plant,
        flora_species_params=flora_params,
        herbivore_species_params=herbivore_params,
        env=env,
        tile_populations=tile_populations,
        plant_death_causes=None,
    )

    assert math.isclose(metabolized, 40.0, rel_tol=1e-5)
    assert killed is True
    assert plant.energy == 0.0
    assert swarm.population == 98


def test_rate_limited_phloem_translocation_and_recovery() -> None:
    """Verify exponential relaxation of apparent nutrition factor during active withdrawal and recovery."""
    world = ECSWorld()
    plant_entity = world.create_entity()
    plant = PlantComponent(
        entity_id=plant_entity.entity_id,
        species_id=0,
        x=1,
        y=1,
        energy=10.0,
        max_energy=10.0,
        base_energy=10.0,
        growth_rate=0.1,
        survival_threshold=1.0,
        reproduction_interval=5,
        seed_min_dist=1.0,
        seed_max_dist=3.0,
        seed_energy_cost=5.0,
        apparent_nutrition_factor=1.0,
        target_nutrition_factor=0.2,
        translocation_rate=0.5,
        withdrawal_ticks_remaining=2,
    )
    world.add_component(plant_entity.entity_id, plant)

    # Tick 1: Active withdrawal (remaining = 2 -> 1)
    # apparent_nutrition = 1.0 + (0.2 - 1.0) * 0.5 = 0.6
    _phase_manage_nutrition_recovery(world)
    assert plant.withdrawal_ticks_remaining == 1
    assert math.isclose(plant.apparent_nutrition_factor, 0.6, rel_tol=1e-5)

    # Tick 2: Active withdrawal (remaining = 1 -> 0)
    # apparent_nutrition = 0.6 + (0.2 - 0.6) * 0.5 = 0.4
    _phase_manage_nutrition_recovery(world)
    assert plant.withdrawal_ticks_remaining == 0
    assert math.isclose(plant.apparent_nutrition_factor, 0.4, rel_tol=1e-5)

    # Tick 3: Recovery toward 1.0 (remaining = 0)
    # apparent_nutrition = 0.4 + (1.0 - 0.4) * 0.5 = 0.7
    _phase_manage_nutrition_recovery(world)
    assert plant.withdrawal_ticks_remaining == 0
    assert math.isclose(plant.apparent_nutrition_factor, 0.7, rel_tol=1e-5)
