"""Benchmark coverage for replay and telemetry export serialization hot paths."""

from __future__ import annotations

import os
import warnings

import numpy as np
import polars as pl
import pytest

from phids.io.replay import deserialise_state, serialise_state
from phids.telemetry.export import export_bytes_csv, export_bytes_json


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
def test_replay_state_roundtrip_serialization_benchmark(benchmark) -> None:  # type: ignore[no-untyped-def]
    """Benchmark msgpack replay frame serialize+deserialize roundtrip on a representative snapshot."""
    state = {
        "tick": 42,
        "terminated": False,
        "termination_reason": None,
        "state_revision": 3,
        "plant_energy_layer": [[0.0, 1.0], [2.0, 3.0]],
        "signal_layers": [[[0.1, 0.0], [0.2, 0.3]], [[0.0, 0.0], [0.0, 0.5]]],
        "toxin_layers": [[[0.0, 0.0], [0.0, 0.1]]],
        "flow_field": [[0.4, 0.2], [0.1, 0.0]],
        "wind_vector_x": [[0.0, 0.1], [0.0, 0.1]],
        "wind_vector_y": [[0.0, -0.1], [0.0, -0.1]],
    }

    def _roundtrip() -> dict[str, object]:
        frame = serialise_state(state)
        return deserialise_state(frame)

    decoded = benchmark(_roundtrip)

    _enforce_budget(
        benchmark,
        metric_prefix="replay_roundtrip",
        warn_mean_ms=_budget_from_env("PHIDS_REPLAY_ROUNDTRIP_WARN_MEAN_MS", 2.0),
        fail_mean_ms=_budget_from_env("PHIDS_REPLAY_ROUNDTRIP_FAIL_MEAN_MS", 12.0),
        warn_p95_ms=_budget_from_env("PHIDS_REPLAY_ROUNDTRIP_WARN_P95_MS", 4.0),
        fail_p95_ms=_budget_from_env("PHIDS_REPLAY_ROUNDTRIP_FAIL_P95_MS", 24.0),
    )

    assert decoded["tick"] == state["tick"]


@pytest.mark.benchmark
def test_telemetry_export_bytes_csv_benchmark(benchmark) -> None:  # type: ignore[no-untyped-def]
    """Benchmark CSV byte export throughput for telemetry DataFrame streaming/download paths."""
    df = pl.DataFrame(
        {
            "tick": list(range(128)),
            "plant_population": [100 + (idx % 7) for idx in range(128)],
            "herbivore_population": [20 + (idx % 5) for idx in range(128)],
            "total_flora_energy": [500.0 + float(idx) for idx in range(128)],
        }
    )

    encoded = benchmark(export_bytes_csv, df)

    _enforce_budget(
        benchmark,
        metric_prefix="export_csv",
        warn_mean_ms=_budget_from_env("PHIDS_EXPORT_CSV_WARN_MEAN_MS", 3.0),
        fail_mean_ms=_budget_from_env("PHIDS_EXPORT_CSV_FAIL_MEAN_MS", 15.0),
        warn_p95_ms=_budget_from_env("PHIDS_EXPORT_CSV_WARN_P95_MS", 6.0),
        fail_p95_ms=_budget_from_env("PHIDS_EXPORT_CSV_FAIL_P95_MS", 30.0),
    )

    assert encoded.startswith(b"tick,")


@pytest.mark.benchmark
def test_telemetry_export_bytes_json_benchmark(benchmark) -> None:  # type: ignore[no-untyped-def]
    """Benchmark NDJSON byte export throughput for telemetry DataFrame streaming/download paths."""
    df = pl.DataFrame(
        {
            "tick": list(range(128)),
            "plant_population": [100 + (idx % 7) for idx in range(128)],
            "herbivore_population": [20 + (idx % 5) for idx in range(128)],
            "total_flora_energy": [500.0 + float(idx) for idx in range(128)],
        }
    )

    encoded = benchmark(export_bytes_json, df)

    _enforce_budget(
        benchmark,
        metric_prefix="export_ndjson",
        warn_mean_ms=_budget_from_env("PHIDS_EXPORT_JSON_WARN_MEAN_MS", 3.0),
        fail_mean_ms=_budget_from_env("PHIDS_EXPORT_JSON_FAIL_MEAN_MS", 15.0),
        warn_p95_ms=_budget_from_env("PHIDS_EXPORT_JSON_WARN_P95_MS", 6.0),
        fail_p95_ms=_budget_from_env("PHIDS_EXPORT_JSON_FAIL_P95_MS", 30.0),
    )

    assert encoded.startswith(b'{"tick":')
