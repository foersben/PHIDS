# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Zero-allocation Python heap memory invariant unit tests for JIT hot paths."""

from __future__ import annotations

import os
import tracemalloc

import numpy as np
import pytest

from phids.engine.core.flow_field import _compute_flow_field


@pytest.mark.heap_allocation
@pytest.mark.skipif(os.environ.get("NUMBA_DISABLE_JIT") == "1", reason="Requires Numba JIT enabled")
def test_flow_field_zero_python_heap_allocation() -> None:
    """Verify flow-field generation makes zero Python heap memory allocations during warm loop execution."""
    width, height = 32, 32
    plant_energy = np.zeros((width, height), dtype=np.float64, order="C")
    apparent_nutrition = np.ones((width, height), dtype=np.float64, order="C")
    toxin_layers = np.zeros((1, width, height), dtype=np.float64, order="C")

    base = np.zeros((width, height), dtype=np.float64, order="C")
    current = np.zeros((width, height), dtype=np.float64, order="C")
    nxt = np.zeros((width, height), dtype=np.float64, order="C")

    # Warm up JIT compilation
    _compute_flow_field(
        plant_energy, apparent_nutrition, toxin_layers, width, height, base, current, nxt, 1.0, 1.0, 0.5, 1e-6
    )

    tracemalloc.start()
    snapshot_before = tracemalloc.take_snapshot()

    for _ in range(20):
        _compute_flow_field(
            plant_energy, apparent_nutrition, toxin_layers, width, height, base, current, nxt, 1.0, 1.0, 0.5, 1e-6
        )

    snapshot_after = tracemalloc.take_snapshot()
    tracemalloc.stop()

    stats = snapshot_after.compare_to(snapshot_before, "lineno")
    total_new_bytes = sum(stat.size_diff for stat in stats if stat.size_diff > 0)

    # Hot path execution should make zero Python array allocations (< 2048 bytes C-API wrapper boundary)
    assert total_new_bytes <= 2048
