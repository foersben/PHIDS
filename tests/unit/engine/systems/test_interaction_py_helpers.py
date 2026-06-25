"""Unit tests for ECS interaction system heuristics.

This module provides targeted tests for the interaction module's internal
heuristics (anchoring, taste rejection, starvation, crowding) using
isolated ECS components and fully compliant GridEnvironment instances.
"""

from __future__ import annotations

# ruff: noqa: I001

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

from phids.engine.core.ecs import ECSWorld
from phids.engine.core.biotope import GridEnvironment
from phids.engine.systems.interaction import run_interaction
from phids.engine.components.swarm import SwarmComponent
from phids.engine.components.plant import PlantComponent


def test_interaction_anchoring_heuristic(
    add_swarm: Callable[..., int],
    add_plant: Callable[..., int],
) -> None:
    """Validate that swarms anchor (do not move) when positioned on compatible, nutritious flora."""
    world = ECSWorld()
    env = GridEnvironment(width=16, height=16, num_signals=1, num_toxins=1)

    # Place a nutritious plant at (1,1)
    plant_entity = add_plant(
        world=world,
        x=1,
        y=1,
        species_id=0,
        energy=10.0,
    )

    # Place a compatible swarm at (1,1)
    swarm_entity = add_swarm(
        world=world,
        x=1,
        y=1,
        species_id=0,
        population=5,
        energy=5.0,
    )

    swarm = world.get_entity(swarm_entity).get_component(SwarmComponent)
    plant = world.get_entity(plant_entity).get_component(PlantComponent)

    # Prevent mitosis bisection
    swarm.initial_population = swarm.population

    initial_energy = swarm.energy
    initial_plant_energy = plant.energy

    # Tick the interaction system
    run_interaction(world, env, diet_matrix=[[True]], tick=0)

    # Swarm should have fed and remain anchored at (1,1)
    assert swarm.x == 1
    assert swarm.y == 1
    assert swarm.energy > initial_energy
    assert plant.energy < initial_plant_energy


def test_interaction_taste_rejection(
    add_swarm: Callable[..., int],
    add_plant: Callable[..., int],
) -> None:
    """Validate that swarms reject incompatible flora, triggering repulsion state."""
    world = ECSWorld()
    env = GridEnvironment(width=16, height=16, num_signals=1, num_toxins=1)

    # Place an incompatible plant at (1,1) with species 1
    add_plant(
        world=world,
        x=1,
        y=1,
        species_id=1,
        energy=10.0,
    )

    # Place a swarm at (1,1) looking for species 0
    swarm_entity = add_swarm(
        world=world,
        x=1,
        y=1,
        species_id=0,
        population=5,
        energy=10.0,
    )

    swarm = world.get_entity(swarm_entity).get_component(SwarmComponent)

    # Prevent mitosis bisection
    swarm.initial_population = swarm.population
    # Freeze movement on this tick so it stays at (1,1) to check compatibility
    swarm.move_cooldown = 1

    # Tick the interaction system
    run_interaction(world, env, diet_matrix=[[True, False]], tick=0)

    # Swarm should be repelled
    assert swarm.repelled is True
    assert swarm.repelled_ticks_remaining == 2


def test_interaction_starvation_ceil_casualty(
    add_swarm: Callable[..., int],
) -> None:
    """Validate that starvation induces deterministic casualties based on energy deficit."""
    world = ECSWorld()
    env = GridEnvironment(width=16, height=16, num_signals=1, num_toxins=1)

    swarm_entity = add_swarm(
        world=world,
        x=1,
        y=1,
        species_id=0,
        population=5,
        energy=0.0,
    )

    swarm = world.get_entity(swarm_entity).get_component(SwarmComponent)

    # Prevent mitosis bisection
    swarm.initial_population = swarm.population
    # Freeze movement to isolate attrition
    swarm.move_cooldown = 1

    # Override parameters to control the test
    swarm.energy_upkeep_per_individual = 0.5
    swarm.energy_min = 2.0

    run_interaction(world, env, diet_matrix=[[False]], tick=0)

    # Casualties: ceil(5 * 2.0 * 0.5 / 2.0) = 3
    # Population should be 5 - 3 = 2
    assert swarm.population == 2


def test_interaction_crowding_dispersal(
    add_swarm: Callable[..., int],
) -> None:
    """Validate that swarms on a crowded cell will trigger dispersal logic."""
    world = ECSWorld()
    env = GridEnvironment(width=16, height=16, num_signals=1, num_toxins=1)

    # Place many swarms on the same cell (1,1) to exceed cell capacity
    swarm_entities = []
    for _ in range(60):
        ent = add_swarm(
            world=world,
            x=1,
            y=1,
            species_id=0,
            population=10,  # 60 * 10 = 600 individuals
            energy=10.0,
        )
        swarm = world.get_entity(ent).get_component(SwarmComponent)
        # Prevent mitosis bisection
        swarm.initial_population = swarm.population
        swarm_entities.append(ent)

    run_interaction(world, env, diet_matrix=[[False]], tick=0)

    # At least some swarms should have moved due to crowding
    moved_count = 0
    for ent in swarm_entities:
        swarm = world.get_entity(ent).get_component(SwarmComponent)
        if swarm.x != 1 or swarm.y != 1:
            moved_count += 1

    assert moved_count > 0


def test_interaction_random_fallback_and_missing_entity(
    add_swarm: Callable[..., int],
) -> None:
    """Cover the pure-Python fallback (when random choice is mocked) and missing entity checks."""
    from unittest.mock import patch
    from phids.engine.systems.interaction import _choose_neighbour_by_flow_probability

    # 1. Register a non-existent entity to trigger the "not world.has_entity" check
    world = ECSWorld()
    env = GridEnvironment(width=16, height=16, num_signals=1, num_toxins=1)

    world.register_position(99999, 1, 1)

    # Place a swarm at (1,1)
    swarm_entity = add_swarm(
        world=world,
        x=1,
        y=1,
        species_id=0,
        population=5,
        energy=10.0,
    )

    swarm = world.get_entity(swarm_entity).get_component(SwarmComponent)
    # Prevent mitosis bisection
    swarm.initial_population = swarm.population

    # CASE A: flat field, inertia dx=0, dy=0
    swarm.last_dx = 0
    swarm.last_dy = 0
    with (
        patch("random.choice", side_effect=lambda x: x[0]),
        patch("random.choices", side_effect=lambda x, *_, **__: [x[0]]),
    ):
        run_interaction(world, env, diet_matrix=[[False]], tick=0)

    # CASE B: flat field, inertia dx=1, dy=0
    swarm.last_dx = 1
    swarm.last_dy = 0
    with patch("random.choices", side_effect=lambda x, *_, **__: [x[0]]):
        run_interaction(world, env, diet_matrix=[[False]], tick=0)

    # CASE C: non-flat field, not invert
    env.flow_field[1, 1] = 1.0
    env.flow_field[2, 1] = 5.0
    swarm.last_dx = 0
    swarm.last_dy = 0
    with patch("random.choices", side_effect=lambda x, *_, **__: [x[0]]):
        run_interaction(world, env, diet_matrix=[[False]], tick=0)

    # CASE D: non-flat field, invert=True
    with patch("random.choices", side_effect=lambda x, *_, **__: [x[0]]):
        _choose_neighbour_by_flow_probability(swarm, env.flow_field, env.width, env.height, invert=True)

    # 3. Clean up the non-existent entity from the registry to avoid side effects
    world.unregister_position(99999, 1, 1)
