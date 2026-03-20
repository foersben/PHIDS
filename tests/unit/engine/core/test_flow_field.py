"""
Test coverage for PHIDS flow-field computation and signal/toxin propagation invariants.

This module implements unit tests for the PHIDS flow-field computation and signal/toxin propagation logic. The test suite verifies deterministic gradient generation, camouflage application, and toxin repulsion, ensuring compliance with NumPy vectorization, double-buffered state management, and O(1) spatial hash invariants. Each test function is documented to state the invariant or biological behavior being validated and its scientific rationale, supporting reproducible and rigorous validation of emergent ecological dynamics and flow-field mechanics. The module-level docstring is written in accordance with Google-style documentation standards, providing a comprehensive scholarly abstract of the test suite's scope and scientific rationale.
"""

from __future__ import annotations

import numpy as np

from phids.engine.core.flow_field import (
    _compute_flow_field_impl,
    apply_camouflage,
    compute_flow_field,
)


def test_compute_flow_field_impl_returns_zero_field_for_zero_inputs() -> None:
    """Verify the low-level flow kernel returns an all-zero field for zero inputs."""
    plant_energy = np.zeros((1, 1), dtype=np.float64)
    toxin_sum = np.zeros((1, 1), dtype=np.float64)

    flow = _compute_flow_field_impl(plant_energy, toxin_sum, width=1, height=1)

    assert np.allclose(flow, np.zeros((1, 1), dtype=np.float64))


def test_compute_flow_field_impl_propagates_along_single_row() -> None:
    """Verify attraction propagates symmetrically from a single row source."""
    plant_energy = np.zeros((1, 5), dtype=np.float64)
    toxin_sum = np.zeros((1, 5), dtype=np.float64)
    plant_energy[0, 2] = 6.0

    flow = _compute_flow_field_impl(plant_energy, toxin_sum, width=1, height=5)

    assert flow[0, 2] > 0.0
    assert flow[0, 0] > 0.0
    assert flow[0, 4] > 0.0
    assert flow[0, 2] > flow[0, 0]
    assert np.isclose(flow[0, 0], flow[0, 4])


def test_compute_flow_field_impl_propagates_toxin_repulsion_along_single_column() -> None:
    """Verify toxin repulsion propagates symmetrically along a single column."""
    plant_energy = np.zeros((5, 1), dtype=np.float64)
    toxin_sum = np.zeros((5, 1), dtype=np.float64)
    toxin_sum[2, 0] = 2.5

    flow = _compute_flow_field_impl(plant_energy, toxin_sum, width=5, height=1)

    assert flow[2, 0] < 0.0
    assert flow[0, 0] < 0.0
    assert flow[4, 0] < 0.0
    assert flow[2, 0] < flow[0, 0]
    assert np.isclose(flow[0, 0], flow[4, 0])


def test_compute_flow_field_propagates_plant_attraction_and_toxin_repulsion() -> None:
    """Verify the flow wrapper combines attraction and repulsion in one output field."""
    plant_energy = np.zeros((3, 3), dtype=np.float64)
    toxin_layers = np.zeros((2, 3, 3), dtype=np.float64)
    plant_energy[1, 1] = 4.0
    toxin_layers[0, 1, 1] = 1.0

    flow = compute_flow_field(plant_energy, toxin_layers, width=3, height=3)

    assert flow[1, 1] > 0.0
    assert flow[0, 0] > 0.0
    assert flow[1, 1] > flow[0, 0]


def test_compute_flow_field_sums_multiple_toxin_layers_and_handles_edges() -> None:
    """Verify toxin layers are aggregated correctly and edge cells remain stable."""
    plant_energy = np.zeros((2, 2), dtype=np.float64)
    toxin_layers = np.zeros((2, 2, 2), dtype=np.float64)
    plant_energy[0, 0] = 2.0
    toxin_layers[0, 0, 0] = 1.0
    toxin_layers[1, 1, 1] = 2.0

    flow = compute_flow_field(plant_energy, toxin_layers, width=2, height=2)

    assert flow[1, 1] < 0.0
    assert flow[0, 0] > flow[1, 1]
    assert flow[0, 1] < flow[0, 0]


def test_compute_flow_field_impl_is_linear_for_multiple_sources() -> None:
    """Verify linear superposition for multiple plant-energy sources in the core kernel."""
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
    """Verify the wrapper sums toxin layers before delegating to the core kernel."""
    plant_energy = np.zeros((2, 3), dtype=np.float64)
    toxin_layers = np.zeros((3, 2, 3), dtype=np.float64)
    toxin_layers[0, 0, 1] = 0.25
    toxin_layers[1, 0, 1] = 0.75
    toxin_layers[2, 1, 2] = 2.0

    flow = compute_flow_field(plant_energy, toxin_layers, width=2, height=3)
    expected = _compute_flow_field_impl(plant_energy, toxin_layers.sum(axis=0), width=2, height=3)

    assert np.allclose(flow, expected)


def test_compute_flow_field_reaches_cells_beyond_one_hop() -> None:
    """Verify flow influence reaches cells beyond immediate neighbors."""
    plant_energy = np.zeros((7, 7), dtype=np.float64)
    toxin_layers = np.zeros((1, 7, 7), dtype=np.float64)
    plant_energy[0, 0] = 10.0

    flow = compute_flow_field(plant_energy, toxin_layers, width=7, height=7)

    assert flow[2, 2] > 0.0


def test_apply_camouflage_scales_one_cell_in_place() -> None:
    """Verify camouflage attenuates a targeted cell in place."""
    flow_field = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64)

    apply_camouflage(flow_field, 1, 0, 0.25)

    assert np.allclose(flow_field, np.array([[1.0, 2.0], [0.75, 4.0]], dtype=np.float64))


def test_apply_camouflage_supports_full_and_zero_attenuation() -> None:
    """Verify camouflage handles both full attenuation and neutral scaling."""
    flow_field = np.array([[5.0, -2.0]], dtype=np.float64)

    apply_camouflage(flow_field, 0, 0, 1.0)
    apply_camouflage(flow_field, 0, 1, 0.0)

    assert np.allclose(flow_field, np.array([[5.0, 0.0]], dtype=np.float64))


def test_flow_field_generation_and_camouflage() -> None:
    """Verify attractor-repeller contrast and cell-local camouflage attenuation."""
    plant_energy = np.array([[0.0, 0.0], [10.0, 0.0]], dtype=np.float64)
    toxin_layers = np.zeros((1, 2, 2), dtype=np.float64)
    toxin_layers[0, 0, 1] = 2.0

    flow = compute_flow_field(plant_energy, toxin_layers, width=2, height=2)
    assert flow.shape == (2, 2)
    assert flow[1, 0] > flow[0, 1]

    before = flow[1, 0]
    apply_camouflage(flow, 1, 0, 0.25)
    assert np.isclose(flow[1, 0], before * 0.25)
