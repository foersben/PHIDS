# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for Boltzmann/Softmax stochastic action selection in movement."""

import numpy as np

from phids.engine.systems.interaction.movement import _softmax_field_choice_jit


def test_softmax_field_choice_high_temperature():
    """Property test: At very high temperatures, distribution approaches uniform."""
    count = 4
    invert = False
    scores = np.array([10.0, 20.0, 30.0, 40.0], dtype=np.float64)
    c_x = np.array([0, 1, 2, 3], dtype=np.int32)
    c_y = np.array([0, 0, 0, 0], dtype=np.int32)
    adjusted_scores = np.zeros(4, dtype=np.float64)
    weights = np.zeros(4, dtype=np.float64)
    tau = 1000.0  # Extremely high temperature

    # Run 10000 trials
    choices = {0: 0, 1: 0, 2: 0, 3: 0}
    np.random.seed(42)
    for _ in range(10000):
        rand_val = float(np.random.random())
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
        choices[x] += 1

    # With tau=1000, e^(10/1000) ~ e^(40/1000) ~ 1.0. All bins should get ~2500 hits.
    for val in choices.values():
        assert 2200 < val < 2800, f"Distribution is skewed: {choices}"


def test_softmax_field_choice_low_temperature():
    """Property test: At very low temperatures, distribution approaches greedy argmax."""
    count = 4
    invert = False
    scores = np.array([10.0, 20.0, 30.0, 40.0], dtype=np.float64)
    c_x = np.array([0, 1, 2, 3], dtype=np.int32)
    c_y = np.array([0, 0, 0, 0], dtype=np.int32)
    adjusted_scores = np.zeros(4, dtype=np.float64)
    weights = np.zeros(4, dtype=np.float64)
    tau = 0.01  # Extremely low temperature

    choices = {0: 0, 1: 0, 2: 0, 3: 0}
    np.random.seed(42)
    for _ in range(1000):
        rand_val = float(np.random.random())
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
        choices[x] += 1

    # The max score (40.0, idx=3) should be chosen almost 100% of the time.
    assert choices[3] == 1000, f"Greedy choice failed at low temp: {choices}"
