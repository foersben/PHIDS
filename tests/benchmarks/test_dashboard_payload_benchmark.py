"""Benchmark coverage for live dashboard payload assembly and JSON serialization.

This benchmark measures the end-to-end cost of constructing the live dashboard
payload in :func:`phids.api.presenters.dashboard.build_live_dashboard_payload`
and serializing it with ``json.dumps``. The measurement reflects the dominant
hot path used by the `/ws/ui/stream` JSON transport and therefore acts as a
regression guard for UI-stream throughput under evolving payload contracts.
"""

from __future__ import annotations

import json

import pytest

from phids.api.presenters.dashboard import build_live_dashboard_payload
from phids.engine.loop import SimulationLoop


@pytest.mark.benchmark
def test_dashboard_payload_build_and_json_encode_benchmark(  # type: ignore[no-untyped-def]
    benchmark,
    loop_config_builder,
) -> None:
    """Benchmark dashboard payload assembly plus JSON encoding for one simulation snapshot."""
    loop = SimulationLoop(loop_config_builder(max_ticks=30))

    def _build_and_encode() -> str:
        payload = build_live_dashboard_payload(loop, substance_names={})
        return json.dumps(payload)

    encoded = benchmark(_build_and_encode)

    assert encoded
    decoded = json.loads(encoded)
    assert "plants" in decoded
    assert isinstance(decoded["plants"], dict)
    assert "x" in decoded["plants"]
    assert "swarms" in decoded
    assert isinstance(decoded["swarms"], dict)
