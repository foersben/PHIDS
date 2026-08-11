# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Numba JIT vs Python pure reference floating-point equivalence unit tests."""

from __future__ import annotations

import numpy as np
import pytest

from phids.engine.core.flow_field import _compute_flow_field


def _py_compute_flow_field(
    plant_energy: np.ndarray,
    apparent_nutrition: np.ndarray,
    toxin_layers: np.ndarray,
    width: int,
    height: int,
    alpha: float,
    beta: float,
) -> np.ndarray:
    """Pure Python reference implementation of flow-field potential calculation."""
    num_toxins = toxin_layers.shape[0]
    result = np.zeros((width, height), dtype=np.float64)
    for x in range(width):
        for y in range(height):
            food_val = plant_energy[x, y] * apparent_nutrition[x, y]
            toxin_val = 0.0
            for k in range(num_toxins):
                toxin_val += toxin_layers[k, x, y]
            result[x, y] = alpha * food_val - beta * toxin_val
    return result


@pytest.mark.jit_parity
def test_flow_field_numba_jit_parity_with_python_reference() -> None:
    """Assert Numba JIT flow-field potential matches pure Python implementation within float tolerance."""
    width, height = 16, 16
    np.random.seed(42)

    plant_energy = np.random.uniform(0.0, 100.0, (width, height)).astype(np.float64)
    apparent_nutrition = np.random.uniform(0.5, 1.5, (width, height)).astype(np.float64)
    toxin_layers = np.random.uniform(0.0, 10.0, (2, width, height)).astype(np.float64)

    base = np.zeros((width, height), dtype=np.float64)
    current = np.zeros((width, height), dtype=np.float64)
    nxt = np.zeros((width, height), dtype=np.float64)

    alpha, beta = 1.2, 0.8

    # Run JIT implementation with zero decay to compare base potential calculation
    jit_result = _compute_flow_field(
        plant_energy,
        apparent_nutrition,
        toxin_layers,
        width,
        height,
        base,
        current,
        nxt,
        alpha,
        beta,
        0.0,
        1e-4,
    )

    # Run Pure Python implementation
    py_result = _py_compute_flow_field(plant_energy, apparent_nutrition, toxin_layers, width, height, alpha, beta)

    # Assert parity within floating point epsilon
    np.testing.assert_allclose(jit_result, py_result, rtol=1e-5, atol=1e-5)
