# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for the MCP server resource and tool surfaces."""

import json
from unittest.mock import MagicMock, patch

from phids.mcp_server import (
    active_draft_resource,
    inspect_telemetry_schema,
    query_diagnostic_logs,
    runtime_snapshot,
    validate_okf_compliance,
)


def test_active_draft_resource() -> None:
    """Test JSON serialization of the draft state."""
    resource_str = active_draft_resource()
    data = json.loads(resource_str)
    assert "scenario_name" in data
    assert "grid_width" in data


def test_runtime_snapshot() -> None:
    """Test runtime_snapshot returns correct counts."""
    snapshot = runtime_snapshot()
    assert "scenario_name" in snapshot
    assert "dimensions" in snapshot
    assert "termination_thresholds" in snapshot
    assert snapshot["flora_species_count"] >= 0


def test_inspect_telemetry_schema_error() -> None:
    """Test telemetry schema handles invalid path gracefully."""
    result = inspect_telemetry_schema("/invalid/path/that/does/not/exist")
    assert result["status"] == "error"
    assert "Store path does not exist" in result["message"]


@patch("phids.mcp_server.subprocess.run")
def test_validate_okf_compliance_success(mock_run: MagicMock) -> None:
    """Test OKF compliance tool success path."""
    mock_run.return_value = MagicMock(returncode=0, stdout="OKF passed", stderr="")
    result = validate_okf_compliance()
    assert result["compliant"] is True
    assert "OKF passed" in result["output"]


@patch("phids.mcp_server.subprocess.run")
def test_validate_okf_compliance_failure(mock_run: MagicMock) -> None:
    """Test OKF compliance tool failure path."""
    mock_run.return_value = MagicMock(returncode=1, stdout="Fail", stderr="OKF failed")
    result = validate_okf_compliance()
    assert result["compliant"] is False
    assert "Fail" in result["output"]


@patch("phids.mcp_server.get_recent_logs")
def test_query_diagnostic_logs(mock_get_logs: MagicMock) -> None:
    """Test diagnostic logs tool."""
    mock_get_logs.return_value = [{"message": "Log 1"}, {"message": "Log 2"}]
    result = query_diagnostic_logs()
    assert result == [{"message": "Log 1"}, {"message": "Log 2"}]
