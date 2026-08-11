# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit Invariant Tests for Numba JIT Softmax Zero-Weight Fallback.

This module validates that when flow-field candidate weights are uniform, weighted choice
falls back deterministically without division-by-zero or NaN propagation.
"""

from __future__ import annotations

import numpy as np
import pytest

from phids.engine.systems.interaction.movement import _weighted_field_choice_jit


@pytest.mark.jit_parity
def test_numba_jit_weighted_field_choice_zero_weight_fallback() -> None:
    """Verify that when all weights are equal, choice falls back safely using rand_val.

    Raises:
        AssertionError: If candidate selection crashes or fails to return center cell at rand_val=0.0.
    """
    scores = np.array([0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float64)
    cx = np.array([5, 5, 6, 5, 4], dtype=np.int32)
    cy = np.array([5, 6, 5, 4, 5], dtype=np.int32)
    adj_scores = np.zeros(5, dtype=np.float64)
    weights = np.zeros(5, dtype=np.float64)

    # rand_val = 0.0 selects first candidate (5, 5)
    tx, ty = _weighted_field_choice_jit(
        count=5,
        invert=False,
        scores=scores,
        c_x=cx,
        c_y=cy,
        adjusted_scores=adj_scores,
        weights=weights,
        rand_val=0.0,
    )
    assert (tx, ty) == (5, 5)
