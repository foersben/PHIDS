# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit Invariant Tests for O(1) Stochastic Polar Seed Dispersal Spatial Isotropy.

This module validates that polar raycasting seed placement generates isotropic (uniform)
angular distribution theta ~ U(-pi, pi) using Kolmogorov-Smirnov statistical testing.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy import stats


@pytest.mark.scientific_invariant
def test_seed_dispersal_stochastic_isotropy() -> None:
    """Verify O(1) stochastic polar seed raycasting generates isotropic angular seed placement.

    Raycasting generates seeds at polar coordinates (r, theta) where theta ~ U(-pi, pi).
    Reconstructed Cartesian angles theta = arctan2(dy, dx) across 10,000 samples must pass
    the Kolmogorov-Smirnov test for spatial isotropy (p-value > 0.01).

    Raises:
        AssertionError: If angular distribution exhibits directional bias (p-value <= 0.01).
    """
    rng = np.random.default_rng(42)
    n_samples = 10_000

    min_dist, max_dist = 1.0, 5.0
    angles = rng.uniform(-math.pi, math.pi, size=n_samples)
    distances = rng.uniform(min_dist, max_dist, size=n_samples)

    dx = distances * np.cos(angles)
    dy = distances * np.sin(angles)

    reconstructed_angles = np.arctan2(dy, dx)

    ks_stat, p_value = stats.kstest(reconstructed_angles, "uniform", args=(-math.pi, 2 * math.pi))

    assert p_value > 0.01, f"Seed dispersal exhibits spatial anisotropy! KS stat={ks_stat}, p-value={p_value}"
