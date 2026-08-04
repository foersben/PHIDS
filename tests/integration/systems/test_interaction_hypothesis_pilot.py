# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Optional Hypothesis pilot for bounded interaction-system arithmetic invariants.

# MUTATION_TESTING_EXEMPTION: Stochastic / Hypothesis-driven test suite.
# Non-deterministic input generation makes mutmut results unreliable and
# causes excessive runtime. The equivalent deterministic parametric coverage
# lives in test_interaction_invariants/.

This pilot draws random inputs from bounded ``hypothesis`` strategies to
extend confidence beyond the fixed parametric grid in
``test_interaction_invariants/``. When Hypothesis is not installed the
entire module is skipped gracefully.

Step-runner helpers (``run_attrition_step``, ``run_reproduction_step``,
``run_mitosis_step``) are imported from
``test_interaction_invariants/conftest.py`` - the single authoritative source
shared with the deterministic parametric suite.
"""

from __future__ import annotations

import math

import pytest

# Import shared step-runners from the authoritative single source.
# This eliminates all previously duplicated helper functions.
from tests.integration.systems._interaction_helpers import (
    run_attrition_step,
    run_mitosis_step,
    run_reproduction_step,
)

from phids.engine.components.swarm import SwarmComponent

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st
except ModuleNotFoundError:
    pytest.skip("Install hypothesis to run optional property pilots.", allow_module_level=True)


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
    """Bounded random inputs preserve the documented attrition casualty and residual formulas.

    Intent:
        Extend the deterministic parametric sweep with Hypothesis-generated inputs
        to increase statistical confidence in the closed-form attrition model.

    Preconditions:
        - upkeep derived from upkeep_quarters / 4.0 to avoid floating-point drift.
        - initial_energy scaled to half-unit multiples of energy_min.
        - Hypothesis profile: max_examples=128, derandomize=True for reproducibility.

    Invariants Tested:
        - Same casualty and residual energy formulas as the deterministic suite.
        - Extinct swarms are removed from ECS; non-zero survivors retain non-negative energy.
    """
    upkeep = upkeep_quarters / 4.0
    initial_energy = initial_energy_units * (energy_min / 2.0)

    metabolic_cost = population * energy_min * upkeep * 24
    post_cost_energy = initial_energy - metabolic_cost
    if post_cost_energy >= 0.0:
        expected_population = population
        expected_energy = post_cost_energy
    else:
        deficit = -post_cost_energy
        casualties = math.ceil(deficit / energy_min)
        expected_population = max(0, population - casualties)
        expected_energy = max(0.0, (casualties * energy_min) - deficit)

    world, swarm_id = run_attrition_step(
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
    """Bounded random inputs preserve floor-based surplus-to-offspring conversion.

    Intent:
        Extend the deterministic parametric reproduction tests using Hypothesis to
        cover fractional surplus combinations not enumerated in the fixed grid.

    Preconditions:
        - initial_energy = baseline + (whole_surplus_units + fractional_surplus) * cost_per_offspring.
        - Hypothesis profile: max_examples=128, derandomize=True for reproducibility.

    Invariants Tested:
        - updated.population == population + floor(surplus / cost_per_offspring).
        - Residual energy satisfies 0 <= residual < cost_per_offspring.
    """
    baseline_energy = float(population) * energy_min
    cost_per_offspring = max(energy_min, energy_min * reproduction_divisor)
    initial_energy = baseline_energy + ((whole_surplus_units + fractional_surplus) * cost_per_offspring)

    surplus = max(0.0, initial_energy - baseline_energy)
    expected_offspring = int(surplus // cost_per_offspring)
    expected_population = population + expected_offspring
    expected_energy = initial_energy - (expected_offspring * cost_per_offspring)

    world, swarm_id = run_reproduction_step(
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
    """Bounded random inputs preserve threshold semantics and binary fission conservation laws.

    Intent:
        Extend the deterministic six-case mitosis parametrization with Hypothesis-
        generated inputs spanning the full combinatorial space of threshold, energy,
        and population parameters.

    Preconditions:
        - Hypothesis profile: max_examples=96, derandomize=True for reproducibility.
        - Offspring placement deterministically patched to (2,1) inside run_mitosis_step.

    Invariants Tested:
        - Below threshold: single swarm, population and energy unchanged.
        - At or above threshold: exactly two swarms; binary fission conserves population and energy.
    """
    world, parent_id, offspring_pos, pre_split_energy = run_mitosis_step(
        population=population,
        initial_population=initial_population,
        split_population_threshold=split_population_threshold,
        initial_energy=energy,
        energy_min=energy_min,
    )

    split_threshold = split_population_threshold
    should_split = population >= split_threshold

    swarms = [entity.get_component(SwarmComponent) for entity in world.query(SwarmComponent)]
    if not should_split:
        assert len(swarms) == 1
        assert swarms[0].population == population
        assert swarms[0].energy == pytest.approx(pre_split_energy)
        return

    assert len(swarms) == 2
    offspring_ids = [entity.entity_id for entity in world.query(SwarmComponent) if entity.entity_id != parent_id]
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
