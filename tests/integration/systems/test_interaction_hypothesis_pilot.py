"""Optional Hypothesis pilot for bounded interaction-system arithmetic invariants."""

from __future__ import annotations

import math
from unittest.mock import patch

import numpy as np
import pytest

from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.engine.systems.interaction import run_interaction

try:
    from hypothesis import given, settings, strategies as st
except ModuleNotFoundError:
    pytest.skip("Install hypothesis to run optional property pilots.", allow_module_level=True)


_NO_DIET_MATRIX = np.zeros((1, 1), dtype=np.bool_)


def _spawn_swarm(
    world: ECSWorld,
    *,
    x: int,
    y: int,
    species_id: int,
    population: int,
    energy: float,
    energy_min: float,
    velocity: int,
    consumption_rate: float,
) -> int:
    """Spawn and register one swarm entity for local pilot setup."""
    entity = world.create_entity()
    world.add_component(
        entity.entity_id,
        SwarmComponent(
            entity_id=entity.entity_id,
            species_id=species_id,
            x=x,
            y=y,
            population=population,
            initial_population=max(1, population // 2),
            energy=energy,
            energy_min=energy_min,
            velocity=velocity,
            consumption_rate=consumption_rate,
        ),
    )
    world.register_position(entity.entity_id, x, y)
    return entity.entity_id


def _run_attrition_only(
    *,
    population: int,
    initial_energy: float,
    energy_min: float,
    upkeep: float,
) -> tuple[ECSWorld, int]:
    """Run one interaction tick with only metabolic attrition enabled."""
    world = ECSWorld()
    env = GridEnvironment(width=3, height=3, num_signals=1, num_toxins=1)

    swarm_id = _spawn_swarm(
        world,
        x=1,
        y=1,
        species_id=0,
        population=population,
        energy=initial_energy,
        energy_min=energy_min,
        velocity=1,
        consumption_rate=1.0,
    )
    swarm = world.get_entity(swarm_id).get_component(SwarmComponent)
    swarm.move_cooldown = 1
    swarm.energy_upkeep_per_individual = upkeep
    swarm.reproduction_energy_divisor = 1_000_000.0
    swarm.split_population_threshold = 1000

    run_interaction(world, env, diet_matrix=_NO_DIET_MATRIX, tick=0)
    return world, swarm_id


def _run_reproduction_only(
    *,
    population: int,
    initial_energy: float,
    energy_min: float,
    reproduction_divisor: float,
) -> tuple[ECSWorld, int]:
    """Run one interaction tick with only reproduction arithmetic enabled."""
    world = ECSWorld()
    env = GridEnvironment(width=3, height=3, num_signals=1, num_toxins=1)

    swarm_id = _spawn_swarm(
        world,
        x=1,
        y=1,
        species_id=0,
        population=population,
        energy=initial_energy,
        energy_min=energy_min,
        velocity=1,
        consumption_rate=1.0,
    )
    swarm = world.get_entity(swarm_id).get_component(SwarmComponent)
    swarm.move_cooldown = 1
    swarm.energy_upkeep_per_individual = 0.0
    swarm.reproduction_energy_divisor = reproduction_divisor
    swarm.split_population_threshold = 1000

    run_interaction(world, env, diet_matrix=_NO_DIET_MATRIX, tick=0)
    return world, swarm_id


def _run_mitosis_only(
    *,
    population: int,
    initial_population: int,
    split_population_threshold: int,
    energy: float,
    energy_min: float,
) -> tuple[ECSWorld, int, tuple[int, int], float]:
    """Run one interaction tick with only the mitosis branch enabled and deterministic offspring placement."""
    world = ECSWorld()
    env = GridEnvironment(width=4, height=4, num_signals=1, num_toxins=1)
    offspring_pos = (2, 1)

    swarm_id = _spawn_swarm(
        world,
        x=1,
        y=1,
        species_id=0,
        population=population,
        energy=energy,
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

    with patch(
        "phids.engine.systems.interaction._random_walk_step",
        return_value=offspring_pos,
    ):
        run_interaction(world, env, diet_matrix=_NO_DIET_MATRIX, tick=0)
    return world, swarm_id, offspring_pos, energy


@pytest.mark.hypothesis_pilot
@settings(max_examples=128, deadline=None, derandomize=True)
@given(
    population=st.integers(min_value=1, max_value=16),
    energy_min=st.sampled_from((1.0, 2.0, 4.0)),
    upkeep_quarters=st.integers(min_value=0, max_value=8),
    initial_energy_units=st.integers(min_value=0, max_value=256),
)
def test_attrition_closed_form_holds_for_bounded_hypothesis_samples(
    population: int,
    energy_min: float,
    upkeep_quarters: int,
    initial_energy_units: int,
) -> None:
    """Bounded random inputs preserve the documented attrition casualty and residual formulas."""
    upkeep = upkeep_quarters / 4.0
    initial_energy = initial_energy_units * (energy_min / 2.0)

    metabolic_cost = population * energy_min * upkeep
    post_cost_energy = initial_energy - metabolic_cost
    if post_cost_energy >= 0.0:
        expected_population = population
        expected_energy = post_cost_energy
    else:
        deficit = -post_cost_energy
        casualties = math.ceil(deficit / energy_min)
        expected_population = max(0, population - casualties)
        expected_energy = max(0.0, (casualties * energy_min) - deficit)

    world, swarm_id = _run_attrition_only(
        population=population,
        initial_energy=initial_energy,
        energy_min=energy_min,
        upkeep=upkeep,
    )

    if expected_population == 0:
        assert not world.has_entity(swarm_id)
        return

    assert world.has_entity(swarm_id)
    updated = world.get_entity(swarm_id).get_component(SwarmComponent)
    assert updated.population == expected_population
    assert updated.energy == pytest.approx(expected_energy)
    assert 0.0 <= updated.energy


@pytest.mark.hypothesis_pilot
@settings(max_examples=128, deadline=None, derandomize=True)
@given(
    population=st.integers(min_value=1, max_value=16),
    energy_min=st.sampled_from((1.0, 2.0, 4.0)),
    reproduction_divisor=st.sampled_from((1.0, 1.5, 2.0)),
    whole_surplus_units=st.integers(min_value=0, max_value=8),
    fractional_surplus=st.sampled_from((0.0, 0.1, 0.5, 0.99)),
)
def test_reproduction_closed_form_holds_for_bounded_hypothesis_samples(
    population: int,
    energy_min: float,
    reproduction_divisor: float,
    whole_surplus_units: int,
    fractional_surplus: float,
) -> None:
    """Bounded random inputs preserve floor-based surplus-to-offspring conversion."""
    baseline_energy = float(population) * energy_min
    cost_per_offspring = max(energy_min, energy_min * reproduction_divisor)
    initial_energy = baseline_energy + (
        (whole_surplus_units + fractional_surplus) * cost_per_offspring
    )

    surplus = max(0.0, initial_energy - baseline_energy)
    expected_offspring = int(surplus // cost_per_offspring)
    expected_population = population + expected_offspring
    expected_energy = initial_energy - (expected_offspring * cost_per_offspring)

    world, swarm_id = _run_reproduction_only(
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


@pytest.mark.hypothesis_pilot
@settings(max_examples=96, deadline=None, derandomize=True)
@given(
    population=st.integers(min_value=1, max_value=16),
    initial_population=st.integers(min_value=1, max_value=8),
    split_population_threshold=st.sampled_from((0, 8, 10, 12, 16)),
    energy=st.sampled_from((4.0, 8.0, 12.0, 16.0, 24.0)),
    energy_min=st.sampled_from((1.0, 2.0, 4.0)),
)
def test_mitosis_threshold_partition_and_energy_halving_hold_for_bounded_hypothesis_samples(
    population: int,
    initial_population: int,
    split_population_threshold: int,
    energy: float,
    energy_min: float,
) -> None:
    """Bounded random inputs preserve threshold semantics and binary fission conservation laws."""
    world, parent_id, offspring_pos, pre_split_energy = _run_mitosis_only(
        population=population,
        initial_population=initial_population,
        split_population_threshold=split_population_threshold,
        energy=energy,
        energy_min=energy_min,
    )

    split_threshold = (
        split_population_threshold if split_population_threshold > 0 else 2 * initial_population
    )
    should_split = population >= split_threshold

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
    assert sorted((parent.population, offspring.population)) == sorted(
        (population // 2, population - (population // 2)),
    )
    assert parent.energy == pytest.approx(pre_split_energy / 2.0)
    assert offspring.energy == pytest.approx(pre_split_energy / 2.0)
    assert parent_id in world.entities_at(parent.x, parent.y)
    assert offspring_ids[0] in world.entities_at(*offspring_pos)
    assert (offspring.x, offspring.y) == offspring_pos
