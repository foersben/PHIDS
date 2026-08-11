# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for movement system list population conversion and aversion memory decay branches."""

from __future__ import annotations

import numpy as np
import pytest

from phids.engine.components.swarm import SwarmComponent
from phids.engine.systems.interaction.movement import (
    _choose_neighbour_by_flow_probability,
)


@pytest.mark.unit
def test_choose_neighbour_with_list_populations() -> None:
    """Verify that _choose_neighbour_by_flow_probability handles list tile_populations input cleanly.

    Raises:
        AssertionError: If neighbour choice fails when tile_populations is passed as a list.
    """
    swarm = SwarmComponent(
        entity_id=1,
        species_id=0,
        x=5,
        y=5,
        population=10,
        initial_population=10,
        energy=50.0,
        energy_min=5.0,
        velocity=1,
        consumption_rate=5.0,
    )
    flow_field = np.ones((16, 16), dtype=np.float64)
    tile_pops_list = [0] * (16 * 16)
    cx = np.zeros(5, dtype=np.int32)
    cy = np.zeros(5, dtype=np.int32)
    scores = np.zeros(5, dtype=np.float64)
    adj_scores = np.zeros(5, dtype=np.float64)
    weights = np.zeros(5, dtype=np.float64)

    nx, ny = _choose_neighbour_by_flow_probability(
        swarm=swarm,
        flow_field=flow_field,
        width=16,
        height=16,
        invert=False,
        c_x=cx,
        c_y=cy,
        scores=scores,
        adjusted_scores=adj_scores,
        weights=weights,
        tile_populations=tile_pops_list,
    )

    assert 0 <= nx < 16
    assert 0 <= ny < 16


@pytest.mark.unit
def test_python_movement_fallbacks() -> None:
    """Verify python movement fallback logic when random choice is mocked or non-flat fields are evaluated."""
    from phids.engine.systems.interaction.movement import (
        _choose_neighbour_by_flow_probability_python,
        _python_flat_field_choice,
    )

    swarm = SwarmComponent(
        entity_id=1,
        species_id=0,
        x=5,
        y=5,
        population=10,
        initial_population=10,
        energy=50.0,
        energy_min=5.0,
        velocity=1,
        consumption_rate=5.0,
        last_dx=1,
        last_dy=0,
    )

    # Flat field test
    candidates = [(5, 5), (4, 5), (6, 5), (5, 4), (5, 6)]
    choice = _python_flat_field_choice(swarm, candidates)
    assert choice in candidates

    # Flat field test with zero inertia
    swarm.last_dx = 0
    swarm.last_dy = 0
    choice2 = _python_flat_field_choice(swarm, candidates)
    assert choice2 in candidates

    # Non-flat flow field test
    flow_field = np.zeros((16, 16), dtype=np.float64)
    flow_field[6, 5] = 10.0  # attractant hotspot
    nx, ny = _choose_neighbour_by_flow_probability_python(swarm, flow_field, 16, 16, invert=False)
    assert 0 <= nx < 16 and 0 <= ny < 16

    # Inverted flow field test
    nx_inv, ny_inv = _choose_neighbour_by_flow_probability_python(swarm, flow_field, 16, 16, invert=True)
    assert 0 <= nx_inv < 16 and 0 <= ny_inv < 16


@pytest.mark.unit
def test_random_walk_step_mocked_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify _random_walk_step when random.choice is monkeypatched."""
    from phids.engine.systems.interaction.movement import _random_walk_step

    def dummy_choice(seq: list[tuple[int, int]]) -> tuple[int, int]:
        return seq[0]

    monkeypatch.setattr("random.choice", dummy_choice)
    cx = np.zeros(5, dtype=np.int32)
    cy = np.zeros(5, dtype=np.int32)
    res = _random_walk_step(5, 5, 16, 16, cx, cy)
    assert res == (5, 5)
