# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Phloem translocation kinetics stability and convergence unit tests."""

from __future__ import annotations

import hypothesis.strategies as st
import pytest
from hypothesis import given


def phloem_translocation_step(n_current: float, n_target: float, k_rate: float) -> float:
    """First-order exponential relaxation step for phloem carbohydrate translocation."""
    return n_current - k_rate * (n_current - n_target)


@given(
    n_initial=st.floats(min_value=0.0, max_value=200.0, allow_nan=False, allow_infinity=False),
    n_target=st.floats(min_value=0.0, max_value=200.0, allow_nan=False, allow_infinity=False),
    k_rate=st.floats(min_value=0.01, max_value=0.5, allow_nan=False, allow_infinity=False),
    steps=st.integers(min_value=5, max_value=50),
)
@pytest.mark.scientific_invariant
def test_phloem_translocation_monotonic_convergence(
    n_initial: float, n_target: float, k_rate: float, steps: int
) -> None:
    """Assert phloem translocation relaxation converges monotonically without overshoot."""
    current = n_initial
    min_bound = min(n_initial, n_target)
    max_bound = max(n_initial, n_target)

    for _ in range(steps):
        next_n = phloem_translocation_step(current, n_target, k_rate)

        # Bounds invariant
        assert min_bound - 1e-9 <= next_n <= max_bound + 1e-9

        # Monotonic convergence invariant
        dist_before = abs(current - n_target)
        dist_after = abs(next_n - n_target)
        assert dist_after <= dist_before + 1e-9

        current = next_n
