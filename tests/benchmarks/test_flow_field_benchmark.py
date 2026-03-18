"""Performance benchmarks for the Numba-accelerated flow-field gradient kernel.

This module measures the wall-clock throughput of :func:`~phids.engine.core.flow_field.compute_flow_field`
on a representative 40×40 grid under a realistic multi-source configuration. The benchmark
validates not only correctness (finite output values, expected shape) but also that the Numba
JIT-compiled iterative Jacobi propagation does not regress in throughput relative to the
performance contract established when the kernel was introduced. Changes to diffusion iteration
count, decay constants, or subnormal-float truncation thresholds should be accompanied by a
re-run of this benchmark to detect performance regressions before they reach CI.
"""

from __future__ import annotations

import numpy as np
import pytest

from phids.engine.core.flow_field import compute_flow_field


@pytest.mark.benchmark
def test_flow_field_generation_benchmark(benchmark) -> None:  # type: ignore[no-untyped-def]
    """Benchmarks compute_flow_field throughput on a 40×40 grid with two plant attractors and one toxin repeller.

    The benchmark uses ``pytest-benchmark`` to measure median call latency across repeated
    invocations of the full public wrapper :func:`~phids.engine.core.flow_field.compute_flow_field`,
    including the ``toxin_layers.sum(axis=0)`` aggregation and the final NumPy cast. Correctness
    is verified post-benchmark: the returned array must be shaped (40, 40) and contain no
    non-finite values, confirming that the Jacobi propagation and subnormal-float truncation
    produce numerically stable outputs.

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
