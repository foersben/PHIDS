"""Benchmark coverage for live dashboard payload assembly and JSON serialization.

This benchmark measures the end-to-end cost of constructing the live dashboard
payload in :func:`phids.api.presenters.dashboard.build_live_dashboard_payload`
and serializing it with ``json.dumps``. The measurement reflects the dominant
hot path used by the `/ws/ui/stream` JSON transport and therefore acts as a
regression guard for UI-stream throughput under evolving payload contracts.
"""

from __future__ import annotations

import json
import os
import warnings

import numpy as np
import pytest

from phids.api.presenters.dashboard import build_live_dashboard_payload
from phids.engine.loop import SimulationLoop


def _budget_from_env(name: str, default_ms: float) -> float:
    """Return a float millisecond budget from environment, falling back to ``default_ms``."""
    raw = os.getenv(name)
    if raw is None:
        return default_ms
    try:
        value = float(raw)
    except ValueError:
        return default_ms
    return value if value > 0.0 else default_ms


@pytest.mark.benchmark
def test_dashboard_payload_build_and_json_encode_benchmark(  # type: ignore[no-untyped-def]
    benchmark,
    loop_config_builder,
) -> None:
    """Benchmark dashboard payload assembly plus JSON encoding for one simulation snapshot."""
    loop = SimulationLoop(loop_config_builder(max_ticks=30))

    def _build_and_encode() -> str:
        payload = build_live_dashboard_payload(loop, substance_names={})
        return json.dumps(payload, separators=(",", ":"))

    encoded = benchmark(_build_and_encode)

    stats = benchmark.stats.stats
    rounds = np.asarray(getattr(stats, "data", []), dtype=np.float64)
    mean_ms = float(stats.mean) * 1000.0
    p95_ms = float(np.percentile(rounds, 95)) * 1000.0 if rounds.size > 0 else mean_ms

    warn_mean_ms = _budget_from_env("PHIDS_DASHBOARD_BENCH_WARN_MEAN_MS", 8.0)
    fail_mean_ms = _budget_from_env("PHIDS_DASHBOARD_BENCH_FAIL_MEAN_MS", 40.0)
    warn_p95_ms = _budget_from_env("PHIDS_DASHBOARD_BENCH_WARN_P95_MS", 16.0)
    fail_p95_ms = _budget_from_env("PHIDS_DASHBOARD_BENCH_FAIL_P95_MS", 80.0)

    benchmark.extra_info["mean_ms"] = round(mean_ms, 4)
    benchmark.extra_info["p95_ms"] = round(p95_ms, 4)

    if mean_ms > warn_mean_ms:
        warnings.warn(
            (
                "Dashboard payload mean latency exceeded warning budget: "
                f"{mean_ms:.3f}ms > {warn_mean_ms:.3f}ms"
            ),
            RuntimeWarning,
        )
    if p95_ms > warn_p95_ms:
        warnings.warn(
            (
                "Dashboard payload p95 latency exceeded warning budget: "
                f"{p95_ms:.3f}ms > {warn_p95_ms:.3f}ms"
            ),
            RuntimeWarning,
        )

    assert mean_ms <= fail_mean_ms, (
        "Dashboard payload mean latency exceeded fail budget: "
        f"{mean_ms:.3f}ms > {fail_mean_ms:.3f}ms"
    )
    assert p95_ms <= fail_p95_ms, (
        f"Dashboard payload p95 latency exceeded fail budget: {p95_ms:.3f}ms > {fail_p95_ms:.3f}ms"
    )

    assert encoded
    decoded = json.loads(encoded)
    assert "plants" in decoded
    assert isinstance(decoded["plants"], dict)
    assert "x" in decoded["plants"]
    assert "swarms" in decoded
    assert isinstance(decoded["swarms"], dict)
