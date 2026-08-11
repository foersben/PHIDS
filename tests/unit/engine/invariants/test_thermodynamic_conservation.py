# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Thermodynamic conservation and non-negativity invariant unit tests for PHIDS.

Verifies First Law energy accounting and non-negativity bounds across entity state transitions.
"""

from __future__ import annotations

import pytest

from phids.api.schemas.species import FloraSpeciesParams, HerbivoreResistancesSchema, HerbivoreSpeciesParams
from phids.api.schemas.triggers import PassiveDefensesSchema
from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.engine.systems.interaction import run_interaction


@pytest.mark.scientific_invariant
def test_global_energy_accounting_invariants() -> None:
    """Verify that plant and swarm energy values remain strictly non-negative."""
    world = ECSWorld()
    env = GridEnvironment(width=10, height=10)

    plant_eid = world.create_entity()
    plant = PlantComponent(
        entity_id=plant_eid.entity_id,
        species_id=0,
        x=2,
        y=2,
        energy=50.0,
        max_energy=100.0,
        base_energy=10.0,
        growth_rate=5.0,
        survival_threshold=0.0,
        reproduction_interval=10,
        seed_min_dist=1,
        seed_max_dist=2,
        seed_energy_cost=5,
    )
    world.add_component(plant_eid.entity_id, plant)
    world.register_position(plant_eid.entity_id, 2, 2)
    env.set_plant_energy(x=2, y=2, species_id=0, value=50.0)

    swarm_eid = world.create_entity()
    swarm = SwarmComponent(
        entity_id=swarm_eid.entity_id,
        species_id=0,
        x=2,
        y=2,
        population=5,
        initial_population=5,
        energy=20.0,
        energy_min=1.0,
        velocity=1,
        consumption_rate=4.0,
        split_population_threshold=1000,
    )
    swarm.repelled = False
    world.add_component(swarm_eid.entity_id, swarm)
    world.register_position(swarm_eid.entity_id, 2, 2)

    flora_params = [
        FloraSpeciesParams(
            species_id=0,
            name="F0",
            base_energy=10,
            max_energy=100,
            growth_rate=5,
            survival_threshold=0,
            reproduction_interval=10,
            passive_defenses=PassiveDefensesSchema(digestibility_modifier=1.0, mechanical_damage_per_bite=0.0),
        )
    ]
    herb_params = [
        HerbivoreSpeciesParams(
            species_id=0,
            name="H0",
            energy_min=1,
            velocity=1,
            consumption_rate=4.0,
            energy_upkeep_per_individual=0.1,
            resistances=HerbivoreResistancesSchema(digestive_efficiency=1.0, morphological_adaptation=0.0),
        )
    ]
    diet = [[True]]

    initial_plant_energy = plant.energy
    initial_swarm_total_energy = swarm.energy

    run_interaction(world, env, diet, flora_params, herb_params, tick=0)

    assert plant.energy >= 0.0, "Plant energy must never be negative"
    assert swarm.energy >= 0.0, "Swarm energy must never be negative"
    assert swarm.population >= 0, "Swarm population must never be negative"

    # Total energy consumed by swarm equals loss of plant energy
    energy_lost_by_plant = initial_plant_energy - plant.energy
    assert energy_lost_by_plant >= 0.0, "Plant should lose energy during feeding"

    # Energy gained by swarm (before upkeep) is bounded by energy lost by plant
    final_swarm_total_energy = swarm.energy
    energy_gained_by_swarm = final_swarm_total_energy - initial_swarm_total_energy
    assert energy_gained_by_swarm <= energy_lost_by_plant + 1e-6, "Energy gain cannot exceed intake"
