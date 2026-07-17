# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Integration tests for biological mechanics.

Validates digestibility modulation, resource withdrawal, defensive triggers,
and complex plant-herbivore interaction pathways in PHIDS.
"""

import numpy as np

from phids.api.schemas import (
    FloraSpeciesParams,
    HerbivoreSpeciesParams,
    PassiveDefensesSchema,
    ResourceWithdrawalAction,
    TriggerConditionSchema,
)
from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.engine.systems.interaction import run_interaction
from phids.engine.systems.signaling import run_signaling


def test_digestibility_modulation_scales_metabolized_energy() -> None:
    """Verify digestibility modulation correctly scales the metabolized energy."""
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5)

    plant_eid = world.create_entity()
    plant = PlantComponent(
        entity_id=plant_eid.entity_id,
        species_id=0,
        x=2,
        y=2,
        energy=100.0,
        max_energy=200.0,
        base_energy=10.0,
        growth_rate=0.0,
        survival_threshold=0.0,
        reproduction_interval=10,
        seed_min_dist=1,
        seed_max_dist=2,
        seed_energy_cost=5,
    )
    world.add_component(plant_eid.entity_id, plant)
    world.register_position(plant_eid.entity_id, 2, 2)

    swarm_eid = world.create_entity()
    swarm = SwarmComponent(
        entity_id=swarm_eid.entity_id,
        species_id=0,
        x=2,
        y=2,
        population=10,
        initial_population=10,
        energy=50.0,
        energy_min=1.0,
        velocity=1,
        consumption_rate=2.0,
        split_population_threshold=1000,
        reproduction_energy_divisor=1000.0,
    )
    swarm.repelled = False
    world.add_component(swarm_eid.entity_id, swarm)
    world.register_position(swarm_eid.entity_id, 2, 2)

    flora_params = [
        FloraSpeciesParams(
            species_id=0,
            name="F0",
            base_energy=10,
            max_energy=200,
            growth_rate=0,
            survival_threshold=0,
            reproduction_interval=10,
            passive_defenses=PassiveDefensesSchema(digestibility_modifier=0.5, mechanical_damage_per_bite=0.0),
        )
    ]
    herb_params = [
        HerbivoreSpeciesParams(
            species_id=0,
            name="H0",
            energy_min=1,
            velocity=1,
            consumption_rate=2.0,
            energy_upkeep_per_individual=0.0,
            resistances=dict(digestive_efficiency=1.0, morphological_adaptation=0.0),
        )
    ]

    diet = [[True]]

    run_interaction(world, env, diet, flora_params, herb_params, tick=0)

    assert plant.energy == 80.0
    assert swarm.energy == 59.5


def test_resource_withdrawal_dims_apparent_nutrition() -> None:
    """Verify resource withdrawal properly dims the apparent nutrition factor."""
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5)

    plant_eid = world.create_entity()
    plant = PlantComponent(
        entity_id=plant_eid.entity_id,
        species_id=0,
        x=2,
        y=2,
        energy=100.0,
        max_energy=200.0,
        base_energy=10.0,
        growth_rate=0.0,
        survival_threshold=0.0,
        reproduction_interval=10,
        seed_min_dist=1,
        seed_max_dist=2,
        seed_energy_cost=5,
    )
    world.add_component(plant_eid.entity_id, plant)
    world.register_position(plant_eid.entity_id, 2, 2)

    swarm_eid = world.create_entity()
    swarm = SwarmComponent(
        entity_id=swarm_eid.entity_id,
        species_id=0,
        x=2,
        y=2,
        population=10,
        initial_population=10,
        energy=50.0,
        energy_min=1.0,
        velocity=1,
        consumption_rate=2.0,
        split_population_threshold=1000,
    )
    world.add_component(swarm_eid.entity_id, swarm)
    world.register_position(swarm_eid.entity_id, 2, 2)

    trigger_conditions = {
        0: [
            TriggerConditionSchema(
                herbivore_species_id=0,
                min_herbivore_population=5,
                aftereffect_ticks=10,
                action=ResourceWithdrawalAction(apparent_nutrition_factor=0.1),
            )
        ]
    }

    assert plant.apparent_nutrition_factor == 1.0

    run_signaling(world, env, trigger_conditions, mycorrhizal_inter_species=False, signal_velocity=1, tick=0)

    assert np.isclose(plant.apparent_nutrition_factor, 0.1)
    assert plant.withdrawal_ticks_remaining == 9


def test_mechanical_attrition_enforces_integer_casualties() -> None:
    """Verify mechanical attrition strictly deducts an integer floor of casualties."""
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5)

    plant_eid = world.create_entity()
    plant = PlantComponent(
        entity_id=plant_eid.entity_id,
        species_id=0,
        x=2,
        y=2,
        energy=10.0,
        max_energy=200.0,
        base_energy=10.0,
        growth_rate=0.0,
        survival_threshold=0.0,
        reproduction_interval=10,
        seed_min_dist=1,
        seed_max_dist=2,
        seed_energy_cost=5,
    )
    world.add_component(plant_eid.entity_id, plant)
    world.register_position(plant_eid.entity_id, 2, 2)
    env.plant_energy_by_species[0, 2, 2] = 150.0
    env.plant_energy_layer[2, 2] = 150.0

    swarm_eid = world.create_entity()
    swarm = SwarmComponent(
        entity_id=swarm_eid.entity_id,
        species_id=0,
        x=2,
        y=2,
        population=10,
        initial_population=10,
        energy=10.0,
        energy_min=10.0,
        velocity=1,
        consumption_rate=5.0,  # Bites taken per individual
        reproduction_energy_divisor=1.0,
        energy_upkeep_per_individual=0.1,
        split_population_threshold=20,
        move_cooldown=1,
    )
    world.add_component(swarm_eid.entity_id, swarm)
    world.register_position(swarm_eid.entity_id, 2, 2)

    diet_matrix = [[True]]
    flora_params = [
        FloraSpeciesParams(
            species_id=0,
            name="test_flora",
            base_energy=10.0,
            max_energy=200.0,
            growth_rate=0.0,
            survival_threshold=0.0,
            reproduction_interval=10,
            seed_min_dist=1,
            seed_max_dist=2,
            seed_energy_cost=5.0,
            passive_defenses=PassiveDefensesSchema(
                mechanical_damage_per_bite=2.5,
                digestibility_modifier=1.0,
            ),
        )
    ]
    herbivore_params = [
        HerbivoreSpeciesParams(
            species_id=0,
            name="test_herbivore",
            velocity=1,
            energy_upkeep_per_individual=0.1,
            energy_min=10.0,
            reproduction_energy_divisor=1.0,
            split_population_threshold=20,
            move_cooldown=1,
            consumption_rate=5.0,
            resistances=dict(
                morphological_adaptation=0.0,
                digestive_efficiency=1.0,
            ),
        )
    ]

    # Act
    run_interaction(world, env, diet_matrix, flora_params, herbivore_params, tick=0)

    # 10 initial population. Consumed 50 energy. Damage = 2.5 -> casualties = 2.
    # New population should be 8.
    assert swarm.population == 8


def test_flow_field_toxin_additive_stacking() -> None:
    """Verify that the flow field stacks multiple toxin layers additively."""
    import numpy as np

    from phids.engine.core.flow_field import compute_flow_field

    width = 5
    height = 5
    plant_energy = np.zeros((width, height), dtype=np.float64)
    apparent_nutrition_layer = np.ones((width, height), dtype=np.float64)

    # Let's add multiple toxins
    toxin_layers = np.zeros((2, width, height), dtype=np.float64)
    toxin_layers[0, 2, 2] = 5.0
    toxin_layers[1, 2, 2] = 3.0

    # In base formula F = alpha * E - beta * sum(T_k)
    # The Jacobi iteration starts with base[x, y] = (E * AN) - sum(T)
    # So base[2,2] should be 0 - (5.0 + 3.0) = -8.0

    result_field = compute_flow_field(plant_energy, apparent_nutrition_layer, toxin_layers, width, height)

    # result_field[2, 2] should be highly negative, propagating outward.
    # It must reflect the combination of 5.0 and 3.0, not just the max (5.0).
    # Since we start at -8.0 and do multiple iterations of averaging, the exact value depends on the kernel decay,
    # but the base field value should have been exactly -8.0 before propagation.
    # A single toxin of 5.0 would start at -5.0.
    # A single toxin of 8.0 would start at -8.0.

    toxin_layer_single = np.zeros((1, width, height), dtype=np.float64)
    toxin_layer_single[0, 2, 2] = 8.0
    result_single = compute_flow_field(plant_energy, apparent_nutrition_layer, toxin_layer_single, width, height)

    # Additive stacking should yield exactly the same flow field
    # as a single toxin layer with the summed magnitude.
    np.testing.assert_array_almost_equal(result_field, result_single)
