# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for Branchless Capacity Masking in swarm movement logic."""

from __future__ import annotations

import numpy as np

from phids.engine.systems.interaction.movement import (
    _apply_branchless_capacity_mask_jit,
    _weighted_field_choice_jit,
)


def test_apply_branchless_capacity_mask_zeros_overcrowded_tiles() -> None:
    """Verify that candidate tiles exceeding capacity have their weight masked to 0.0 branchlessly."""
    count = 5
    width = 10
    max_cap = 500

    # Current cell (5,5) at index 0
    # Neighbor cell 1: (4,5) -> population 100 (allowed)
    # Neighbor cell 2: (6,5) -> population 600 (overcrowded!)
    # Neighbor cell 3: (5,4) -> population 50 (allowed)
    # Neighbor cell 4: (5,6) -> population 550 (overcrowded!)
    c_x = np.array([5, 4, 6, 5, 5], dtype=np.int32)
    c_y = np.array([5, 5, 5, 4, 6], dtype=np.int32)

    tile_populations = np.zeros(100, dtype=np.int32)
    tile_populations[5 * width + 4] = 100
    tile_populations[5 * width + 6] = 600  # Over capacity
    tile_populations[4 * width + 5] = 50
    tile_populations[6 * width + 5] = 550  # Over capacity

    weights = np.ones(5, dtype=np.float64)

    total_w = _apply_branchless_capacity_mask_jit(
        count,
        5,
        5,
        width,
        c_x,
        c_y,
        tile_populations,
        max_cap,
        weights,
    )

    # Current cell (index 0) remains weight 1.0
    assert weights[0] == 1.0
    # Neighbor 1 (index 1) under capacity -> weight 1.0
    assert weights[1] == 1.0
    # Neighbor 2 (index 2) over capacity -> weight 0.0 (masked!)
    assert weights[2] == 0.0
    # Neighbor 3 (index 3) under capacity -> weight 1.0
    assert weights[3] == 1.0
    # Neighbor 4 (index 4) over capacity -> weight 0.0 (masked!)
    assert weights[4] == 0.0

    assert total_w == 3.0


def test_weighted_field_choice_jit_with_capacity_masking() -> None:
    """Verify that _weighted_field_choice_jit respects branchless capacity masking."""
    count = 5
    width = 10
    max_cap = 500

    c_x = np.array([5, 4, 6, 5, 5], dtype=np.int32)
    c_y = np.array([5, 5, 5, 4, 6], dtype=np.int32)

    scores = np.array([1.0, 10.0, 100.0, 10.0, 100.0], dtype=np.float64)
    adjusted_scores = np.empty(5, dtype=np.float64)
    weights = np.empty(5, dtype=np.float64)

    tile_populations = np.zeros(100, dtype=np.int32)
    # Target high-score tiles (6,5) and (5,6) are overcrowded
    tile_populations[5 * width + 6] = 600
    tile_populations[6 * width + 5] = 600

    # Pick with rand_val = 0.5
    selected_x, selected_y = _weighted_field_choice_jit(
        count=count,
        invert=False,
        scores=scores,
        c_x=c_x,
        c_y=c_y,
        adjusted_scores=adjusted_scores,
        weights=weights,
        rand_val=0.5,
        tile_populations=tile_populations,
        width=width,
        max_capacity=max_cap,
        current_x=5,
        current_y=5,
    )

    # Overcrowded high-score cells (6,5) and (5,6) must NOT be selected
    assert (selected_x, selected_y) != (6, 5)
    assert (selected_x, selected_y) != (5, 6)
