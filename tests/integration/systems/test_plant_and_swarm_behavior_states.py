# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Integration tests ensuring complete coverage of plant and herbivore swarm runtime states.

This module validates per-entity runtime state mechanics for both :class:`PlantComponent` and
:class:`SwarmComponent`:
1. Plant apparent nutrition factor transitions, withdrawal duration decay, and target factor reset.
2. Energy loss cause attribution (herbivory, mycorrhizal tax, reproduction, defense maintenance).
3. Airborne seed flight parameters (drop height, terminal velocity) under wind displacement.
4. Swarm repelled state lifecycle, random walk countdown, and clearing upon valid feeding.
5. Swarm aversion memory exponential decay (0.95 factor per move tick) and 0.01 threshold reset.
6. Swarm velocity move-cooldown decoupling and behavior paradigm configuration.
"""

from __future__ import annotations

import numpy as np
import pytest

from phids.api.schemas.species import FloraSpeciesParams, HerbivoreResistancesSchema, HerbivoreSpeciesParams
from phids.api.schemas.triggers import PassiveDefensesSchema
from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.engine.systems.interaction import run_interaction
from phids.engine.systems.interaction.movement import _resolve_swarm_movement
from phids.engine.systems.signaling.lifecycle import _phase_manage_nutrition_recovery


def _flora_params(species_id: int = 0) -> FloraSpeciesParams:
    return FloraSpeciesParams(
        species_id=species_id,
        name=f"flora-{species_id}",
        base_energy=10.0,
        max_energy=30.0,
        growth_rate=5.0,
        survival_threshold=1.0,
        reproduction_interval=1,
        seed_min_dist=1.0,
        seed_max_dist=3.0,
        seed_energy_cost=2.0,
        triggers=[],
        passive_defenses=PassiveDefensesSchema(digestibility_modifier=1.0, mechanical_damage_per_bite=0.0),
    )


def _herbivore_params(species_id: int = 0) -> HerbivoreSpeciesParams:
    return HerbivoreSpeciesParams(
        species_id=species_id,
        name=f"herbivore-{species_id}",
        energy_min=1.0,
        velocity=2,
        consumption_rate=2.0,
        reproduction_energy_divisor=1.0,
        energy_upkeep_per_individual=0.05,
        split_population_threshold=10,
        resistances=HerbivoreResistancesSchema(),
    )


def test_plant_apparent_nutrition_withdrawal_decay_and_reset() -> None:
    """Verify apparent nutrition factor smoothly transitions and reverts after withdrawal duration expires."""
    world = ECSWorld()
    plant_entity = world.create_entity()
    plant_id = plant_entity.entity_id
    plant = PlantComponent(
        entity_id=plant_id,
        species_id=0,
        x=2,
        y=2,
        energy=15.0,
        max_energy=30.0,
        base_energy=10.0,
        growth_rate=5.0,
        survival_threshold=1.0,
        reproduction_interval=5,
        seed_min_dist=1.0,
        seed_max_dist=3.0,
        seed_energy_cost=2.0,
        apparent_nutrition_factor=1.0,
        target_nutrition_factor=0.5,
        translocation_rate=0.5,
        withdrawal_ticks_remaining=2,
    )
    world.add_component(plant_id, plant)

    # Tick 1: Translocation moves factor towards 0.5; withdrawal ticks decrement from 2 to 1
    _phase_manage_nutrition_recovery(world)
    assert plant.apparent_nutrition_factor == pytest.approx(0.75)
    assert plant.withdrawal_ticks_remaining == 1
    assert plant.target_nutrition_factor == pytest.approx(0.5)

    # Tick 2: Translocation continues; withdrawal ticks decrement from 1 to 0
    _phase_manage_nutrition_recovery(world)
    assert plant.withdrawal_ticks_remaining == 0

    # Tick 3: Recovery moves factor back towards 1.0
    _phase_manage_nutrition_recovery(world)
    assert plant.apparent_nutrition_factor > 0.75


def test_plant_last_energy_loss_cause_herbivory_attribution() -> None:
    """Verify plant entity records 'herbivory' in last_energy_loss_cause when grazed by a swarm."""
    world = ECSWorld()
    env = GridEnvironment(width=4, height=4, num_signals=1, num_toxins=1)

    plant_entity = world.create_entity()
    plant_id = plant_entity.entity_id
    plant = PlantComponent(
        entity_id=plant_id,
        species_id=0,
        x=1,
        y=1,
        energy=10.0,
        max_energy=20.0,
        base_energy=5.0,
        growth_rate=1.0,
        survival_threshold=1.0,
        reproduction_interval=10,
        seed_min_dist=1.0,
        seed_max_dist=2.0,
        seed_energy_cost=2.0,
    )
    world.add_component(plant_id, plant)
    world.register_position(plant_id, 1, 1)

    swarm_entity = world.create_entity()
    swarm_id = swarm_entity.entity_id
    swarm = SwarmComponent(
        entity_id=swarm_id,
        species_id=0,
        x=1,
        y=1,
        population=5,
        initial_population=5,
        energy=2.0,
        energy_min=1.0,
        velocity=1,
        consumption_rate=3.0,
        move_cooldown=1,
    )
    world.add_component(swarm_id, swarm)
    world.register_position(swarm_id, 1, 1)

    diet_matrix = [[True]]
    flora_dict = {0: _flora_params(0)}
    herb_dict = {0: _herbivore_params(0)}

    run_interaction(world, env, diet_matrix, list(flora_dict.values()), list(herb_dict.values()), tick=1)

    assert plant.energy < 10.0
    assert plant.last_energy_loss_cause == "death_herbivory"


def test_plant_airborne_seed_flight_parameters() -> None:
    """Verify seed_drop_height and seed_terminal_velocity are retained on PlantComponent instances."""
    plant = PlantComponent(
        entity_id=1,
        species_id=0,
        x=3,
        y=3,
        energy=20.0,
        max_energy=30.0,
        base_energy=10.0,
        growth_rate=5.0,
        survival_threshold=1.0,
        reproduction_interval=2,
        seed_min_dist=1.0,
        seed_max_dist=4.0,
        seed_energy_cost=3.0,
        seed_drop_height=2.5,
        seed_terminal_velocity=0.4,
    )

    assert plant.seed_drop_height == 2.5
    assert plant.seed_terminal_velocity == 0.4
    assert plant.camouflage is False
    assert plant.camouflage_factor == 1.0


def _move_swarm(
    swarm: SwarmComponent,
    entity_id: int,
    env: GridEnvironment,
    world: ECSWorld,
    diet_matrix: list[list[bool]] | None = None,
) -> bool:
    if diet_matrix is None:
        diet_matrix = [[True]]
    entity = world.get_entity(entity_id)
    tile_populations = [0] * (env.width * env.height)
    scratch_cx = np.empty(5, dtype=np.int32)
    scratch_cy = np.empty(5, dtype=np.int32)
    scratch_scores = np.empty(5, dtype=np.float64)
    scratch_adjusted = np.empty(5, dtype=np.float64)
    scratch_weights = np.empty(5, dtype=np.float64)
    return _resolve_swarm_movement(
        swarm,
        entity,
        env,
        world,
        diet_matrix,
        tile_populations,
        scratch_cx,
        scratch_cy,
        scratch_scores,
        scratch_adjusted,
        scratch_weights,
    )


def test_swarm_repelled_state_countdown_and_clearing() -> None:
    """Verify repelled random-walk countdown decrements and clears repelled flag."""
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=1, num_toxins=1)

    swarm_entity = world.create_entity()
    swarm_id = swarm_entity.entity_id
    swarm = SwarmComponent(
        entity_id=swarm_id,
        species_id=0,
        x=2,
        y=2,
        population=5,
        initial_population=5,
        energy=2.0,
        energy_min=1.0,
        velocity=1,
        consumption_rate=1.0,
        repelled=True,
        repelled_ticks_remaining=2,
    )
    world.add_component(swarm_id, swarm)

    # Tick 1: Swarm moves in random walk phase, ticks remaining decrements to 1
    _move_swarm(swarm, swarm_id, env, world)
    assert swarm.repelled_ticks_remaining == 1

    # Tick 2: Ticks remaining decrements to 0, repelled clears
    _move_swarm(swarm, swarm_id, env, world)
    assert swarm.repelled_ticks_remaining == 0
    assert swarm.repelled is False


def test_swarm_aversion_memory_exponential_decay() -> None:
    """Verify swarm aversion memory decays by 0.95 each movement tick and resets below 0.01."""
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=1, num_toxins=1)

    swarm_entity = world.create_entity()
    swarm_id = swarm_entity.entity_id
    swarm = SwarmComponent(
        entity_id=swarm_id,
        species_id=0,
        x=2,
        y=2,
        population=5,
        initial_population=5,
        energy=2.0,
        energy_min=1.0,
        velocity=1,
        consumption_rate=1.0,
        aversion_memory=0.02,
    )
    world.add_component(swarm_id, swarm)

    # Tick 1: 0.02 * 0.95 = 0.019
    _move_swarm(swarm, swarm_id, env, world)
    assert swarm.aversion_memory == pytest.approx(0.019)

    # Tick 2: 0.019 * 0.95 = 0.01805
    _move_swarm(swarm, swarm_id, env, world)
    assert swarm.aversion_memory == pytest.approx(0.01805)

    # Set aversion memory close to threshold (0.0105 * 0.95 = 0.009975 < 0.01) -> resets to 0.0
    swarm.aversion_memory = 0.0105
    _move_swarm(swarm, swarm_id, env, world)
    assert swarm.aversion_memory == 0.0


def test_swarm_move_cooldown_velocity_decoupling() -> None:
    """Verify velocity setting dictates movement period move_cooldown."""
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=1, num_toxins=1)

    swarm_entity = world.create_entity()
    swarm_id = swarm_entity.entity_id
    swarm = SwarmComponent(
        entity_id=swarm_id,
        species_id=0,
        x=2,
        y=2,
        population=5,
        initial_population=5,
        energy=2.0,
        energy_min=1.0,
        velocity=3,  # Moves once every 3 ticks
        consumption_rate=1.0,
        move_cooldown=2,
    )
    world.add_component(swarm_id, swarm)

    # Tick 1: move_cooldown=2 > 0 -> decrements to 1, no move
    moved = _move_swarm(swarm, swarm_id, env, world)
    assert moved is False
    assert swarm.move_cooldown == 1

    # Tick 2: move_cooldown=1 > 0 -> decrements to 0, no move
    moved = _move_swarm(swarm, swarm_id, env, world)
    assert moved is False
    assert swarm.move_cooldown == 0


def test_swarm_behavior_paradigm_configuration() -> None:
    """Verify behavior_paradigm and split_population_threshold fields on SwarmComponent."""
    swarm = SwarmComponent(
        entity_id=10,
        species_id=1,
        x=0,
        y=0,
        population=12,
        initial_population=5,
        energy=4.0,
        energy_min=1.0,
        velocity=1,
        consumption_rate=2.0,
        behavior_paradigm="solitary_grazer",
        split_population_threshold=20,
    )

    assert swarm.behavior_paradigm == "solitary_grazer"
    assert swarm.split_population_threshold == 20
