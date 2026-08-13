# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for Plan 2 trampling FMA kernel and MVT Full Belly Override movement lock."""

from __future__ import annotations

import numpy as np

from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.systems.interaction.movement import (
    _compute_trample_probability_jit,
    _is_swarm_anchored,
    _is_swarm_anchored_jit,
)


def test_zero_mass_full_vulnerability() -> None:
    """Validate that zero structural mass (seedling) yields maximum vulnerability (1.0)."""
    # max_structural_mass = 0.0 -> fallback vulnerability = 1.0
    prob = _compute_trample_probability_jit(
        swarm_population=100,
        trample_factor=0.01,
        structural_mass=0.0,
        max_structural_mass=0.0,
    )
    # 100 * 0.01 * 1.0 = 1.0
    assert prob == 1.0


def test_adult_mass_zero_vulnerability() -> None:
    """Validate that full adult structural mass (M_structural == max) yields zero vulnerability (0.0)."""
    prob = _compute_trample_probability_jit(
        swarm_population=100,
        trample_factor=0.05,
        structural_mass=150.0,
        max_structural_mass=150.0,
    )
    # vulnerability = max(0, 1 - 150/150) = 0.0 -> P = 0.0
    assert prob == 0.0


def test_trampling_probability_linear_scaling() -> None:
    """Validate linear scaling of trampling probability between 0 and max structural mass."""
    # Half-grown plant: structural_mass = 50, max = 100 -> vulnerability = 0.5
    prob = _compute_trample_probability_jit(
        swarm_population=50,
        trample_factor=0.01,
        structural_mass=50.0,
        max_structural_mass=100.0,
    )
    # 50 * 0.01 * 0.5 = 0.25
    assert np.isclose(prob, 0.25)


def test_mvt_full_belly_override_locks_movement() -> None:
    """Validate Marginal Value Theorem (MVT) Full Belly Override locks movement when intake >= upkeep."""
    plant_energy = np.zeros((1, 5, 5), dtype=np.float64)
    diet = np.ones((1, 1), dtype=np.bool_)

    # Case 1: Low nutrition, no food co-located, zero intake -> not anchored
    anchored_empty = _is_swarm_anchored_jit(
        x=2,
        y=2,
        species_id=0,
        apparent_nutrition_val=0.1,
        plant_energy_by_species=plant_energy,
        diet_matrix=diet,
        caloric_intake=0.0,
        metabolic_upkeep=5.0,
    )
    assert not anchored_empty

    # Case 2: Full belly (caloric_intake=6.0 >= metabolic_upkeep=5.0) -> anchored!
    anchored_full = _is_swarm_anchored_jit(
        x=2,
        y=2,
        species_id=0,
        apparent_nutrition_val=0.1,
        plant_energy_by_species=plant_energy,
        diet_matrix=diet,
        caloric_intake=6.0,
        metabolic_upkeep=5.0,
    )
    assert anchored_full


def test_is_swarm_anchored_python_wrapper_extracts_mvt() -> None:
    """Validate that _is_swarm_anchored Python wrapper extracts last_caloric_intake and metabolism_upkeep."""
    env = GridEnvironment(width=5, height=5)
    diet = [[True]]

    swarm = SwarmComponent(
        entity_id=1,
        species_id=0,
        x=2,
        y=2,
        population=10,
        initial_population=10,
        energy=100.0,
        energy_min=1.0,
        velocity=1,
        consumption_rate=2.0,
    )
    swarm.last_caloric_intake = 10.0  # type: ignore[attr-defined]
    swarm.metabolism_upkeep = 5.0  # type: ignore[attr-defined]

    # Full belly override should return True even on empty grid
    assert _is_swarm_anchored(swarm, env, diet)
