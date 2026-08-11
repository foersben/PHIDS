# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Scientific Invariant Tests for Holling Type II Functional Response Bounds.

This module validates that Holling Type II intake per individual I(N) = (a * N) / (1 + a * T_h * N)
is strictly upper-bounded by the theoretical handling time saturation ceiling 1 / T_h as N -> infinity.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st


@given(
    plant_energy=st.floats(min_value=1e3, max_value=1e8),
    handling_time=st.floats(min_value=0.01, max_value=10.0),
    raw_rate=st.floats(min_value=1.0, max_value=50.0),
)
@pytest.mark.scientific_invariant
@pytest.mark.hypothesis_pilot
def test_holling_type_ii_asymptotic_upper_bound(plant_energy: float, handling_time: float, raw_rate: float) -> None:
    """Hypothesis test verifying Holling Type II intake never exceeds ceiling (1 / handling_time).

    Args:
        plant_energy: Plant target energy reserve N in [1e3, 1e8].
        handling_time: Herbivore handling time per unit biomass T_h in [0.01, 10.0].
        raw_rate: Raw per-individual consumption rate a in [1.0, 50.0].

    Raises:
        AssertionError: If intake exceeds the theoretical upper bound 1 / T_h.
    """
    # Holling Type II formula: I(N) = (a * N) / (1 + a * Th * N)
    potential_per_ind = (raw_rate * plant_energy) / (1.0 + raw_rate * handling_time * plant_energy)

    max_theoretical_intake = 1.0 / handling_time
    assert potential_per_ind <= max_theoretical_intake + 1e-9


@pytest.mark.scientific_invariant
def test_holling_type_ii_zero_plant_energy_safety() -> None:
    """Verify Holling Type II intake is strictly 0.0 when plant energy N = 0.

    Raises:
        AssertionError: If intake is non-zero when target plant energy is zero.
    """
    plant_energy = 0.0
    handling_time = 0.5
    raw_rate = 10.0

    potential_per_ind = (raw_rate * plant_energy) / (1.0 + raw_rate * handling_time * plant_energy)
    assert potential_per_ind == 0.0
