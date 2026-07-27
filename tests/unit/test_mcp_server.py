# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for the MCP server resource and tool surfaces."""

import json
from unittest.mock import MagicMock, patch

from phids.mcp_server import (
    active_draft_resource,
    inspect_telemetry_schema,
    query_batch_jobs,
    query_diagnostic_logs,
    read_batch_summary,
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
    assert "placement_mode" in snapshot
    assert "mycorrhizal_inter_species" in snapshot
    assert "active_batch_jobs_count" in snapshot
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


@patch("phids.mcp_server.get_draft")
def test_query_batch_jobs(mock_get_draft: MagicMock) -> None:
    """Test query_batch_jobs returns a dictionary."""
    from phids.api.schemas.responses import BatchJobState

    mock_draft = MagicMock()
    mock_draft.active_batch_jobs = {
        "job_1": BatchJobState(
            job_id="job_1", status="done", completed=10, total=10, scenario_name="test", started_at=""
        )
    }
    mock_get_draft.return_value = mock_draft
    result = query_batch_jobs()
    assert "job_1" in result
    assert result["job_1"]["status"] == "done"
    assert result["job_1"]["total_runs"] == 10


@patch("phids.mcp_server._PROJECT_ROOT")
def test_read_batch_summary_success(mock_root: MagicMock) -> None:
    """Test read_batch_summary tool success path."""
    mock_path = MagicMock()
    mock_path.exists.return_value = True

    mock_root.__truediv__.return_value.__truediv__.return_value.__truediv__.return_value = mock_path

    with patch("builtins.open") as mock_open:
        # Avoid curly braces in read_data that break coverage templite by returning a normal dict
        mock_open.return_value.__enter__.return_value.read.return_value = '{"dummy": "data"}'
        result = read_batch_summary("job_123")
        assert result["status"] == "success"
        assert result["data"]["dummy"] == "data"


@patch("phids.mcp_server._PROJECT_ROOT")
def test_read_batch_summary_not_found(mock_root: MagicMock) -> None:
    """Test read_batch_summary tool failure path."""
    mock_path = MagicMock()
    mock_path.exists.return_value = False

    mock_root.__truediv__.return_value.__truediv__.return_value.__truediv__.return_value = mock_path

    result = read_batch_summary("job_123")
    assert result["status"] == "error"
    assert "Summary file not found" in result["message"]
