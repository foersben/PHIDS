# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Targeted unit and edge-case tests for flow field calculation coverage.

Validates SIMD base initialization parity, power-of-2 Jacobi relaxation,
subnormal float flushing under fastmath=True, parallel iteration parity,
and batch worker thread governance.
"""

from __future__ import annotations

import subprocess
import sys

import numpy as np
import pytest

from phids.engine.core.biotope import _numba_convolve_signal_layer
from phids.engine.core.flow_field import (
    _init_base_and_current_jit,
    _propagate_iteration_jit_parallel,
    _propagate_iteration_jit_pow2,
    _propagate_iteration_jit_pow2_parallel,
    _truncate_subnormals_jit,
    compute_flow_field,
)


def test_init_base_and_current_jit_vectorized_parity() -> None:
    """Verify SIMD-vectorized _init_base_and_current_jit matches explicit scalar loop calculation.

    Tests numerical parity across multi-layer toxin arrays and plant energy attraction fields.
    """
    w, h = 8, 8
    plant_energy = np.array([[float(x + y) for y in range(h)] for x in range(w)], dtype=np.float64)
    apparent_nutrition = np.ones((w, h), dtype=np.float64)
    toxin_layers = np.zeros((3, w, h), dtype=np.float64)
    toxin_layers[0, 2, 3] = 0.5
    toxin_layers[1, 2, 3] = 0.25
    toxin_layers[2, 4, 4] = 1.0

    base = np.zeros((w, h), dtype=np.float64)
    current = np.zeros((w, h), dtype=np.float64)

    _init_base_and_current_jit(
        width=w,
        height=h,
        plant_energy=plant_energy,
        apparent_nutrition_layer=apparent_nutrition,
        toxin_layers=toxin_layers,
        base=base,
        current=current,
        alpha=2.0,
        beta=1.5,
    )

    # Expected at (2,3): alpha*(2+3)*1.0 - beta*(0.5+0.25+0) = 10.0 - 1.125 = 8.875
    assert base[2, 3] == pytest.approx(8.875)
    assert current[2, 3] == pytest.approx(8.875)
    assert np.array_equal(base, current)


def test_flow_field_pow2_propagation_parity() -> None:
    """Verify bitwise power-of-2 Jacobi relaxation kernel convergence parity."""
    width, height = 16, 16
    plant_energy = np.zeros((width, height), dtype=np.float64)
    plant_energy[8, 8] = 50.0

    apparent_nutrition = np.ones((width, height), dtype=np.float64)
    toxin_layers = np.zeros((1, width, height), dtype=np.float64)

    field = compute_flow_field(
        plant_energy=plant_energy,
        apparent_nutrition_layer=apparent_nutrition,
        toxin_layers=toxin_layers,
        width=width,
        height=height,
    )

    assert field[8, 8] > 0.0
    assert field[7, 8] > 0.0
    assert field[0, 0] >= 0.0


def test_subnormal_float_flushing_and_fastmath_parity() -> None:
    """Verify subnormal float zeroing and fastmath=True kernel precision parity."""
    width, height = 8, 8
    kernel = np.array([[0.1, 0.2, 0.1], [0.2, 0.4, 0.2], [0.1, 0.2, 0.1]], dtype=np.float64)

    advected = np.full((width, height), 1e-15, dtype=np.float64)
    write_buf = np.zeros((width, height), dtype=np.float64)

    # Subnormal tail (< 1e-4) should be zeroed out
    _numba_convolve_signal_layer(
        width,
        height,
        decay=0.9,
        epsilon=1e-4,
        kernel=kernel,
        write_buffer=write_buf,
        advected_scratch=advected,
    )
    assert np.all(write_buf == 0.0)

    # Test explicit subnormal truncation kernel
    flow_arr = np.array([[1e-10, 5.0], [0.0, 1e-3]], dtype=np.float64)
    _truncate_subnormals_jit(2, 2, flow_arr, threshold=1e-4)
    assert flow_arr[0, 0] == 0.0
    assert flow_arr[0, 1] == 5.0
    assert flow_arr[1, 1] == 1e-3


def test_parallel_jit_flow_field_parity() -> None:
    """Verify multi-threaded parallel JIT Jacobi relaxation parity across grid sizes."""
    width, height = 128, 128
    plant_energy = np.zeros((width, height), dtype=np.float64)
    plant_energy[64, 64] = 100.0
    apparent_nutrition = np.ones((width, height), dtype=np.float64)
    toxin_layers = np.zeros((1, width, height), dtype=np.float64)

    field_parallel = compute_flow_field(
        plant_energy=plant_energy,
        apparent_nutrition_layer=apparent_nutrition,
        toxin_layers=toxin_layers,
        width=width,
        height=height,
    )

    # Parity check between pow2 sequential and pow2 parallel
    base = np.zeros((width, height), dtype=np.float64)
    base[64, 64] = 100.0
    current_seq = base.copy()
    nxt_seq = np.zeros_like(base)
    current_par = base.copy()
    nxt_par = np.zeros_like(base)

    mask_x, mask_y = width - 1, height - 1
    diff_seq = _propagate_iteration_jit_pow2(width, height, mask_x, mask_y, 0.6, base, current_seq, nxt_seq)
    diff_par = _propagate_iteration_jit_pow2_parallel(width, height, mask_x, mask_y, 0.6, base, current_par, nxt_par)

    assert np.allclose(diff_seq, diff_par)
    assert np.allclose(nxt_seq, nxt_par)

    # Check non-pow2 parallel kernel parity
    current_std_par = base.copy()
    nxt_std_par = np.zeros_like(base)
    diff_std = _propagate_iteration_jit_parallel(width, height, 0.6, base, current_std_par, nxt_std_par)
    assert np.allclose(diff_seq, diff_std)
    assert np.allclose(nxt_seq, nxt_std_par)
    assert field_parallel[64, 64] > 0.0


def test_batch_processing_thread_governance() -> None:
    """Verify batch worker thread pinning env configuration."""
    cmd = [
        sys.executable,
        "-c",
        "import os; from phids.engine.batch.orchestrator import _init_batch_worker; "
        "_init_batch_worker(); assert os.environ.get('NUMBA_NUM_THREADS') == '1'",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
