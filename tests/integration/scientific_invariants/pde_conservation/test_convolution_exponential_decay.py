# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Scientific Invariant Tests for Biotope Diffusion Exponential Decay Law.

This module validates that Gaussian kernel convolution coupled with exponential decay rate
lambda matches the mathematical decay equation M(t) = M_0 (1 - lambda)^t.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from phids.engine.core.biotope import _numba_convolve_signal_layer


@given(
    decay=st.floats(min_value=0.5, max_value=1.0),
    multiplier=st.floats(min_value=1.0, max_value=100.0),
)
@pytest.mark.scientific_invariant
@pytest.mark.hypothesis_pilot
def test_convolution_exponential_decay_invariant(decay: float, multiplier: float) -> None:
    """Hypothesis test enforcing that normalized kernel convolution matches exponential decay.

    For a normalized Gaussian diffusion kernel (sum(K) = 1.0) and uniform initial concentration C,
    the post-convolution concentration must equal C * decay to floating-point precision.

    Args:
        decay: Decay multiplier (1.0 - evaporation_rate) in [0.5, 1.0].
        multiplier: Uniform initial concentration level in [1.0, 100.0].

    Raises:
        AssertionError: If output concentration deviates from C * decay.
    """
    width, height = 16, 16
    advected = np.full((width, height), multiplier, dtype=np.float64)

    # 3x3 normalized gaussian kernel (sum = 1.0)
    kernel = np.array([[0.0625, 0.125, 0.0625], [0.125, 0.25, 0.125], [0.0625, 0.125, 0.0625]], dtype=np.float64)
    write_buf = np.zeros((width, height), dtype=np.float64)

    _numba_convolve_signal_layer(
        width,
        height,
        decay=decay,
        epsilon=1e-12,
        kernel=kernel,
        write_buffer=write_buf,
        advected_scratch=advected,
    )

    expected_val = multiplier * decay
    np.testing.assert_allclose(write_buf, expected_val, rtol=1e-5, atol=1e-6)
