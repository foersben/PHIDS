# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit Invariant Tests for Branchless Carrying Capacity Masking in Movement.

This module validates that branchless floating-point multiplication (weights * mask) correctly zero-out
candidate cell weights exceeding tile carrying capacity while preserving current cell inertia.
"""

from __future__ import annotations

import numpy as np
import pytest

from phids.engine.systems.interaction.movement import _apply_branchless_capacity_mask_jit


@pytest.mark.jit_parity
def test_numba_jit_branchless_capacity_mask_parity() -> None:
    """Verify branchless floating-point capacity masking logic.

    Candidate cell carrying capacity check mask = min(1.0, is_current + is_under_capacity).
    Over-capacity candidate cells must be masked to 0.0, while the current cell (i=0) must retain weight 1.0.

    Raises:
        AssertionError: If over-capacity candidate cell weight is non-zero or current cell weight is masked.
    """
    cx = np.array([5, 5, 6, 5, 4], dtype=np.int32)
    cy = np.array([5, 6, 5, 4, 5], dtype=np.int32)

    tile_pops = np.zeros(16 * 16, dtype=np.int32)
    width = 16
    tile_pops[6 * width + 5] = 5  # (5, 6) = 5
    tile_pops[5 * width + 6] = 1  # (6, 5) = 1
    tile_pops[4 * width + 5] = 10  # (5, 4) = 10

    max_cap = 5
    weights = np.array([1.0, 1.0, 1.0, 1.0, 1.0], dtype=np.float64)

    _apply_branchless_capacity_mask_jit(
        count=5,
        x=5,
        y=5,
        width=width,
        c_x=cx,
        c_y=cy,
        tile_populations=tile_pops,
        max_capacity=max_cap,
        weights=weights,
    )

    # Current cell (i=0) always retains weight (1.0)
    assert weights[0] == 1.0
    # Candidate 1 (pop=5 <= max_cap) retains weight 1.0
    assert weights[1] == 1.0
    # Candidate 2 (pop=1 < max_cap) retains weight 1.0
    assert weights[2] == 1.0
    # Candidate 3 (pop=10 > max_cap) masked to 0.0
    assert weights[3] == 0.0
