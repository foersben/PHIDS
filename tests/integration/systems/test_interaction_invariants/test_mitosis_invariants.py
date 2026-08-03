# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Deterministic closed-form invariant checks for the mitosis (binary fission) sub-phase.

This module verifies that the interaction system's mitosis branch triggers at the
correct population threshold and conserves both population and energy via
deterministic binary partitioning.

Step-runner helpers are imported from ``conftest.py`` (shared with
``test_interaction_hypothesis_pilot.py``).
"""

from __future__ import annotations

import pytest
from tests.integration.systems._interaction_helpers import run_mitosis_step

from phids.engine.components.swarm import SwarmComponent


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
        (9, 5, 10, False),
        (10, 5, 10, True),
        (11, 5, 10, True),
    ],
)
def test_mitosis_threshold_and_partition_invariants(
    population: int,
    initial_population: int,
    split_population_threshold: int,
    should_split: bool,
) -> None:
    """Mitosis triggers at threshold and conserves population/energy via deterministic binary partitioning.

    Intent:
        Verify six boundary cases: two below-threshold cases that must NOT split and
        four at-or-above-threshold cases that MUST split. For splits, confirm population
        and energy are exactly halved between parent and offspring.

    Preconditions:
        - Swarm placed at (1,1) on a 4x4 grid with initial_energy=12.0, energy_min=2.0.
        - Offspring placement patched to deterministic position (2,1).
        - Attrition, reproduction, movement, and feeding all suppressed.

    Invariants Tested:
        - No-split: single swarm remains; population and energy unchanged.
        - Split: exactly two swarms exist post-tick.
        - parent.population + offspring.population == population.
        - Populations sorted match [population//2, population - population//2].
        - parent.energy == pytest.approx(pre_split_energy / 2.0).
        - offspring.energy == pytest.approx(pre_split_energy / 2.0).
        - Spatial registration correct for both swarms.
    """
    initial_energy = 12.0
    energy_min = 2.0

    world, parent_id, offspring_pos, pre_split_energy = run_mitosis_step(
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
    offspring_ids = [entity.entity_id for entity in world.query(SwarmComponent) if entity.entity_id != parent_id]
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
