"""Benchmark coverage for websocket frame encoding paths used by PHIDS streaming managers."""

from __future__ import annotations

import os
import warnings

import numpy as np
import pytest

from phids.api.presenters.dashboard import build_live_dashboard_payload
from phids.api.websockets.manager import SimulationStreamManager, UIStreamManager
from phids.engine.loop import SimulationLoop


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
def test_simulation_websocket_frame_encode_benchmark(  # type: ignore[no-untyped-def]
    benchmark,
    loop_config_builder,
) -> None:
    """Benchmark msgpack+zlib frame construction for the simulation binary websocket stream."""
    loop = SimulationLoop(loop_config_builder(max_ticks=20))
    manager = SimulationStreamManager()

    def _encode_frame() -> bytes:
        loop.tick += 1
        return manager._encoded_snapshot_bytes(loop)

    encoded = benchmark(_encode_frame)

    _enforce_budget(
        benchmark,
        metric_prefix="simulation_ws_encode",
        warn_mean_ms=_budget_from_env("PHIDS_WS_SIM_ENCODE_WARN_MEAN_MS", 12.0),
        fail_mean_ms=_budget_from_env("PHIDS_WS_SIM_ENCODE_FAIL_MEAN_MS", 60.0),
        warn_p95_ms=_budget_from_env("PHIDS_WS_SIM_ENCODE_WARN_P95_MS", 24.0),
        fail_p95_ms=_budget_from_env("PHIDS_WS_SIM_ENCODE_FAIL_P95_MS", 120.0),
    )

    assert encoded


@pytest.mark.benchmark
def test_ui_websocket_payload_encode_benchmark(  # type: ignore[no-untyped-def]
    benchmark,
    loop_config_builder,
) -> None:
    """Benchmark compact JSON payload assembly for the UI websocket stream."""
    loop = SimulationLoop(loop_config_builder(max_ticks=20))
    manager = UIStreamManager(
        payload_builder=lambda current_loop: build_live_dashboard_payload(
            current_loop,
            substance_names={},
        )
    )

    def _encode_payload() -> str:
        loop.tick += 1
        return manager._encoded_payload(loop)

    encoded = benchmark(_encode_payload)

    _enforce_budget(
        benchmark,
        metric_prefix="ui_ws_encode",
        warn_mean_ms=_budget_from_env("PHIDS_WS_UI_ENCODE_WARN_MEAN_MS", 12.0),
        fail_mean_ms=_budget_from_env("PHIDS_WS_UI_ENCODE_FAIL_MEAN_MS", 60.0),
        warn_p95_ms=_budget_from_env("PHIDS_WS_UI_ENCODE_WARN_P95_MS", 24.0),
        fail_p95_ms=_budget_from_env("PHIDS_WS_UI_ENCODE_FAIL_P95_MS", 120.0),
    )

    assert encoded
