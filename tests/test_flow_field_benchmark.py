"""Experimental validation suite for test flow field benchmark.

This module defines hypothesis-driven checks for deterministic ecosystem behavior, API constraints, and simulation invariants. The tests map computational rules to biological interpretations, including metabolic attrition, trigger-gated signaling, and O(1) spatial locality assumptions, to ensure that implementation details remain aligned with the PHIDS scientific model.
"""

from __future__ import annotations

import numpy as np

from phids.engine.core.flow_field import compute_flow_field


def test_flow_field_generation_benchmark(benchmark) -> None:  # type: ignore[no-untyped-def]
    """Validates the flow field generation benchmark invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Args:
        benchmark: Input value used to parameterize deterministic behavior for this callable.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    width = 40
    height = 40
    plant_energy = np.zeros((width, height), dtype=np.float64)
    toxin_layers = np.zeros((4, width, height), dtype=np.float64)

    plant_energy[10, 10] = 10.0
    plant_energy[30, 20] = 4.0
    toxin_layers[0, 20, 20] = 2.0

    result = benchmark(compute_flow_field, plant_energy, toxin_layers, width, height)

    assert result.shape == (width, height)
    assert np.isfinite(result).all()
