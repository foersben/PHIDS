# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Toroidal geometry and topological invariant property-based unit tests."""

from __future__ import annotations

import hypothesis.strategies as st
import pytest
from hypothesis import given

from phids.engine.core.ecs import ECSWorld


@given(
    x=st.integers(min_value=-10000, max_value=10000),
    y=st.integers(min_value=-10000, max_value=10000),
    width=st.sampled_from([16, 32, 64, 128, 256, 1024]),
    height=st.sampled_from([16, 32, 64, 128, 256, 1024]),
)
@pytest.mark.scientific_invariant
def test_toroidal_coordinate_wrapping_bounds(x: int, y: int, width: int, height: int) -> None:
    """Assert toroidal coordinate wrapping produces bounds strictly within grid dimensions."""
    wrapped_x = x % width
    wrapped_y = y % height

    assert 0 <= wrapped_x < width
    assert 0 <= wrapped_y < height

    # For power-of-two width/height, bitwise AND produces identical wrapping
    if (width & (width - 1)) == 0:
        assert (x & (width - 1)) == wrapped_x
    if (height & (height - 1)) == 0:
        assert (y & (height - 1)) == wrapped_y


@given(
    x1=st.integers(min_value=0, max_value=1023),
    x2=st.integers(min_value=0, max_value=1023),
    width=st.just(1024),
)
@pytest.mark.scientific_invariant
def test_toroidal_distance_symmetry_and_bounds(x1: int, x2: int, width: int) -> None:
    """Assert toroidal periodic distance is symmetric and bounded by width / 2."""
    dx = abs(x1 - x2)
    toroidal_dx = min(dx, width - dx)

    # Symmetry
    dx_reverse = abs(x2 - x1)
    toroidal_dx_reverse = min(dx_reverse, width - dx_reverse)

    assert toroidal_dx == toroidal_dx_reverse
    assert 0 <= toroidal_dx <= width // 2


@given(
    x=st.integers(min_value=-500, max_value=500),
    y=st.integers(min_value=-500, max_value=500),
)
@pytest.mark.scientific_invariant
def test_ecs_spatial_hash_toroidal_registration(x: int, y: int) -> None:
    """Assert ECS spatial hash registers entities cleanly under arbitrary toroidal coordinates."""
    world = ECSWorld()
    eid = world.create_entity()

    width, height = 32, 32
    wrapped_x = x % width
    wrapped_y = y % height

    world.register_position(eid.entity_id, wrapped_x, wrapped_y)
    entities = world.entities_at(wrapped_x, wrapped_y)

    assert eid.entity_id in entities
