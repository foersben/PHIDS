# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Scientific Invariant Tests for Monotone Hill Kinetics Response.

This module validates that Hill equation kinetics S(c) = c^n / (K^n + c^n) exhibit strict monotonicity
S(c1) <= S(c2) for all non-negative chemical concentrations c1 <= c2.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st


@given(
    c1=st.floats(min_value=0.0, max_value=100.0),
    c2=st.floats(min_value=0.0, max_value=100.0),
    k=st.floats(min_value=0.1, max_value=10.0),
    n=st.floats(min_value=1.0, max_value=4.0),
)
@pytest.mark.scientific_invariant
@pytest.mark.hypothesis_pilot
def test_hill_kinetics_monotonicity(c1: float, c2: float, k: float, n: float) -> None:
    """Hypothesis test verifying monotone Hill response S(c1) <= S(c2) under S(c) = c^n / (K^n + c^n).

    Args:
        c1: First chemical concentration in [0.0, 100.0].
        c2: Second chemical concentration in [0.0, 100.0].
        k: Half-saturation constant K in [0.1, 10.0].
        n: Hill cooperativity coefficient n in [1.0, 4.0].

    Raises:
        AssertionError: If S(c1) > S(c2) when c1 <= c2 or if S(c) falls outside [0.0, 1.0].
    """
    low_c, high_c = min(c1, c2), max(c1, c2)

    s_low = (low_c**n) / (k**n + low_c**n)
    s_high = (high_c**n) / (k**n + high_c**n)

    assert s_low <= s_high + 1e-12
    assert 0.0 <= s_low <= 1.0
    assert 0.0 <= s_high <= 1.0
