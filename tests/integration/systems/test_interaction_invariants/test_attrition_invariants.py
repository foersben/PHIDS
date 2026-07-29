# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Deterministic closed-form invariant checks for the metabolic attrition sub-phase.

This module verifies that the interaction system's per-tick attrition arithmetic
matches the analytically derived casualty and residual energy formulas across
bounded parameter sweeps. Each test function isolates the attrition branch by
suppressing movement, feeding, reproduction, and mitosis so that only
energy-drain and casualty logic mutate the ECS world state.

Step-runner helpers are defined in ``tests/integration/systems/conftest.py``
(the single authoritative source shared with ``test_interaction_hypothesis_pilot.py``).
"""

from __future__ import annotations

import math

import pytest
from tests.integration.systems._interaction_helpers import run_attrition_step

from phids.engine.components.swarm import SwarmComponent


@pytest.mark.parametrize("population", [1, 2, 3, 5, 8, 13, 16])
@pytest.mark.parametrize("upkeep", [0.0, 0.25, 0.5, 1.0, 1.5, 2.0])
@pytest.mark.parametrize("energy_fraction", [0.0, 0.25, 0.5, 0.75, 1.0])
def test_attrition_matches_closed_form_over_bounded_parameter_sweep(
    population: int,
    upkeep: float,
    energy_fraction: float,
) -> None:
    """Metabolic attrition follows the closed-form casualty/remainder equations over bounded inputs.

    Intent:
        Verify that for every combination of population (1-16), upkeep coefficient
        (0.0-2.0), and initial energy fraction (0.0-1.0 of the survival baseline),
        the interaction system produces exactly the analytically predicted survivor
        count and residual energy.

    Preconditions:
        - Single swarm with ``energy_min=2.0`` at position (1,1) on a 3x3 grid.
        - Movement, reproduction, and mitosis disabled via cooldown/divisor overrides.
        - Feeding suppressed by all-False diet matrix.

    Invariants Tested:
        - Post-tick population == max(0, population - ceil(deficit / energy_min)).
        - Post-tick energy == max(0.0, casualties * energy_min - deficit).
        - Extinct swarms are removed from the ECS world entirely.
    """
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

    world, swarm_id = run_attrition_step(
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
    population: int,
    upkeep: float,
) -> None:
    """Higher initial energy cannot yield lower surviving population or lower residual energy.

    Intent:
        Confirm the attrition function is monotone: starting with more energy
        can only leave the swarm equal or better off, never worse.

    Preconditions:
        - Two independent ticks: one with initial_energy=0.0, one with 32.0.
        - All non-attrition phases disabled.

    Invariants Tested:
        - high_population >= low_population.
        - high_energy >= low_energy.
    """

    def _step(initial_energy: float) -> tuple[int, float, bool]:
        """Run one attrition tick and return (population, energy, survived)."""
        world, swarm_id = run_attrition_step(
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
    population: int,
    energy_min: float,
) -> None:
    """Zero upkeep preserves both population and energy exactly when attrition is the only active sub-phase.

    Intent:
        When upkeep=0.0 the metabolic cost is zero and no casualties should occur.
        Energy must remain exactly at its initial value.

    Preconditions:
        - Initial energy set to 75% of the survival baseline (population * energy_min * 0.75).
        - upkeep=0.0 so metabolic_cost=0.

    Invariants Tested:
        - population unchanged after tick.
        - energy == pytest.approx(initial_energy).
    """
    initial_energy = float(population) * energy_min * 0.75
    world, swarm_id = run_attrition_step(
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
    deficit: float,
    expected_population: int,
    expected_energy: float,
) -> None:
    """Exact and fractional deficits obey the ceiling casualty rule and remove extinct swarms consistently.

    Intent:
        Verify four edge cases around the boundary between losing N vs N+1 individuals,
        including the degenerate case where the entire swarm is eliminated.

    Preconditions:
        - population=4, energy_min=2.0, upkeep=1.0 (metabolic_cost = 8.0).
        - initial_energy = metabolic_cost - deficit (induces a predictable shortfall).

    Invariants Tested:
        - Ceiling rule: casualties = ceil(deficit / energy_min).
        - Swarm removed from world when expected_population == 0.
        - Residual energy satisfies 0.0 <= energy < energy_min for surviving swarms.
    """
    population = 4
    energy_min = 2.0
    upkeep = 1.0
    metabolic_cost = population * energy_min * upkeep
    initial_energy = metabolic_cost - deficit

    world, swarm_id = run_attrition_step(
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
