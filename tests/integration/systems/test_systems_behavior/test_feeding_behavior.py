# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Integration tests for PHIDS herbivore feeding, movement, and population interaction systems."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import pytest

from phids.api.schemas.species import (
    FloraSpeciesParams,
    HerbivoreResistancesSchema,
    HerbivoreSpeciesParams,
)
from phids.api.schemas.triggers import PassiveDefensesSchema
from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.engine.systems.interaction import run_interaction as _run_interaction_impl

if TYPE_CHECKING:
    from collections.abc import Callable


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
        seed_max_dist=1.0,
        seed_energy_cost=2.0,
        triggers=[],
        passive_defenses=PassiveDefensesSchema(digestibility_modifier=1.0, mechanical_damage_per_bite=0.0),
    )


def run_interaction(world: ECSWorld, env: GridEnvironment, diet_matrix: list[list[bool]], tick: int = 0) -> None:
    """Wrapper function to execute interaction with species parameter arrays."""

    def _herbivore_params(species_id: int = 0) -> HerbivoreSpeciesParams:
        return HerbivoreSpeciesParams(
            species_id=species_id,
            name=f"herbivore-{species_id}",
            energy_min=1.0,
            velocity=1,
            consumption_rate=2.0,
            reproduction_energy_divisor=2.0,
            resistances=HerbivoreResistancesSchema(),
        )

    flora_dict = {0: _flora_params(0), 1: _flora_params(1), 2: _flora_params(2)}
    herb_dict = {0: _herbivore_params(0), 1: _herbivore_params(1), 2: _herbivore_params(2)}
    _run_interaction_impl(world, env, diet_matrix, list(flora_dict.values()), list(herb_dict.values()), tick)


def test_interaction_diet_matrix_blocks_incompatible_feeding(
    add_plant: Callable[..., int], add_swarm: Callable[..., int]
) -> None:
    """Verify incompatible diet entries prevent grazing and force attrition dynamics."""
    world = ECSWorld()
    env = GridEnvironment(width=4, height=4, num_signals=1, num_toxins=1)
    plant_id = add_plant(world, 1, 1, species_id=0, energy=10.0)
    swarm_id = add_swarm(world, 1, 1, species_id=0, pop=5, energy=1.0)
    plant = world.get_entity(plant_id).get_component(PlantComponent)
    swarm = world.get_entity(swarm_id).get_component(SwarmComponent)
    initial_energy = plant.energy
    run_interaction(world, env, diet_matrix=[[False]], tick=0)
    assert plant.energy == pytest.approx(initial_energy)
    assert swarm.energy <= 1.0


def test_interaction_reproduction_can_trigger_same_tick_mitosis(add_swarm: Callable[..., int]) -> None:
    """Verify reproduction can trigger immediate mitosis when thresholds are exceeded."""
    world = ECSWorld()
    env = GridEnvironment(width=4, height=4, num_signals=1, num_toxins=1)
    sid = add_swarm(world, 1, 1, species_id=0, pop=9)
    swarm = world.get_entity(sid).get_component(SwarmComponent)
    swarm.initial_population = 5
    swarm.split_population_threshold = 10
    swarm.energy_upkeep_per_individual = 0.0
    swarm.energy = 10.0
    run_interaction(world, env, diet_matrix=[[False]], tick=0)
    swarms = [e.get_component(SwarmComponent) for e in world.query(SwarmComponent)]
    assert len(swarms) == 2
    assert sum(s.population for s in swarms) == 10


def test_interaction_flow_field_movement_chooses_strongest_gradient(
    add_swarm: Callable[..., int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify movement chooses the direction with the strongest local flow gradient."""
    world = ECSWorld()
    env = GridEnvironment(width=3, height=1, num_signals=1, num_toxins=1)
    env.flow_field[0, 0] = 9.0
    env.flow_field[1, 0] = 1.0
    env.flow_field[2, 0] = 10.0
    sid = add_swarm(world, 1, 0, species_id=0, pop=4)
    swarm = world.get_entity(sid).get_component(SwarmComponent)
    monkeypatch.setattr(random, "choices", lambda seq, weights, **_: [seq[weights.index(max(weights))]])
    run_interaction(world, env, diet_matrix=[[False]], tick=0)
    assert (swarm.x, swarm.y) == (2, 0)
    assert (swarm.last_dx, swarm.last_dy) == (1, 0)


def test_interaction_moved_swarm_does_not_feed_in_same_tick(
    add_plant: Callable[..., int], add_swarm: Callable[..., int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify swarms that moved this tick do not also feed in the same phase."""
    world = ECSWorld()
    env = GridEnvironment(width=3, height=1, num_signals=1, num_toxins=1)
    env.flow_field[0, 0] = 0.0
    env.flow_field[1, 0] = 1.0
    env.flow_field[2, 0] = 5.0
    plant_id = add_plant(world, 2, 0, species_id=0, energy=10.0)
    swarm_id = add_swarm(world, 1, 0, species_id=0, pop=5)
    swarm = world.get_entity(swarm_id).get_component(SwarmComponent)
    swarm.energy_upkeep_per_individual = 0.0
    monkeypatch.setattr(random, "choices", lambda seq, weights, **_: [seq[weights.index(max(weights))]])
    run_interaction(world, env, diet_matrix=[[True]], tick=0)
    plant = world.get_entity(plant_id).get_component(PlantComponent)
    assert (swarm.x, swarm.y) == (2, 0)
    assert plant.energy == pytest.approx(10.0)
    assert swarm.energy == pytest.approx(0.0)


def test_interaction_velocity_scaled_grazing_prevents_cooldown_hyper_feeding(
    add_plant: Callable[..., int], add_swarm: Callable[..., int]
) -> None:
    """Verify cooldown swarms use velocity-scaled grazing to avoid hyper-feeding exploits."""
    world = ECSWorld()
    env = GridEnvironment(width=4, height=1, num_signals=1, num_toxins=1)
    plant_id = add_plant(world, 1, 0, species_id=0, energy=100.0)
    slow_swarm_id = add_swarm(world, 1, 0, species_id=0, pop=10)
    fast_swarm_id = add_swarm(world, 2, 0, species_id=0, pop=10)
    slow_swarm = world.get_entity(slow_swarm_id).get_component(SwarmComponent)
    fast_swarm = world.get_entity(fast_swarm_id).get_component(SwarmComponent)
    slow_swarm.velocity = 5
    slow_swarm.move_cooldown = 4
    fast_swarm.velocity = 1
    fast_swarm.move_cooldown = 0
    slow_swarm.energy_upkeep_per_individual = 0.0
    fast_swarm.energy_upkeep_per_individual = 0.0
    slow_swarm.split_population_threshold = 1000
    fast_swarm.split_population_threshold = 1000
    run_interaction(world, env, diet_matrix=[[True]], tick=0)
    plant = world.get_entity(plant_id).get_component(PlantComponent)
    assert slow_swarm.energy == pytest.approx(2.0)
    assert fast_swarm.energy == pytest.approx(0.0)
    assert plant.energy == pytest.approx(98.0)


def test_interaction_feeding_ignores_stale_plant_entity_ids(
    add_plant: Callable[..., int], add_swarm: Callable[..., int]
) -> None:
    """Feeding skips stale spatial-hash entity identifiers after plant garbage collection."""
    world = ECSWorld()
    env = GridEnvironment(width=3, height=3, num_signals=1, num_toxins=1)
    add_plant(world, 1, 1, species_id=0, energy=1.0)
    first_swarm_id = add_swarm(world, 1, 1, species_id=0, pop=2)
    second_swarm_id = add_swarm(world, 1, 1, species_id=0, pop=2)
    first_swarm = world.get_entity(first_swarm_id).get_component(SwarmComponent)
    second_swarm = world.get_entity(second_swarm_id).get_component(SwarmComponent)
    first_swarm.energy_upkeep_per_individual = 0.0
    second_swarm.energy_upkeep_per_individual = 0.0
    first_swarm.move_cooldown = 1
    second_swarm.move_cooldown = 1
    run_interaction(world, env, diet_matrix=[[True]], tick=0)
    remaining_plants = [entity for entity in world.query(PlantComponent)]
    assert remaining_plants == []
    assert world.has_entity(first_swarm_id)
    assert world.has_entity(second_swarm_id)


def test_repelled_swarm_performs_random_walk(add_swarm: Callable[..., int], monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify repelled swarms follow random-walk displacement and decrement repel duration."""
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=1, num_toxins=1)
    sid = add_swarm(world, 2, 2, species_id=0, pop=6)
    swarm = world.get_entity(sid).get_component(SwarmComponent)
    swarm.repelled = True
    swarm.repelled_ticks_remaining = 2
    monkeypatch.setattr(random, "choice", lambda seq: seq[1])
    run_interaction(world, env, diet_matrix=[[False]], tick=0)
    assert (swarm.x, swarm.y) != (2, 2)
    assert swarm.repelled_ticks_remaining == 1
