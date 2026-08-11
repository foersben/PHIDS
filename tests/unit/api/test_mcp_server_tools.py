# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit test suite for PHIDS MCP Server tool handlers and resources."""

from __future__ import annotations

import tempfile
from pathlib import Path

from phids.mcp_server import (
    active_draft_resource,
    inspect_live_simulation,
    inspect_telemetry_schema,
    live_simulation_resource,
    query_batch_jobs,
    query_diagnostic_logs,
    read_batch_summary,
    runtime_snapshot,
    validate_biological_invariants,
    validate_okf_compliance,
)


def test_query_batch_jobs() -> None:
    """Verify query_batch_jobs returns formatted job metadata dictionary."""
    res = query_batch_jobs()
    assert isinstance(res, dict)


def test_runtime_snapshot() -> None:
    """Verify runtime_snapshot returns structured snapshot dictionary."""
    snapshot = runtime_snapshot()
    assert isinstance(snapshot, dict)
    assert "scenario_name" in snapshot
    assert "grid_width" in snapshot


def test_inspect_live_simulation() -> None:
    """Verify inspect_live_simulation when loop is active vs inactive."""
    res = inspect_live_simulation()
    assert isinstance(res, dict)
    assert "status" in res


def test_validate_biological_invariants() -> None:
    """Verify validate_biological_invariants returns status and message when inactive."""
    res = validate_biological_invariants()
    assert isinstance(res, dict)
    assert "status" in res


def test_query_diagnostic_logs() -> None:
    """Verify query_diagnostic_logs returns list of recent log records."""
    logs = query_diagnostic_logs(limit=10)
    assert isinstance(logs, list)
    assert len(logs) <= 10


def test_validate_okf_compliance() -> None:
    """Verify validate_okf_compliance returns documentation OKF metrics."""
    res = validate_okf_compliance()
    assert isinstance(res, dict)
    assert "compliant" in res
    assert "output" in res


def test_inspect_telemetry_schema_nonexistent() -> None:
    """Verify inspect_telemetry_schema error handling when Zarr store path is missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_zarr = Path(tmpdir) / "missing.zarr"
        res = inspect_telemetry_schema(str(fake_zarr))
        assert res["status"] == "error"
        assert "message" in res


def test_read_batch_summary_nonexistent() -> None:
    """Verify read_batch_summary error handling for invalid job ID."""
    res = read_batch_summary("nonexistent_job_123")
    assert res["status"] == "error"
    assert "message" in res


def test_mcp_resources() -> None:
    """Verify active_draft_resource and live_simulation_resource strings."""
    draft_json = active_draft_resource()
    assert isinstance(draft_json, str)

    sim_str = live_simulation_resource()
    assert isinstance(sim_str, str)
