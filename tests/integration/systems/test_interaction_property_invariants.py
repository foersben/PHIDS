"""Property-style invariant checks for deterministic interaction-phase arithmetic."""

from __future__ import annotations

import math
from collections.abc import Callable

import pytest

from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.engine.systems.interaction import run_interaction


@pytest.mark.parametrize("population", [1, 2, 3, 5, 8, 13, 16])
@pytest.mark.parametrize("upkeep", [0.0, 0.25, 0.5, 1.0, 1.5, 2.0])
@pytest.mark.parametrize("energy_fraction", [0.0, 0.25, 0.5, 0.75, 1.0])
def test_attrition_matches_closed_form_over_bounded_parameter_sweep(
    add_swarm: Callable[..., int],
    population: int,
    upkeep: float,
    energy_fraction: float,
) -> None:
    """Metabolic attrition follows the closed-form casualty/remainder equations over bounded inputs."""
    world = ECSWorld()
    env = GridEnvironment(width=3, height=3, num_signals=1, num_toxins=1)

    energy_min = 2.0
    baseline_energy = population * energy_min
    initial_energy = baseline_energy * energy_fraction

    swarm_id = add_swarm(
        world,
        1,
        1,
        species_id=0,
        pop=population,
        energy=initial_energy,
        energy_min=energy_min,
        velocity=1,
        consumption_rate=1.0,
    )
    swarm = world.get_entity(swarm_id).get_component(SwarmComponent)
    # Freeze movement/feeding/reproduction/mitosis side effects so attrition dominates.
    swarm.move_cooldown = 1
    swarm.energy_upkeep_per_individual = upkeep
    swarm.split_population_threshold = 1000

    metabolic_cost = population * energy_min * upkeep
    post_cost_energy = initial_energy - metabolic_cost
    if post_cost_energy >= 0.0:
        expected_population = population
        expected_energy = post_cost_energy
    else:
        deficit = -post_cost_energy
        casualties = math.ceil(deficit / energy_min)
        expected_population = max(0, population - casualties)
        expected_energy = max(0.0, casualties * energy_min - deficit)

    run_interaction(world, env, diet_matrix=[[False]], tick=0)

    if expected_population == 0:
        assert not world.has_entity(swarm_id)
        return

    assert world.has_entity(swarm_id)
    updated = world.get_entity(swarm_id).get_component(SwarmComponent)
    assert updated.population == expected_population
    assert updated.energy == pytest.approx(expected_energy)
    assert updated.energy >= 0.0


@pytest.mark.parametrize("population", [2, 4, 8, 16])
@pytest.mark.parametrize("upkeep", [0.25, 0.5, 1.0, 1.5])
def test_attrition_is_monotone_in_initial_energy(
    add_swarm: Callable[..., int],
    population: int,
    upkeep: float,
) -> None:
    """Higher initial energy cannot yield lower surviving population or lower residual energy."""

    def _step(initial_energy: float) -> tuple[int, float, bool]:
        world = ECSWorld()
        env = GridEnvironment(width=3, height=3, num_signals=1, num_toxins=1)
        swarm_id = add_swarm(
            world,
            1,
            1,
            species_id=0,
            pop=population,
            energy=initial_energy,
            energy_min=2.0,
            velocity=1,
            consumption_rate=1.0,
        )
        swarm = world.get_entity(swarm_id).get_component(SwarmComponent)
        swarm.move_cooldown = 1
        swarm.energy_upkeep_per_individual = upkeep
        swarm.split_population_threshold = 1000

        run_interaction(world, env, diet_matrix=[[False]], tick=0)

        if not world.has_entity(swarm_id):
            return (0, 0.0, False)
        updated = world.get_entity(swarm_id).get_component(SwarmComponent)
        return (updated.population, float(updated.energy), True)

    low_population, low_energy, _ = _step(initial_energy=0.0)
    high_population, high_energy, _ = _step(initial_energy=32.0)

    assert high_population >= low_population
    assert high_energy >= low_energy
