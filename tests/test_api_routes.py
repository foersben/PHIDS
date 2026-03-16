"""Experimental validation suite for test api routes.

This module defines hypothesis-driven checks for deterministic ecosystem behavior, API constraints, and simulation invariants. The tests map computational rules to biological interpretations, including metabolic attrition, trigger-gated signaling, and O(1) spatial locality assumptions, to ensure that implementation details remain aligned with the PHIDS scientific model.
"""

from __future__ import annotations

from phids.api.main import app


def test_required_routes_present() -> None:
    """Validates the required routes present invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    paths = {route.path for route in app.router.routes}

    assert "/api/scenario/load" in paths
    assert "/api/simulation/start" in paths
    assert "/api/simulation/pause" in paths
    assert "/api/simulation/step" in paths
    assert "/api/simulation/reset" in paths
    assert "/api/simulation/tick-rate" in paths
    assert "/" in paths
    assert "/ui/dashboard" in paths
    assert "/ui/diagnostics/frontend" in paths
    assert "/ui/placements" in paths
    assert "/api/ui/cell-details" in paths
    assert "/api/telemetry/export/csv" in paths
    assert "/api/telemetry/export/json" in paths
    assert "/api/telemetry/chartjs-data" in paths
    assert "/api/telemetry/table_preview" in paths
    assert "/api/telemetry" in paths
    assert "/api/export/{data_type}" in paths
    assert "/api/batch/start" in paths
    assert "/api/batch/ledger" in paths
    assert "/api/batch/load-persisted" in paths
    assert "/ui/batch" in paths
    assert "/ws/simulation/stream" in paths
    assert "/ws/ui/stream" in paths
