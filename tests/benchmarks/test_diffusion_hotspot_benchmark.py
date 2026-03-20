"""Benchmark coverage for signal diffusion hotspot behavior in GridEnvironment."""

from __future__ import annotations

import os
import warnings

import numpy as np
import pytest

from phids.engine.core.biotope import GridEnvironment


def _budget_from_env(name: str, default_ms: float) -> float:
    """Return a positive millisecond budget from environment or a deterministic fallback."""
    raw = os.getenv(name)
    if raw is None:
        return default_ms
    try:
        value = float(raw)
    except ValueError:
        return default_ms
    return value if value > 0.0 else default_ms


def _enforce_budget(  # type: ignore[no-untyped-def]
    benchmark,
    *,
    metric_prefix: str,
    warn_mean_ms: float,
    fail_mean_ms: float,
    warn_p95_ms: float,
    fail_p95_ms: float,
) -> None:
    """Apply warning and fail budget checks using pytest-benchmark timing statistics."""
    stats = benchmark.stats.stats
    rounds = np.asarray(getattr(stats, "data", []), dtype=np.float64)
    mean_ms = float(stats.mean) * 1000.0
    p95_ms = float(np.percentile(rounds, 95)) * 1000.0 if rounds.size > 0 else mean_ms

    benchmark.extra_info[f"{metric_prefix}_mean_ms"] = round(mean_ms, 4)
    benchmark.extra_info[f"{metric_prefix}_p95_ms"] = round(p95_ms, 4)

    if mean_ms > warn_mean_ms:
        warnings.warn(
            (
                f"{metric_prefix} mean latency exceeded warning budget: "
                f"{mean_ms:.3f}ms > {warn_mean_ms:.3f}ms"
            ),
            RuntimeWarning,
        )
    if p95_ms > warn_p95_ms:
        warnings.warn(
            (
                f"{metric_prefix} p95 latency exceeded warning budget: "
                f"{p95_ms:.3f}ms > {warn_p95_ms:.3f}ms"
            ),
            RuntimeWarning,
        )

    assert mean_ms <= fail_mean_ms, (
        f"{metric_prefix} mean latency exceeded fail budget: {mean_ms:.3f}ms > {fail_mean_ms:.3f}ms"
    )
    assert p95_ms <= fail_p95_ms, (
        f"{metric_prefix} p95 latency exceeded fail budget: {p95_ms:.3f}ms > {fail_p95_ms:.3f}ms"
    )


@pytest.mark.benchmark
def test_diffusion_sparse_fast_path_benchmark(benchmark) -> None:  # type: ignore[no-untyped-def]
    """Benchmark diffusion when all signal layers remain below the epsilon activity threshold."""
    env = GridEnvironment(width=40, height=40, num_signals=4, num_toxins=1)

    def _diffuse_sparse() -> None:
        env.diffuse_signals()

    benchmark(_diffuse_sparse)

    _enforce_budget(
        benchmark,
        metric_prefix="diffusion_sparse",
        warn_mean_ms=_budget_from_env("PHIDS_DIFFUSION_SPARSE_WARN_MEAN_MS", 4.0),
        fail_mean_ms=_budget_from_env("PHIDS_DIFFUSION_SPARSE_FAIL_MEAN_MS", 20.0),
        warn_p95_ms=_budget_from_env("PHIDS_DIFFUSION_SPARSE_WARN_P95_MS", 8.0),
        fail_p95_ms=_budget_from_env("PHIDS_DIFFUSION_SPARSE_FAIL_P95_MS", 40.0),
    )

    assert np.count_nonzero(env.signal_layers) == 0


@pytest.mark.benchmark
def test_diffusion_active_hotspot_benchmark(benchmark) -> None:  # type: ignore[no-untyped-def]
    """Benchmark diffusion under active plumes and non-zero wind vectors across all signal layers."""
    env = GridEnvironment(width=40, height=40, num_signals=4, num_toxins=1)
    env.set_uniform_wind(0.25, -0.1)

    for signal_id in range(env.num_signals):
        env.signal_layers[signal_id, 20, 20] = 1.0
        env.signal_layers[signal_id, 14, 23] = 0.6
        env.signal_layers[signal_id, 27, 18] = 0.4

    def _diffuse_active() -> None:
        env.diffuse_signals()

    benchmark(_diffuse_active)

    _enforce_budget(
        benchmark,
        metric_prefix="diffusion_active",
        warn_mean_ms=_budget_from_env("PHIDS_DIFFUSION_ACTIVE_WARN_MEAN_MS", 6.0),
        fail_mean_ms=_budget_from_env("PHIDS_DIFFUSION_ACTIVE_FAIL_MEAN_MS", 30.0),
        warn_p95_ms=_budget_from_env("PHIDS_DIFFUSION_ACTIVE_WARN_P95_MS", 12.0),
        fail_p95_ms=_budget_from_env("PHIDS_DIFFUSION_ACTIVE_FAIL_P95_MS", 60.0),
    )

    assert np.isfinite(env.signal_layers).all()
    assert float(env.signal_layers.max()) >= 0.0
