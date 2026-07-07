import numpy as np

from phids.api.schemas import (
    FloraSpeciesParams,
    HerbivoreResistancesSchema,
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
            resistances=HerbivoreResistancesSchema(digestive_efficiency=1.0, morphological_adaptation=0.0),
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
    assert plant.withdrawal_ticks_remaining == 10
