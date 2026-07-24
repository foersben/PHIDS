# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Focused mutation-pilot regressions for flow-field branch and arithmetic semantics."""

from __future__ import annotations

import numpy as np
import pytest

from phids.engine.core.flow_field import _compute_flow_field_impl, compute_flow_field


def _compute_flow_field_impl_test(plant_energy, apparent_nutrition_layer, toxin_layers, width, height):
    """Helper for Flow Field tests.

    Args:
        plant_energy: Array of plant energy per cell.
        apparent_nutrition_layer: Array of apparent nutrition multipliers per cell.
        toxin_layers: Array of toxin concentration layers per cell.
        width: The width of the grid environment.
        height: The height of the grid environment.

    Returns:
        Flow-field gradient of shape ``(W, H)``.
    """
    import numpy as np

    return _compute_flow_field_impl(
        plant_energy,
        apparent_nutrition_layer,
        toxin_layers,
        width,
        height,
        np.zeros((width, height), dtype=np.float64),
        np.zeros((width, height), dtype=np.float64),
        np.zeros((width, height), dtype=np.float64),
        1.0,
        1.0,
        0.6,
        1e-4,
    )


def test_subnormal_clipping_is_strictly_less_than_boundary() -> None:
    """Values below 1e-4 clip to zero, while exactly 1e-4 remains non-zero."""
    toxin_sum = np.zeros((1, 1, 1), dtype=np.float64)

    at_boundary = _compute_flow_field_impl_test(
        np.array([[1e-4]], dtype=np.float64),
        np.array([[1.0]], dtype=np.float64),
        toxin_sum,
        width=1,
        height=1,
    )
    below_boundary = _compute_flow_field_impl_test(
        np.array([[9.9e-5]], dtype=np.float64),
        np.array([[1.0]], dtype=np.float64),
        toxin_sum,
        width=1,
        height=1,
    )

    assert at_boundary[0, 0] == pytest.approx(1e-4)
    assert below_boundary[0, 0] == 0.0


def test_base_term_sign_is_plant_minus_toxin() -> None:
    """Single-cell polarity remains attraction minus repulsion and does not invert sign."""
    attractive = _compute_flow_field_impl_test(
        np.array([[3.0]], dtype=np.float64),
        np.array([[1.0]], dtype=np.float64),
        np.array([[[1.0]]], dtype=np.float64),
        width=1,
        height=1,
    )
    repulsive = _compute_flow_field_impl_test(
        np.array([[1.0]], dtype=np.float64),
        np.array([[1.0]], dtype=np.float64),
        np.array([[[3.0]]], dtype=np.float64),
        width=1,
        height=1,
    )

    assert attractive[0, 0] > 0.0
    assert repulsive[0, 0] < 0.0


def test_wrapper_aggregates_all_toxin_layers_by_sum() -> None:
    """Wrapper behavior equals kernel invocation on explicit toxin-layer sums."""
    plant_energy = np.zeros((2, 2), dtype=np.float64)
    toxin_layers = np.zeros((3, 2, 2), dtype=np.float64)
    toxin_layers[0, 0, 0] = 0.5
    toxin_layers[1, 0, 0] = 1.0
    toxin_layers[2, 1, 1] = 2.5

    wrapped = compute_flow_field(plant_energy, np.ones((2, 2)), toxin_layers, width=2, height=2)
    explicit = _compute_flow_field_impl_test(plant_energy, np.ones((2, 2)), toxin_layers, width=2, height=2)

    assert np.allclose(wrapped, explicit)


def test_diffusion_reaches_cells_beyond_immediate_neighbors() -> None:
    """Iterative propagation reaches multi-hop cells, guarding against one-pass mutants."""
    plant_energy = np.zeros((7, 7), dtype=np.float64)
    toxin_layers = np.zeros((1, 7, 7), dtype=np.float64)
    plant_energy[0, 0] = 12.0

    flow = compute_flow_field(plant_energy, np.ones((7, 7)), toxin_layers, width=7, height=7)

    assert flow[2, 2] > 0.0


def test_compute_flow_field_defaults() -> None:
    """Verify that default keyword arguments such as alpha and decay are strictly respected.

    This kills mutmut survivors that change alpha=1.0 to 2.0 or default arrays to None.
    """
    plant_energy = np.ones((1, 1), dtype=np.float64)
    apparent_nutrition_layer = np.ones((1, 1), dtype=np.float64)
    toxin_layers = np.zeros((1, 1, 1), dtype=np.float64)

    # Run with absolutely no kwargs
    result_default = compute_flow_field(plant_energy, apparent_nutrition_layer, toxin_layers, 1, 1)

    # Since alpha=1.0, beta=1.0, the calculation for a 1x1 with 1.0 plant and 0.0 toxin
    # should be exactly 1.0 * (1.0 - 0.0) = 1.0
    assert result_default[0, 0] == 1.0

    # And verify the strict float64 dtype requirement
    assert result_default.dtype == np.float64
