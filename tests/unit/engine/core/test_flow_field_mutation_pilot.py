"""Focused mutation-pilot regressions for flow-field branch and arithmetic semantics."""

from __future__ import annotations

import numpy as np
import pytest

from phids.engine.core.flow_field import _compute_flow_field_impl, compute_flow_field


def test_subnormal_clipping_is_strictly_less_than_boundary() -> None:
    """Values below 1e-4 clip to zero, while exactly 1e-4 remains non-zero."""
    toxin_sum = np.zeros((1, 1), dtype=np.float64)

    at_boundary = _compute_flow_field_impl(
        np.array([[1e-4]], dtype=np.float64),
        toxin_sum,
        width=1,
        height=1,
    )
    below_boundary = _compute_flow_field_impl(
        np.array([[9.9e-5]], dtype=np.float64),
        toxin_sum,
        width=1,
        height=1,
    )

    assert at_boundary[0, 0] == pytest.approx(1e-4)
    assert below_boundary[0, 0] == 0.0


def test_base_term_sign_is_plant_minus_toxin() -> None:
    """Single-cell polarity remains attraction minus repulsion and does not invert sign."""
    attractive = _compute_flow_field_impl(
        np.array([[3.0]], dtype=np.float64),
        np.array([[1.0]], dtype=np.float64),
        width=1,
        height=1,
    )
    repulsive = _compute_flow_field_impl(
        np.array([[1.0]], dtype=np.float64),
        np.array([[3.0]], dtype=np.float64),
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

    wrapped = compute_flow_field(plant_energy, toxin_layers, width=2, height=2)
    explicit = _compute_flow_field_impl(plant_energy, toxin_layers.sum(axis=0), width=2, height=2)

    assert np.allclose(wrapped, explicit)


def test_diffusion_reaches_cells_beyond_immediate_neighbors() -> None:
    """Iterative propagation reaches multi-hop cells, guarding against one-pass mutants."""
    plant_energy = np.zeros((7, 7), dtype=np.float64)
    toxin_layers = np.zeros((1, 7, 7), dtype=np.float64)
    plant_energy[0, 0] = 12.0

    flow = compute_flow_field(plant_energy, toxin_layers, width=7, height=7)

    assert flow[2, 2] > 0.0
