from __future__ import annotations

import numpy as np

from phids.engine.core.flow_field import (
    _compute_flow_field_impl,
    apply_camouflage,
    compute_flow_field,
)


def test_compute_flow_field_impl_returns_zero_field_for_zero_inputs() -> None:
    plant_energy = np.zeros((1, 1), dtype=np.float64)
    toxin_sum = np.zeros((1, 1), dtype=np.float64)

    flow = _compute_flow_field_impl(plant_energy, toxin_sum, width=1, height=1)

    assert np.allclose(flow, np.zeros((1, 1), dtype=np.float64))


def test_compute_flow_field_impl_propagates_along_single_row() -> None:
    plant_energy = np.zeros((1, 3), dtype=np.float64)
    toxin_sum = np.zeros((1, 3), dtype=np.float64)
    plant_energy[0, 1] = 6.0

    flow = _compute_flow_field_impl(plant_energy, toxin_sum, width=1, height=3)

    expected = np.array([[3.0, 6.0, 3.0]], dtype=np.float64)
    assert np.allclose(flow, expected)


def test_compute_flow_field_impl_propagates_toxin_repulsion_along_single_column() -> None:
    plant_energy = np.zeros((3, 1), dtype=np.float64)
    toxin_sum = np.zeros((3, 1), dtype=np.float64)
    toxin_sum[1, 0] = 2.5

    flow = _compute_flow_field_impl(plant_energy, toxin_sum, width=3, height=1)

    expected = np.array([[-1.25], [-2.5], [-1.25]], dtype=np.float64)
    assert np.allclose(flow, expected)


def test_compute_flow_field_propagates_plant_attraction_and_toxin_repulsion() -> None:
    plant_energy = np.zeros((3, 3), dtype=np.float64)
    toxin_layers = np.zeros((2, 3, 3), dtype=np.float64)
    plant_energy[1, 1] = 4.0
    toxin_layers[0, 1, 1] = 1.0

    flow = compute_flow_field(plant_energy, toxin_layers, width=3, height=3)

    expected = np.zeros((3, 3), dtype=np.float64)
    expected[1, 1] = 3.0
    expected[0, 1] = 1.5
    expected[2, 1] = 1.5
    expected[1, 0] = 1.5
    expected[1, 2] = 1.5
    assert np.allclose(flow, expected)


def test_compute_flow_field_sums_multiple_toxin_layers_and_handles_edges() -> None:
    plant_energy = np.zeros((2, 2), dtype=np.float64)
    toxin_layers = np.zeros((2, 2, 2), dtype=np.float64)
    plant_energy[0, 0] = 2.0
    toxin_layers[0, 0, 0] = 1.0
    toxin_layers[1, 1, 1] = 2.0

    flow = compute_flow_field(plant_energy, toxin_layers, width=2, height=2)

    expected = np.array(
        [
            [1.0, -0.5],
            [-0.5, -2.0],
        ],
        dtype=np.float64,
    )
    assert np.allclose(flow, expected)


def test_compute_flow_field_impl_is_linear_for_multiple_sources() -> None:
    shape = (3, 3)
    zero_toxins = np.zeros(shape, dtype=np.float64)

    plant_a = np.zeros(shape, dtype=np.float64)
    plant_a[0, 1] = 4.0
    plant_b = np.zeros(shape, dtype=np.float64)
    plant_b[2, 1] = 2.0

    combined = _compute_flow_field_impl(plant_a + plant_b, zero_toxins, width=3, height=3)
    separate_sum = _compute_flow_field_impl(
        plant_a, zero_toxins, width=3, height=3
    ) + _compute_flow_field_impl(
        plant_b,
        zero_toxins,
        width=3,
        height=3,
    )

    assert np.allclose(combined, separate_sum)


def test_compute_flow_field_wrapper_sums_toxin_layers_before_propagation() -> None:
    plant_energy = np.zeros((2, 3), dtype=np.float64)
    toxin_layers = np.zeros((3, 2, 3), dtype=np.float64)
    toxin_layers[0, 0, 1] = 0.25
    toxin_layers[1, 0, 1] = 0.75
    toxin_layers[2, 1, 2] = 2.0

    flow = compute_flow_field(plant_energy, toxin_layers, width=2, height=3)
    expected = _compute_flow_field_impl(plant_energy, toxin_layers.sum(axis=0), width=2, height=3)

    assert np.allclose(flow, expected)


def test_apply_camouflage_scales_one_cell_in_place() -> None:
    flow_field = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64)

    apply_camouflage(flow_field, 1, 0, 0.25)

    assert np.allclose(flow_field, np.array([[1.0, 2.0], [0.75, 4.0]], dtype=np.float64))


def test_apply_camouflage_supports_full_and_zero_attenuation() -> None:
    flow_field = np.array([[5.0, -2.0]], dtype=np.float64)

    apply_camouflage(flow_field, 0, 0, 1.0)
    apply_camouflage(flow_field, 0, 1, 0.0)

    assert np.allclose(flow_field, np.array([[5.0, 0.0]], dtype=np.float64))
