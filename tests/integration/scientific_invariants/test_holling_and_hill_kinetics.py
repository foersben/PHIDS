# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Holling Type II saturating response and Sigmoidal Hill kinetics property-based tests."""

from __future__ import annotations

import hypothesis.strategies as st
import pytest
from hypothesis import given


def holling_type_ii_intake(energy: float, search_rate: float, handling_time: float) -> float:
    """Holling Type II saturating functional intake response function."""
    if energy <= 0.0:
        return 0.0
    denom = 1.0 + search_rate * handling_time * energy
    return (search_rate * energy) / denom if denom > 0.0 else 0.0


def sigmoidal_hill_priming(concentration: float, half_max_k: float, hill_n: float) -> float:
    """Sigmoidal Hill kinetics continuous dose-response priming function."""
    if concentration <= 0.0:
        return 0.0
    c_n = concentration**hill_n
    k_n = half_max_k**hill_n
    denom = k_n + c_n
    return c_n / denom if denom > 0.0 else 0.0


@given(
    e1=st.floats(min_value=0.0, max_value=1e4, allow_nan=False, allow_infinity=False),
    e2=st.floats(min_value=0.0, max_value=1e4, allow_nan=False, allow_infinity=False),
    search_rate=st.floats(min_value=0.01, max_value=10.0, allow_nan=False, allow_infinity=False),
    handling_time=st.floats(min_value=0.01, max_value=5.0, allow_nan=False, allow_infinity=False),
)
@pytest.mark.scientific_invariant
def test_holling_type_ii_monotonicity_and_asymptote_invariants(
    e1: float, e2: float, search_rate: float, handling_time: float
) -> None:
    """Assert Holling Type II intake is monotonic with plant energy and bounded by 1 / handling_time."""
    min_e, max_e = min(e1, e2), max(e1, e2)
    intake_min = holling_type_ii_intake(min_e, search_rate, handling_time)
    intake_max = holling_type_ii_intake(max_e, search_rate, handling_time)

    # Monotonicity
    assert intake_min <= intake_max + 1e-9

    # Asymptotic ceiling limit
    max_intake_ceiling = 1.0 / handling_time
    assert intake_max <= max_intake_ceiling + 1e-9


@given(
    c1=st.floats(min_value=0.0, max_value=1e3, allow_nan=False, allow_infinity=False),
    c2=st.floats(min_value=0.0, max_value=1e3, allow_nan=False, allow_infinity=False),
    k=st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False),
    n=st.floats(min_value=1.0, max_value=4.0, allow_nan=False, allow_infinity=False),
)
@pytest.mark.scientific_invariant
def test_sigmoidal_hill_kinetics_boundedness_and_monotonicity(c1: float, c2: float, k: float, n: float) -> None:
    """Assert Sigmoidal Hill kinetics priming is bounded in [0, 1] and monotonic."""
    min_c, max_c = min(c1, c2), max(c1, c2)
    s_min = sigmoidal_hill_priming(min_c, k, n)
    s_max = sigmoidal_hill_priming(max_c, k, n)

    # Monotonicity
    assert s_min <= s_max + 1e-9

    # Bounds [0, 1]
    assert 0.0 <= s_min <= 1.0
    assert 0.0 <= s_max <= 1.0

    # Half-activation property
    s_at_k = sigmoidal_hill_priming(k, k, n)
    assert abs(s_at_k - 0.5) < 1e-6
