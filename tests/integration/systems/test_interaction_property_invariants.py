"""Property-style invariant checks for deterministic interaction-phase arithmetic."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import cast

import numpy as np
import pytest

from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.engine.systems.interaction import run_interaction


_NO_DIET = np.zeros((1, 1), dtype=np.bool_)
_NO_DIET_MATRIX = cast(list[list[bool]], _NO_DIET)


def _run_attrition_step(
    add_swarm: Callable[..., int],
    *,
    population: int,
    initial_energy: float,
    upkeep: float,
    energy_min: float = 2.0,
) -> tuple[ECSWorld, int]:
    """Runs one interaction tick with non-attrition side effects disabled for arithmetic isolation."""
    world = ECSWorld()
    env = GridEnvironment(width=3, height=3, num_signals=1, num_toxins=1)
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
    # Freeze movement/feeding/reproduction/mitosis so only attrition arithmetic mutates state.
    swarm.move_cooldown = 1
    swarm.energy_upkeep_per_individual = upkeep
    swarm.reproduction_energy_divisor = 1_000_000.0
    swarm.split_population_threshold = 1000

    run_interaction(world, env, diet_matrix=_NO_DIET_MATRIX, tick=0)
    return world, swarm_id


def _run_reproduction_step(
    add_swarm: Callable[..., int],
    *,
    population: int,
    initial_energy: float,
    energy_min: float,
    reproduction_divisor: float,
) -> tuple[ECSWorld, int]:
    """Runs one interaction tick with only the reproduction arithmetic branch active."""
    world = ECSWorld()
    env = GridEnvironment(width=3, height=3, num_signals=1, num_toxins=1)
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
        reproduction_energy_divisor=reproduction_divisor,
    )
    swarm = world.get_entity(swarm_id).get_component(SwarmComponent)
    swarm.move_cooldown = 1
    swarm.energy_upkeep_per_individual = 0.0
    swarm.split_population_threshold = 1000

    run_interaction(world, env, diet_matrix=_NO_DIET_MATRIX, tick=0)
    return world, swarm_id


def _run_mitosis_step(
    add_swarm: Callable[..., int],
    monkeypatch: pytest.MonkeyPatch,
    *,
    population: int,
    initial_population: int,
    split_population_threshold: int,
    initial_energy: float,
    energy_min: float,
) -> tuple[ECSWorld, int, tuple[int, int], float]:
    """Runs one interaction tick with only the mitosis branch active and deterministic offspring placement."""
    world = ECSWorld()
    env = GridEnvironment(width=4, height=4, num_signals=1, num_toxins=1)
    offspring_pos = (2, 1)
    monkeypatch.setattr(
        "phids.engine.systems.interaction._random_walk_step",
        lambda x, y, width, height: offspring_pos,
    )

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
    swarm.initial_population = initial_population
    swarm.move_cooldown = 1
    swarm.energy_upkeep_per_individual = 0.0
    swarm.reproduction_energy_divisor = 1_000_000.0
    swarm.split_population_threshold = split_population_threshold

    run_interaction(world, env, diet_matrix=_NO_DIET_MATRIX, tick=0)
    return world, swarm_id, offspring_pos, initial_energy


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
    energy_min = 2.0
    baseline_energy = population * energy_min
    initial_energy = baseline_energy * energy_fraction

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

    world, swarm_id = _run_attrition_step(
        add_swarm,
        population=population,
        initial_energy=initial_energy,
        upkeep=upkeep,
        energy_min=energy_min,
    )

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
        world, swarm_id = _run_attrition_step(
            add_swarm,
            population=population,
            initial_energy=initial_energy,
            upkeep=upkeep,
        )

        if not world.has_entity(swarm_id):
            return (0, 0.0, False)
        updated = world.get_entity(swarm_id).get_component(SwarmComponent)
        return (updated.population, float(updated.energy), True)

    low_population, low_energy, _ = _step(initial_energy=0.0)
    high_population, high_energy, _ = _step(initial_energy=32.0)

    assert high_population >= low_population
    assert high_energy >= low_energy


@pytest.mark.parametrize("population", [1, 4, 8, 16])
@pytest.mark.parametrize("energy_min", [1.0, 2.0, 4.0])
def test_zero_upkeep_is_identity_map_for_population_and_energy(
    add_swarm: Callable[..., int],
    population: int,
    energy_min: float,
) -> None:
    """Zero upkeep preserves both population and energy exactly when attrition is the only active sub-phase."""
    initial_energy = float(population) * energy_min * 0.75
    world, swarm_id = _run_attrition_step(
        add_swarm,
        population=population,
        initial_energy=initial_energy,
        upkeep=0.0,
        energy_min=energy_min,
    )

    assert world.has_entity(swarm_id)
    updated = world.get_entity(swarm_id).get_component(SwarmComponent)
    assert updated.population == population
    assert updated.energy == pytest.approx(initial_energy)


@pytest.mark.parametrize(
    ("deficit", "expected_population", "expected_energy"),
    [
        (2.0, 3, 0.0),
        (2.1, 2, 1.9),
        (6.0, 1, 0.0),
        (6.1, 0, 0.0),
    ],
)
def test_deficit_ceiling_rule_and_cleanup_boundaries(
    add_swarm: Callable[..., int],
    deficit: float,
    expected_population: int,
    expected_energy: float,
) -> None:
    """Exact and fractional deficits obey the ceiling casualty rule and remove extinct swarms consistently."""
    population = 4
    energy_min = 2.0
    upkeep = 1.0
    metabolic_cost = population * energy_min * upkeep
    initial_energy = metabolic_cost - deficit

    world, swarm_id = _run_attrition_step(
        add_swarm,
        population=population,
        initial_energy=initial_energy,
        upkeep=upkeep,
        energy_min=energy_min,
    )

    if expected_population == 0:
        assert not world.has_entity(swarm_id)
        return

    assert world.has_entity(swarm_id)
    updated = world.get_entity(swarm_id).get_component(SwarmComponent)
    assert updated.population == expected_population
    assert updated.energy == pytest.approx(expected_energy)
    assert 0.0 <= updated.energy < energy_min


@pytest.mark.parametrize("population", [1, 2, 4, 8, 16])
@pytest.mark.parametrize("energy_min", [1.0, 2.0, 4.0])
@pytest.mark.parametrize("reproduction_divisor", [1.0, 1.5, 2.0])
@pytest.mark.parametrize("surplus_units", [0.0, 0.5, 0.99, 1.0, 1.75, 2.25])
def test_reproduction_matches_closed_form_surplus_conversion(
    add_swarm: Callable[..., int],
    population: int,
    energy_min: float,
    reproduction_divisor: float,
    surplus_units: float,
) -> None:
    """Surplus-to-offspring conversion follows the closed-form floor rule under bounded inputs."""
    baseline_energy = float(population) * energy_min
    cost_per_offspring = max(energy_min, energy_min * reproduction_divisor)
    initial_energy = baseline_energy + (surplus_units * cost_per_offspring)
    surplus = max(0.0, initial_energy - baseline_energy)
    expected_offspring = int(surplus // cost_per_offspring)
    expected_population = population + expected_offspring
    expected_energy = initial_energy - (expected_offspring * cost_per_offspring)

    world, swarm_id = _run_reproduction_step(
        add_swarm,
        population=population,
        initial_energy=initial_energy,
        energy_min=energy_min,
        reproduction_divisor=reproduction_divisor,
    )

    assert world.has_entity(swarm_id)
    updated = world.get_entity(swarm_id).get_component(SwarmComponent)
    assert updated.population == expected_population
    assert updated.energy == pytest.approx(expected_energy)

    residual = updated.energy - baseline_energy
    assert residual >= 0.0
    assert residual < cost_per_offspring


@pytest.mark.parametrize("population", [2, 4, 8, 16])
@pytest.mark.parametrize("energy_min", [1.0, 2.0, 4.0])
@pytest.mark.parametrize("reproduction_divisor", [1.0, 1.5, 2.0])
def test_reproduction_population_is_monotone_in_initial_energy(
    add_swarm: Callable[..., int],
    population: int,
    energy_min: float,
    reproduction_divisor: float,
) -> None:
    """Increasing initial energy cannot reduce post-reproduction population for fixed species parameters."""
    baseline_energy = float(population) * energy_min
    cost_per_offspring = max(energy_min, energy_min * reproduction_divisor)
    low_energy = baseline_energy + (0.25 * cost_per_offspring)
    high_energy = baseline_energy + (2.25 * cost_per_offspring)

    low_world, low_id = _run_reproduction_step(
        add_swarm,
        population=population,
        initial_energy=low_energy,
        energy_min=energy_min,
        reproduction_divisor=reproduction_divisor,
    )
    high_world, high_id = _run_reproduction_step(
        add_swarm,
        population=population,
        initial_energy=high_energy,
        energy_min=energy_min,
        reproduction_divisor=reproduction_divisor,
    )

    low_population = low_world.get_entity(low_id).get_component(SwarmComponent).population
    high_population = high_world.get_entity(high_id).get_component(SwarmComponent).population
    assert high_population >= low_population


@pytest.mark.parametrize(
    (
        "population",
        "initial_population",
        "split_population_threshold",
        "should_split",
    ),
    [
        (7, 4, 8, False),
        (8, 4, 8, True),
        (9, 4, 8, True),
        (9, 5, 0, False),
        (10, 5, 0, True),
        (11, 5, 0, True),
    ],
)
def test_mitosis_threshold_and_partition_invariants(
    add_swarm: Callable[..., int],
    monkeypatch: pytest.MonkeyPatch,
    population: int,
    initial_population: int,
    split_population_threshold: int,
    should_split: bool,
) -> None:
    """Mitosis triggers at threshold and conserves population/energy via deterministic binary partitioning."""
    initial_energy = 12.0
    energy_min = 2.0
    world, parent_id, offspring_pos, pre_split_energy = _run_mitosis_step(
        add_swarm,
        monkeypatch,
        population=population,
        initial_population=initial_population,
        split_population_threshold=split_population_threshold,
        initial_energy=initial_energy,
        energy_min=energy_min,
    )

    swarms = [entity.get_component(SwarmComponent) for entity in world.query(SwarmComponent)]
    if not should_split:
        assert len(swarms) == 1
        assert swarms[0].population == population
        assert swarms[0].energy == pytest.approx(pre_split_energy)
        return

    assert len(swarms) == 2
    offspring_ids = [
        entity.entity_id for entity in world.query(SwarmComponent) if entity.entity_id != parent_id
    ]
    assert len(offspring_ids) == 1

    parent = world.get_entity(parent_id).get_component(SwarmComponent)
    offspring = world.get_entity(offspring_ids[0]).get_component(SwarmComponent)

    assert parent.population + offspring.population == population
    assert sorted([parent.population, offspring.population]) == sorted(
        [population // 2, population - (population // 2)],
    )
    assert parent.energy == pytest.approx(pre_split_energy / 2.0)
    assert offspring.energy == pytest.approx(pre_split_energy / 2.0)

    assert parent_id in world.entities_at(parent.x, parent.y)
    assert offspring_ids[0] in world.entities_at(*offspring_pos)
    assert (offspring.x, offspring.y) == offspring_pos
