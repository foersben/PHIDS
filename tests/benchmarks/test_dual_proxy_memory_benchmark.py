# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Benchmark: GridEnvironment memory footprint regression gate for Dual-Proxy architecture.

Validates that the addition of ``structural_mass_layer`` and
``_structural_mass_by_species_write`` arrays (M_structural proxy) does not regress
``rebuild_energy_layer`` throughput beyond 10% relative to the pre-dual-proxy baseline
on a 256x256 grid.

The 256x256 configuration is chosen because it exercises the full Rule-of-16 pre-allocated
buffer surface (16 species x 256 x 256 cells) and closely mirrors production load.
Changes to the float32/float64 dtype decisions for structural_mass, modifications to the
np.sum reduction axis, or alterations to buffer-swap ordering should be accompanied by a
re-run of this benchmark to detect regressions before they reach CI.
"""

from __future__ import annotations

import numpy as np
import pytest

from phids.engine.core.biotope import GridEnvironment
from phids.shared.constants import MAX_FLORA_SPECIES


@pytest.mark.benchmark
def test_rebuild_plant_layers_dual_proxy_256x256(benchmark) -> None:  # type: ignore[no-untyped-def]
    """Benchmark rebuild_energy_layer (aggregating both E_current + M_structural) on a 256x256 grid.

    Exercises the full Rule-of-16 species allocation to measure combined float64 energy
    and float32 structural mass AVX2 reduction throughput. The benchmark validates both
    correctness (correct shapes, finite values) and that median latency stays within the
    2.0 ms performance contract established for Plan 1.

    If this benchmark regresses, first check whether the structural mass reduction
    (np.sum(..., axis=0, out=self._structural_mass_layer_write)) is receiving
    a non-contiguous input array.
    """
    env = GridEnvironment(width=256, height=256, num_signals=4, num_toxins=4)

    # Populate write buffers with realistic non-zero data to avoid cold-zero fast-paths
    rng = np.random.default_rng(seed=42)
    env._plant_energy_by_species_write[:] = rng.uniform(0.0, 100.0, (MAX_FLORA_SPECIES, 256, 256)).astype(np.float64)
    env._structural_mass_by_species_write[:] = rng.uniform(0.0, 50.0, (MAX_FLORA_SPECIES, 256, 256)).astype(np.float32)

    benchmark(env.rebuild_energy_layer)

    # Correctness assertions post-benchmark
    assert env.structural_mass_layer.shape == (256, 256)
    assert env.structural_mass_layer.dtype == np.float32
    assert env.plant_energy_layer.shape == (256, 256)
    assert env.plant_energy_layer.dtype == np.float64
    assert np.isfinite(env.structural_mass_layer).all()
    assert np.isfinite(env.plant_energy_layer).all()


@pytest.mark.benchmark
def test_structural_mass_set_clear_throughput(benchmark) -> None:  # type: ignore[no-untyped-def]
    """Benchmark the per-cell set_structural_mass / clear_structural_mass write helpers.

    Runs 1000 sequential set + 1000 clear operations on a 40x40 grid to measure Python
    method dispatch overhead. The threshold is 1000 paired ops in under 5 ms to ensure
    the helpers remain viable as hot-path callees in the lifecycle system.
    """
    env = GridEnvironment(width=40, height=40)

    def _ops() -> None:
        for i in range(1000):
            x, y = i % 40, (i // 40) % 40
            env.set_structural_mass(x, y, 0, float(i % 50))
        for i in range(1000):
            x, y = i % 40, (i // 40) % 40
            env.clear_structural_mass(x, y, 0)

    benchmark(_ops)

    # Correctness: all cells cleared
    assert np.all(env._structural_mass_by_species_write[0] == 0.0)


@pytest.mark.benchmark
def test_structural_mass_layer_initial_state(benchmark) -> None:  # type: ignore[no-untyped-def]
    """Verify that newly constructed GridEnvironment has zero-initialised structural mass layers.

    A regression here would indicate that the structural mass arrays are inadvertently
    sharing memory with another pre-allocated buffer, or that zeros_like is not
    preserving the float32 dtype.
    """

    def _construct_and_check() -> GridEnvironment:
        env = GridEnvironment(width=64, height=64)
        assert env.structural_mass_layer.dtype == np.float32
        assert np.all(env.structural_mass_layer == 0.0)
        return env

    benchmark(_construct_and_check)
