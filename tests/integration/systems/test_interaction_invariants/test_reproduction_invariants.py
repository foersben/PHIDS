# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Deterministic closed-form invariant checks for the reproduction sub-phase.

This module verifies that the interaction system's surplus-energy-to-offspring
conversion follows the floor-division closed form across bounded parameter sweeps,
and that reproduction is monotone with respect to initial energy.

Step-runner helpers are imported from ``conftest.py`` (shared with
``test_interaction_hypothesis_pilot.py``).
"""

from __future__ import annotations

import pytest
from tests.integration.systems._interaction_helpers import run_reproduction_step

from phids.engine.components.swarm import SwarmComponent


@pytest.mark.parametrize("population", [1, 2, 4, 8, 16])
@pytest.mark.parametrize("energy_min", [1.0, 2.0, 4.0])
@pytest.mark.parametrize("reproduction_divisor", [1.0, 1.5, 2.0])
@pytest.mark.parametrize("surplus_units", [0.0, 0.5, 0.99, 1.0, 1.75, 2.25])
def test_reproduction_matches_closed_form_surplus_conversion(
    population: int,
    energy_min: float,
    reproduction_divisor: float,
    surplus_units: float,
) -> None:
    """Surplus-to-offspring conversion follows the closed-form floor rule under bounded inputs.

    Intent:
        Confirm that for every combination of population, energy_min, reproduction
        divisor, and fractional surplus units, the interaction system produces exactly
        floor(surplus / cost_per_offspring) new individuals.

    Preconditions:
        - initial_energy = baseline + (surplus_units * cost_per_offspring).
        - Attrition upkeep zeroed; mitosis split threshold set high to prevent fission.
        - All-False diet matrix suppresses feeding.

    Invariants Tested:
        - updated.population == population + expected_offspring.
        - updated.energy == pytest.approx(expected_energy).
        - Residual energy satisfies 0.0 <= residual < cost_per_offspring.
    """
    baseline_energy = float(population) * energy_min
    cost_per_offspring = max(energy_min, energy_min * reproduction_divisor)
    initial_energy = baseline_energy + (surplus_units * cost_per_offspring)
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


@pytest.mark.parametrize("population", [2, 4, 8, 16])
@pytest.mark.parametrize("energy_min", [1.0, 2.0, 4.0])
@pytest.mark.parametrize("reproduction_divisor", [1.0, 1.5, 2.0])
def test_reproduction_population_is_monotone_in_initial_energy(
    population: int,
    energy_min: float,
    reproduction_divisor: float,
) -> None:
    """Increasing initial energy cannot reduce post-reproduction population for fixed species parameters.

    Intent:
        Confirm monotonicity: a swarm entering the tick with more energy can never
        exit with fewer individuals than a swarm with less energy under identical
        species parameters.

    Preconditions:
        - low_energy  = baseline + 0.25 * cost_per_offspring (sub-threshold surplus).
        - high_energy = baseline + 2.25 * cost_per_offspring (super-threshold surplus).
        - Both ticks run independently with isolated ECS worlds.

    Invariants Tested:
        - high_population >= low_population.
    """
    baseline_energy = float(population) * energy_min
    cost_per_offspring = max(energy_min, energy_min * reproduction_divisor)
    low_energy = baseline_energy + (0.25 * cost_per_offspring)
    high_energy = baseline_energy + (2.25 * cost_per_offspring)

    low_world, low_id = run_reproduction_step(
        population=population,
        initial_energy=low_energy,
        energy_min=energy_min,
        reproduction_divisor=reproduction_divisor,
    )
    high_world, high_id = run_reproduction_step(
        population=population,
        initial_energy=high_energy,
        energy_min=energy_min,
        reproduction_divisor=reproduction_divisor,
    )

    low_population = low_world.get_entity(low_id).get_component(SwarmComponent).population
    high_population = high_world.get_entity(high_id).get_component(SwarmComponent).population
    assert high_population >= low_population
