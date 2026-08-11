# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Scientific Invariant Tests for Biotope Semi-Lagrangian Advection Mass Conservation.

This module validates that Bilinear Semi-Lagrangian advection under uniform wind fields
(zero spatial velocity divergence, div(v) = 0) strictly conserves total chemical mass
M = sum c(x, y) to within machine precision tolerance. It also validates that numerical
mass drift under spatially varying divergent wind fields remains strictly bounded (< 2%).
"""

from __future__ import annotations

import numpy as np
import pytest

from phids.engine.core.biotope import _numba_advect_signal_layer


@pytest.mark.scientific_invariant
def test_advection_uniform_wind_mass_conservation() -> None:
    """Verify Semi-Lagrangian advection mass conservation under uniform wind.

    Under a constant uniform wind vector v = (v_x, v_y), the velocity field has zero
    spatial divergence (div(v) = 0). Bilinear Semi-Lagrangian interpolation in a toroidal
    domain must conserve total chemical mass M = sum c(x, y) to machine precision.

    Raises:
        AssertionError: If total chemical mass after advection differs from initial mass.
    """
    width, height = 32, 32
    rng = np.random.default_rng(42)

    layer = rng.uniform(0.0, 100.0, size=(width, height)).astype(np.float64)
    wind_x = np.full((width, height), 2.5, dtype=np.float64)
    wind_y = np.full((width, height), -1.8, dtype=np.float64)
    scratch = np.zeros((width, height), dtype=np.float64)

    initial_mass = float(np.sum(layer))

    _numba_advect_signal_layer(width, height, layer, wind_x, wind_y, scratch)

    advected_mass = float(np.sum(scratch))

    np.testing.assert_allclose(advected_mass, initial_mass, rtol=1e-5, atol=1e-5)


@pytest.mark.scientific_invariant
def test_advection_divergent_wind_mass_bounded_drift() -> None:
    """Verify bounded mass drift under spatially varying divergent wind fields.

    Spatially varying wind vectors introduce non-zero velocity divergence (div(v) != 0).
    While discrete backward interpolation in divergent fields is not strictly mass-conservative,
    the numerical volume expansion/compression error must remain strictly bounded (< 2.0%).

    Raises:
        AssertionError: If numerical mass drift exceeds the 2.0% divergence error bound.
    """
    width, height = 32, 32
    rng = np.random.default_rng(42)

    layer = rng.uniform(0.0, 100.0, size=(width, height)).astype(np.float64)
    wind_x = rng.uniform(-5.0, 5.0, size=(width, height)).astype(np.float64)
    wind_y = rng.uniform(-5.0, 5.0, size=(width, height)).astype(np.float64)
    scratch = np.zeros((width, height), dtype=np.float64)

    initial_mass = float(np.sum(layer))

    _numba_advect_signal_layer(width, height, layer, wind_x, wind_y, scratch)

    advected_mass = float(np.sum(scratch))

    np.testing.assert_allclose(advected_mass, initial_mass, rtol=2e-2)
