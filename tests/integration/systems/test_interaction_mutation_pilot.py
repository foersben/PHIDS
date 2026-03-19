"""Focused mutation-pilot regressions for interaction-system branch semantics."""

from __future__ import annotations

import random
from collections.abc import Callable

import pytest

from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.engine.systems.interaction import TILE_CARRYING_CAPACITY, run_interaction


def test_crowding_threshold_strict_gt_capacity(
    monkeypatch: pytest.MonkeyPatch,
    add_swarm: Callable[..., int],
) -> None:
    """Crowding random-walk triggers only when local population is strictly above carrying capacity."""
    env = GridEnvironment(width=3, height=1, num_signals=1, num_toxins=1)
    env.flow_field[:, 0] = [0.0, 1.0, 3.0]

    # Equality case: should not enter random-walk crowding branch.
    equal_world = ECSWorld()
    equal_swarm_id = add_swarm(
        equal_world,
        1,
        0,
        species_id=0,
        pop=TILE_CARRYING_CAPACITY,
        velocity=1,
        energy=0.0,
    )
    equal_swarm = equal_world.get_entity(equal_swarm_id).get_component(SwarmComponent)
    equal_swarm.energy_upkeep_per_individual = 0.0
    equal_swarm.split_population_threshold = TILE_CARRYING_CAPACITY * 10
    monkeypatch.setattr(
        random, "choice", lambda seq: (_ for _ in ()).throw(AssertionError("unexpected"))
    )
    monkeypatch.setattr(
        random,
        "choices",
        lambda seq, weights, k: [seq[weights.index(max(weights))]],
    )

    run_interaction(equal_world, env, diet_matrix=[[False]], tick=0)

    # Above-capacity case: must use random-walk path.
    above_world = ECSWorld()
    above_swarm_id = add_swarm(
        above_world,
        1,
        0,
        species_id=0,
        pop=TILE_CARRYING_CAPACITY + 1,
        velocity=1,
        energy=0.0,
    )
    above_swarm = above_world.get_entity(above_swarm_id).get_component(SwarmComponent)
    above_swarm.energy_upkeep_per_individual = 0.0
    above_swarm.split_population_threshold = TILE_CARRYING_CAPACITY * 10

    calls = {"random_choice": 0}

    def _choice(seq: list[tuple[int, int]]) -> tuple[int, int]:
        calls["random_choice"] += 1
        return seq[0]

    monkeypatch.setattr(random, "choice", _choice)
    monkeypatch.setattr(
        random,
        "choices",
        lambda seq, weights, k: (_ for _ in ()).throw(
            AssertionError("flow chooser should not run")
        ),
    )

    run_interaction(above_world, env, diet_matrix=[[False]], tick=0)

    assert calls["random_choice"] >= 1


def test_crowding_precedes_anchor_when_edible_plant_present(
    monkeypatch: pytest.MonkeyPatch,
    add_plant: Callable[..., int],
    add_swarm: Callable[..., int],
) -> None:
    """Crowding takes precedence over anchor feeding when both conditions are simultaneously true."""
    world = ECSWorld()
    env = GridEnvironment(width=4, height=1, num_signals=1, num_toxins=1)
    env.flow_field[:, 0] = [0.0, 1.0, 2.0, 3.0]

    plant_id = add_plant(world, 1, 0, species_id=0, energy=20.0)
    swarm_id = add_swarm(world, 1, 0, species_id=0, pop=TILE_CARRYING_CAPACITY + 1)
    swarm = world.get_entity(swarm_id).get_component(SwarmComponent)
    swarm.energy_upkeep_per_individual = 0.0
    swarm.split_population_threshold = TILE_CARRYING_CAPACITY * 10

    monkeypatch.setattr(random, "choice", lambda seq: seq[-1])
    monkeypatch.setattr(
        random,
        "choices",
        lambda seq, weights, k: (_ for _ in ()).throw(
            AssertionError("flow chooser should not run")
        ),
    )

    run_interaction(world, env, diet_matrix=[[True]], tick=0)

    plant = world.get_entity(plant_id).get_component(PlantComponent)
    assert (swarm.x, swarm.y) == (2, 0)
    assert plant.energy == pytest.approx(20.0)


def test_plant_death_requires_strict_less_than_survival_threshold(
    add_plant: Callable[..., int],
    add_swarm: Callable[..., int],
) -> None:
    """A plant survives when post-feeding energy equals its survival threshold exactly."""
    world = ECSWorld()
    env = GridEnvironment(width=3, height=3, num_signals=1, num_toxins=1)

    plant_id = add_plant(world, 1, 1, species_id=0, energy=2.0, survival_threshold=1.0)
    swarm_id = add_swarm(world, 1, 1, species_id=0, pop=1, velocity=1, consumption_rate=1.0)
    swarm = world.get_entity(swarm_id).get_component(SwarmComponent)
    swarm.move_cooldown = 1
    swarm.energy_upkeep_per_individual = 0.0
    swarm.split_population_threshold = 1000

    run_interaction(world, env, diet_matrix=[[True]], tick=0)

    assert world.has_entity(plant_id)
    plant = world.get_entity(plant_id).get_component(PlantComponent)
    assert plant.energy == pytest.approx(1.0)


def test_mixed_diet_contact_prefers_successful_feeding_over_incompatible_flag(
    add_plant: Callable[..., int],
    add_swarm: Callable[..., int],
) -> None:
    """If any compatible feeding occurs, the swarm clears repelled state despite incompatible contacts."""
    world = ECSWorld()
    env = GridEnvironment(width=3, height=3, num_signals=1, num_toxins=1)

    add_plant(world, 1, 1, species_id=0, energy=5.0)
    add_plant(world, 1, 1, species_id=1, energy=5.0)
    swarm_id = add_swarm(world, 1, 1, species_id=0, pop=2, velocity=1, consumption_rate=1.0)
    swarm = world.get_entity(swarm_id).get_component(SwarmComponent)
    swarm.move_cooldown = 1
    swarm.repelled = True
    swarm.repelled_ticks_remaining = 5
    swarm.energy_upkeep_per_individual = 0.0
    swarm.split_population_threshold = 1000

    run_interaction(world, env, diet_matrix=[[True, False]], tick=0)

    assert swarm.repelled is False
    assert swarm.repelled_ticks_remaining == 0


def test_velocity_floor_prevents_zero_division_and_preserves_consumption_scaling(
    add_plant: Callable[..., int],
    add_swarm: Callable[..., int],
) -> None:
    """Velocity zero is clamped to one for feeding-rate scaling so consumption remains finite."""
    world = ECSWorld()
    env = GridEnvironment(width=3, height=3, num_signals=1, num_toxins=1)

    plant_id = add_plant(world, 1, 1, species_id=0, energy=20.0)
    swarm_id = add_swarm(world, 1, 1, species_id=0, pop=4, velocity=0, consumption_rate=2.0)
    swarm = world.get_entity(swarm_id).get_component(SwarmComponent)
    swarm.move_cooldown = 1
    swarm.energy_upkeep_per_individual = 0.0
    swarm.energy_min = 10.0
    swarm.energy = 0.0
    swarm.split_population_threshold = 1000

    run_interaction(world, env, diet_matrix=[[True]], tick=0)

    plant = world.get_entity(plant_id).get_component(PlantComponent)
    assert plant.energy == pytest.approx(12.0)
    assert swarm.energy == pytest.approx(8.0)
