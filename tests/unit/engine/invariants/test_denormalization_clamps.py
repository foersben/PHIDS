# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Denormalization clamp and floating-point subnormal protection unit tests."""

from __future__ import annotations

import numpy as np
import pytest

from phids.engine.core.flow_field import _compute_flow_field


@pytest.mark.scientific_invariant
def test_subnormal_float_denormalization_clamp_threshold() -> None:
    """Verify subnormal floating-point values (< 1e-4) are truncated to 0.0 to prevent FPU traps."""
    width, height = 10, 10

    # Create array populated with subnormal values below 1e-4 threshold
    plant_energy = np.full((width, height), 1e-6, dtype=np.float64)
    apparent_nutrition = np.ones((width, height), dtype=np.float64)
    toxin_layers = np.zeros((1, width, height), dtype=np.float64)

    base = np.zeros((width, height), dtype=np.float64)
    current = np.zeros((width, height), dtype=np.float64)
    nxt = np.zeros((width, height), dtype=np.float64)

    result = _compute_flow_field(
        plant_energy,
        apparent_nutrition,
        toxin_layers,
        width,
        height,
        base,
        current,
        nxt,
        1.0,
        1.0,
        0.5,
        1e-4,
    )

    # Subnormal inputs < 1e-4 must be truncated to exactly 0.0
    assert np.all(result == 0.0), "Values below truncate_threshold 1e-4 must be clamped to zero"
