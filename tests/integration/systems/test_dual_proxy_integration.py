# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""End-to-end integration tests for Decoupled Dual-Proxy Architecture Plan 3.

Validates probabilistic incidental seedling mortality (trampling/consumption),
mature plant structural resistance, M_structural-scaled maintenance cost starvation,
and Zarr replay analytics integration.
"""

from __future__ import annotations

import numpy as np

from phids.api.schemas.species import FloraSpeciesParams, HerbivoreSpeciesParams
from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.engine.systems.interaction.movement import _resolve_incidental_mortality
from phids.engine.systems.lifecycle import run_lifecycle
from phids.telemetry.analytics import calculate_incidental_mortality_rate, calculate_mean_structural_mass_by_species


def test_swarm_movement_incidental_seedling_mortality_probabilistic() -> None:
    """Verify moving swarm has stochastic chance of culling a fragile M=0 seedling on coordinate entry."""
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5)

    # Spawn seedling at (2, 2) with M_structural = 0.0
    plant_entity = world.create_entity()
    plant = PlantComponent(
        entity_id=plant_entity.entity_id,
        species_id=0,
        x=2,
        y=2,
        energy=10.0,
        max_energy=50.0,
        base_energy=10.0,
        growth_rate=0.1,
        survival_threshold=1.0,
        reproduction_interval=10,
        seed_min_dist=1.0,
        seed_max_dist=5.0,
        seed_energy_cost=5.0,
        structural_mass=0.0,
        max_structural_mass=100.0,
    )
    world.add_component(plant_entity.entity_id, plant)
    world.register_position(plant_entity.entity_id, 2, 2)
    env.set_plant_energy(2, 2, 0, 10.0)

    # Spawn macro-swarm with population 50, factor 0.02 -> P = min(0.50, 50 * 0.02 * 1.0) = 0.50
    swarm_entity = world.create_entity()
    swarm = SwarmComponent(
        entity_id=swarm_entity.entity_id,
        species_id=0,
        x=2,
        y=2,
        population=50,
        initial_population=50,
        energy=100.0,
        energy_min=1.0,
        velocity=1,
        consumption_rate=2.0,
    )
    world.add_component(swarm_entity.entity_id, swarm)

    herb_params = {
        0: HerbivoreSpeciesParams(
            species_id=0,
            name="Heavy Trampler",
            energy_min=1.0,
            velocity=1,
            consumption_rate=2.0,
            incidental_mortality_factor=0.02,
            incidental_mortality_mode="trampling",
        )
    }

    # Run resolution 100 times across fresh seeds to verify non-deterministic probabilistic mortality
    cull_count = 0
    for _ in range(100):
        # Re-register plant
        if not world.has_entity(plant_entity.entity_id):
            plant_entity = world.create_entity()
            plant.entity_id = plant_entity.entity_id
            world.add_component(plant_entity.entity_id, plant)
            world.register_position(plant_entity.entity_id, 2, 2)
            env.set_plant_energy(2, 2, 0, 10.0)

        _resolve_incidental_mortality(swarm, 2, 2, world, env, herb_params)
        if not world.has_entity(plant_entity.entity_id):
            cull_count += 1

    # Probabilistic chance P=0.50 across 100 trials should result in ~20 to 80 culls
    assert 20 <= cull_count <= 80


def test_mature_tree_resists_incidental_mortality() -> None:
    """Verify mature plant (M_structural == max_structural_mass) has zero vulnerability and survives passage."""
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5)

    plant_entity = world.create_entity()
    plant = PlantComponent(
        entity_id=plant_entity.entity_id,
        species_id=0,
        x=2,
        y=2,
        energy=50.0,
        max_energy=50.0,
        base_energy=10.0,
        growth_rate=0.1,
        survival_threshold=1.0,
        reproduction_interval=10,
        seed_min_dist=1.0,
        seed_max_dist=5.0,
        seed_energy_cost=5.0,
        structural_mass=100.0,
        max_structural_mass=100.0,  # Full adult mass -> vulnerability = 0.0
    )
    world.add_component(plant_entity.entity_id, plant)
    world.register_position(plant_entity.entity_id, 2, 2)

    swarm = SwarmComponent(
        entity_id=world.create_entity().entity_id,
        species_id=0,
        x=2,
        y=2,
        population=100,
        initial_population=100,
        energy=100.0,
        energy_min=1.0,
        velocity=1,
        consumption_rate=2.0,
    )

    herb_params = {
        0: HerbivoreSpeciesParams(
            species_id=0,
            name="Heavy Trampler",
            energy_min=1.0,
            velocity=1,
            consumption_rate=2.0,
            incidental_mortality_factor=0.05,
        )
    }

    # Run resolution 50 times - mature plant MUST survive every time
    for _ in range(50):
        _resolve_incidental_mortality(swarm, 2, 2, world, env, herb_params)
        assert world.has_entity(plant_entity.entity_id)


def test_overgrazed_mature_plant_starves_due_to_structural_upkeep() -> None:
    """Verify over-grazed mature plant starves when remaining E_current < E_upkeep fee."""
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5)

    # Plant with survival_threshold=2.0, structural_mass=max_structural_mass=100.0
    # upkeep_fee = survival_threshold * STRUCTURAL_UPKEEP_SCALAR * (100/100) = 2.0 * 0.5 * 1.0 = 1.0 energy/tick
    plant_entity = world.create_entity()
    plant = PlantComponent(
        entity_id=plant_entity.entity_id,
        species_id=0,
        x=2,
        y=2,
        energy=1.5,  # Over-grazed energy reserve (just above 1.0 upkeep fee)
        max_energy=50.0,
        base_energy=10.0,
        growth_rate=0.0,
        survival_threshold=2.0,
        reproduction_interval=10,
        seed_min_dist=1.0,
        seed_max_dist=5.0,
        seed_energy_cost=5.0,
        structural_mass=100.0,
        max_structural_mass=100.0,
    )
    world.add_component(plant_entity.entity_id, plant)
    world.register_position(plant_entity.entity_id, 2, 2)
    env.set_plant_energy(2, 2, 0, 1.5)

    flora_params: dict[int, FloraSpeciesParams] = {
        0: FloraSpeciesParams(
            species_id=0,
            name="Oak",
            base_energy=10.0,
            max_energy=50.0,
            growth_rate=0.0,
            survival_threshold=2.0,
            reproduction_interval=100,
        )
    }

    death_causes: dict[str, int] = {}
    # Run 1 lifecycle tick: energy drops 1.5 - 1.0 = 0.5 < survival_threshold (2.0) -> plant dies
    run_lifecycle(
        world,
        env,
        tick=0,
        flora_species_params=flora_params,
        plant_death_causes=death_causes,
        force_all_entities=True,
    )

    assert not world.has_entity(plant_entity.entity_id)
    assert death_causes.get("death_background_deficit", 0) == 1


def test_incidental_mortality_rate_analytics() -> None:
    """Verify calculate_incidental_mortality_rate correctly computes incidental death ratios."""
    causes = {
        "death_background_deficit": 5,
        "death_collateral_trampling": 3,
        "death_incidental_consumption": 2,
    }
    # 5 incidental / 10 total = 0.50
    rate = calculate_incidental_mortality_rate(causes)
    assert rate == 0.50

    # Mean structural mass calculation
    struct_layers = np.zeros((2, 5, 5), dtype=np.float32)
    struct_layers[0, 1, 1] = 20.0
    struct_layers[0, 2, 2] = 40.0
    means = calculate_mean_structural_mass_by_species(struct_layers)
    assert means[0] == 30.0
    assert means[1] == 0.0
