# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for Boltzmann/Softmax stochastic action selection in movement."""

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from phids.engine.systems.interaction.movement import (
    _choose_neighbour_by_flow_probability_jit,
    _flat_field_choice_jit,
    _random_walk_step_jit,
    _softmax_field_choice_jit,
    _weighted_field_choice_jit,
)


@given(
    scores_list=st.lists(
        st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
        min_size=4,
        max_size=4,
    ),
    rand_val=st.floats(min_value=0.0, max_value=0.9999),
)
@settings(max_examples=100, deadline=None)
def test_softmax_field_choice_high_temperature(scores_list: list[float], rand_val: float) -> None:
    """Property test: At very high temperatures, distribution approaches uniform."""
    count = 4
    invert = False
    scores = np.array(scores_list, dtype=np.float64)
    c_x = np.array([0, 1, 2, 3], dtype=np.int32)
    c_y = np.array([0, 0, 0, 0], dtype=np.int32)
    adjusted_scores = np.zeros(4, dtype=np.float64)
    weights = np.zeros(4, dtype=np.float64)

    # We use a massive temperature to drown out the score differences
    tau = 1e9

    # Run the choice
    x, _y = _softmax_field_choice_jit(
        count,
        invert,
        scores,
        c_x,
        c_y,
        adjusted_scores,
        weights,
        rand_val,
        tau,
        tile_populations=None,
        width=0,
        max_capacity=500,
        current_x=-1,
        current_y=-1,
    )

    assert 0 <= x < 4


@given(
    scores_list=st.lists(
        st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
        min_size=4,
        max_size=4,
    ),
    rand_val=st.floats(min_value=0.0, max_value=0.9999),
)
@settings(max_examples=100, deadline=None)
def test_softmax_field_choice_low_temperature(scores_list: list[float], rand_val: float) -> None:
    """Property test: At very low temperatures, distribution approaches greedy argmax."""
    count = 4
    invert = False
    scores = np.array(scores_list, dtype=np.float64)
    # Ensure there is one distinct absolute maximum to test greedy choice
    scores[3] += 2000.0
    c_x = np.array([0, 1, 2, 3], dtype=np.int32)
    c_y = np.array([0, 0, 0, 0], dtype=np.int32)
    adjusted_scores = np.zeros(4, dtype=np.float64)
    weights = np.zeros(4, dtype=np.float64)

    tau = 0.0001

    x, _y = _softmax_field_choice_jit(
        count,
        invert,
        scores,
        c_x,
        c_y,
        adjusted_scores,
        weights,
        rand_val,
        tau,
        tile_populations=None,
        width=0,
        max_capacity=500,
        current_x=-1,
        current_y=-1,
    )

    assert x == 3


def test_softmax_field_choice_jit_parity() -> None:
    """Numba JIT vs Python pure reference equivalence checks."""
    count = 4
    scores = np.array([10.0, 20.0, 30.0, 40.0], dtype=np.float64)
    c_x = np.array([0, 1, 2, 3], dtype=np.int32)
    c_y = np.array([0, 0, 0, 0], dtype=np.int32)

    tau = 1.0
    rand_val = 0.5

    x_jit, y_jit = _softmax_field_choice_jit(
        count,
        False,
        scores,
        c_x,
        c_y,
        np.zeros(4, dtype=np.float64),
        np.zeros(4, dtype=np.float64),
        rand_val,
        tau,
        None,
        0,
        500,
        -1,
        -1,
    )

    x_py, y_py = _softmax_field_choice_jit(
        count,
        False,
        scores,
        c_x,
        c_y,
        np.zeros(4, dtype=np.float64),
        np.zeros(4, dtype=np.float64),
        rand_val,
        tau,
        None,
        0,
        500,
        -1,
        -1,
    )

    assert x_jit == x_py
    assert y_jit == y_py


def test_flat_field_choice_jit_parity() -> None:
    """Numba JIT vs Python pure reference equivalence checks for flat selection."""
    count = 4
    c_x = np.array([0, 1, 2, 3], dtype=np.int32)
    c_y = np.array([0, 0, 0, 0], dtype=np.int32)

    rand_val = 0.5

    x_jit, y_jit = _flat_field_choice_jit(count, 0, 0, 0, 0, c_x, c_y, np.zeros(4, dtype=np.float64), rand_val)

    x_py, y_py = getattr(_flat_field_choice_jit, "py_func", _flat_field_choice_jit)(
        count, 0, 0, 0, 0, c_x, c_y, np.zeros(4, dtype=np.float64), rand_val
    )

    assert x_jit == x_py
    assert y_jit == y_py


def test_weighted_field_choice_jit_parity() -> None:
    """Numba JIT vs Python pure reference equivalence checks for weighted selection."""
    count = 4
    scores = np.array([10.0, 20.0, 30.0, 40.0], dtype=np.float64)
    c_x = np.array([0, 1, 2, 3], dtype=np.int32)
    c_y = np.array([0, 0, 0, 0], dtype=np.int32)

    rand_val = 0.5

    x_jit, y_jit = _weighted_field_choice_jit(
        count,
        False,
        scores,
        c_x,
        c_y,
        np.zeros(4, dtype=np.float64),
        np.zeros(4, dtype=np.float64),
        rand_val,
        None,
        0,
        500,
        -1,
        -1,
    )

    x_py, y_py = getattr(_weighted_field_choice_jit, "py_func", _weighted_field_choice_jit)(
        count,
        False,
        scores,
        c_x,
        c_y,
        np.zeros(4, dtype=np.float64),
        np.zeros(4, dtype=np.float64),
        rand_val,
        None,
        0,
        500,
        -1,
        -1,
    )

    assert x_jit == x_py
    assert y_jit == y_py


def test_choose_neighbour_by_flow_probability_jit_parity() -> None:
    """Numba JIT vs Python pure reference equivalence checks for overarching dispatch."""
    flow_field = np.zeros((10, 10), dtype=np.float64)
    flow_field[1, 0] = 5.0
    flow_field[0, 1] = 10.0

    c_x = np.zeros(5, dtype=np.int32)
    c_y = np.zeros(5, dtype=np.int32)

    x_jit, y_jit = _choose_neighbour_by_flow_probability_jit(
        0,
        0,
        0,
        0,
        flow_field,
        10,
        10,
        False,
        c_x,
        c_y,
        np.zeros(5, dtype=np.float64),
        np.zeros(5, dtype=np.float64),
        np.zeros(5, dtype=np.float64),
        0.5,
        None,
        1.0,
    )

    x_py, y_py = getattr(
        _choose_neighbour_by_flow_probability_jit, "py_func", _choose_neighbour_by_flow_probability_jit
    )(
        0,
        0,
        0,
        0,
        flow_field,
        10,
        10,
        False,
        c_x,
        c_y,
        np.zeros(5, dtype=np.float64),
        np.zeros(5, dtype=np.float64),
        np.zeros(5, dtype=np.float64),
        0.5,
        None,
        1.0,
    )

    assert x_jit == x_py
    assert y_jit == y_py


def test_random_walk_step_jit_parity() -> None:
    """Numba JIT vs Python pure reference equivalence checks for random walk step."""
    c_x = np.zeros(5, dtype=np.int32)
    c_y = np.zeros(5, dtype=np.int32)

    x_jit, y_jit = _random_walk_step_jit(0, 0, 10, 10, c_x, c_y, 0.5)

    x_py, y_py = getattr(_random_walk_step_jit, "py_func", _random_walk_step_jit)(0, 0, 10, 10, c_x, c_y, 0.5)

    assert x_jit == x_py
    assert y_jit == y_py
