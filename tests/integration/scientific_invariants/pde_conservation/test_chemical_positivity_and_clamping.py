# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Scientific Invariant Tests for Chemical Positivity and Subnormal Float Clamping.

This module validates physical concentration non-negativity (c(x, y, t) >= 0.0)
and the explicit truncation of subnormal floating-point tails below SIGNAL_EPSILON
during reaction-diffusion PDE operations.
"""

from __future__ import annotations

import numpy as np
import pytest

from phids.engine.core.biotope import _numba_diffuse_signal_layer
from phids.shared.constants import SIGNAL_EPSILON


@pytest.mark.scientific_invariant
def test_chemical_positivity_invariant() -> None:
    """Verify chemical concentrations remain non-negative under advection-diffusion.

    Chemical concentrations represent non-negative physical quantities (moles/m^2).
    Combined advection and Gaussian convolution must maintain non-negativity everywhere
    for all x, y, t.

    Raises:
        AssertionError: If any cell concentration becomes negative (< 0.0).
    """
    width, height = 16, 16
    rng = np.random.default_rng(123)

    layer = rng.uniform(0.0, 50.0, size=(width, height)).astype(np.float64)
    wind_x = rng.uniform(-10.0, 10.0, size=(width, height)).astype(np.float64)
    wind_y = rng.uniform(-10.0, 10.0, size=(width, height)).astype(np.float64)
    kernel = np.array([[0.05, 0.1, 0.05], [0.1, 0.4, 0.1], [0.05, 0.1, 0.05]], dtype=np.float64)
    write_buf = np.zeros((width, height), dtype=np.float64)
    scratch = np.zeros((width, height), dtype=np.float64)

    _numba_diffuse_signal_layer(
        width,
        height,
        layer,
        wind_x,
        wind_y,
        decay=0.95,
        epsilon=SIGNAL_EPSILON,
        kernel=kernel,
        write_buffer=write_buf,
        advected_scratch=scratch,
    )

    assert np.all(write_buf >= 0.0), "Chemical concentration contained negative values!"


@pytest.mark.scientific_invariant
def test_subnormal_float_clamping_to_zero() -> None:
    """Verify concentration values below SIGNAL_EPSILON snap cleanly to 0.0.

    Subnormal floats incur severe CPU performance penalties in Numba JIT kernels.
    The diffusion kernel must explicitly zero-out concentrations falling below
    SIGNAL_EPSILON (1e-4) to maintain performance and eliminate residual signal tails.

    Raises:
        AssertionError: If concentrations below SIGNAL_EPSILON are not clamped to 0.0.
    """
    width, height = 8, 8
    layer = np.full((width, height), SIGNAL_EPSILON * 0.5, dtype=np.float64)
    wind_x = np.zeros((width, height), dtype=np.float64)
    wind_y = np.zeros((width, height), dtype=np.float64)
    kernel = np.array([[0.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 0.0]], dtype=np.float64)
    write_buf = np.zeros((width, height), dtype=np.float64)
    scratch = np.zeros((width, height), dtype=np.float64)

    _numba_diffuse_signal_layer(
        width,
        height,
        layer,
        wind_x,
        wind_y,
        decay=1.0,
        epsilon=SIGNAL_EPSILON,
        kernel=kernel,
        write_buffer=write_buf,
        advected_scratch=scratch,
    )

    assert np.all(write_buf == 0.0), "Subnormal floats were not clamped to 0.0!"
