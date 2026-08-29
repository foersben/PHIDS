# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit test suite for PHIDS MCP Server tool handlers and resources."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture


import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

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


def test_validate_simulation_config_valid() -> None:
    """Test validate_simulation_config with valid config."""
    from phids.io.scenario import load_scenario_from_json
    from phids.mcp_server import validate_simulation_config

    config = load_scenario_from_json("examples/ecosystem_equilibrium_benchmark_256x256.json")
    valid_json = config.model_dump_json()
    result = validate_simulation_config(valid_json)
    assert result["valid"] is True
    assert len(result["errors"]) == 0


def test_validate_simulation_config_invalid() -> None:
    """Test validate_simulation_config with invalid config."""
    from phids.mcp_server import validate_simulation_config

    invalid_json = '{"grid_width": 3}'  # Not a power of two
    result = validate_simulation_config(invalid_json)
    assert result["valid"] is False
    assert len(result["errors"]) > 0


def test_query_telemetry_schema_success() -> None:
    """Test query_telemetry_schema tool."""
    from phids.mcp_server import query_telemetry_schema

    mock_loop = MagicMock()
    mock_loop.telemetry._rows = [{"col1": 1, "col2": 2}]

    with patch("phids.mcp_server._get_active_sim_loop", return_value=mock_loop):
        res = query_telemetry_schema()
        assert res["status"] == "success"
        assert "col1" in res["columns"]
        assert "col2" in res["columns"]


def test_query_telemetry_schema_empty() -> None:
    """Test query_telemetry_schema tool when empty."""
    from phids.mcp_server import query_telemetry_schema

    mock_loop = MagicMock()
    mock_loop.telemetry._rows = []

    with patch("phids.mcp_server._get_active_sim_loop", return_value=mock_loop):
        res = query_telemetry_schema()
        assert res["status"] == "success"
        assert "No telemetry recorded yet" in res["message"]


def test_export_telemetry_data_error_no_loop() -> None:
    """Test export_telemetry_data error handling."""
    from phids.mcp_server import export_telemetry_data

    with patch("phids.mcp_server._get_active_sim_loop", return_value=None):
        res = export_telemetry_data("csv")
        assert res["status"] == "error"


def test_export_telemetry_data_invalid_params() -> None:
    """Test export_telemetry_data validation."""
    from phids.mcp_server import export_telemetry_data

    mock_loop = MagicMock()
    with patch("phids.mcp_server._get_active_sim_loop", return_value=mock_loop):
        res = export_telemetry_data("csv", data_type="invalid")
        assert res["status"] == "error"
        assert "Invalid data_type" in res["message"]

        res = export_telemetry_data("invalid_format", data_type="timeseries")
        assert res["status"] == "error"
        assert "Invalid format" in res["message"]


def test_export_telemetry_data_csv() -> None:
    """Test export_telemetry_data csv output."""
    from phids.mcp_server import export_telemetry_data

    mock_loop = MagicMock()
    mock_loop.telemetry._rows = [{"test": 1}]

    with patch("phids.mcp_server._get_active_sim_loop", return_value=mock_loop):
        with patch("phids.telemetry.export.core.filter_telemetry_rows", return_value=[{"test": 1}]):
            mock_df = MagicMock()
            mock_df.to_csv.return_value = "test_csv_data"
            with patch("phids.telemetry.export.core.aggregate_to_dataframe", return_value=mock_df):
                res = export_telemetry_data("csv", data_type="timeseries")
                assert res["status"] == "success"
                assert res["data"] == "test_csv_data"


@patch("phids.telemetry.export.png.generate_png_bytes")
def test_export_telemetry_data_png(mock_export: MagicMock) -> None:
    """Test export_telemetry_data png output."""
    import base64

    from phids.mcp_server import export_telemetry_data

    mock_loop = MagicMock()
    mock_loop.telemetry._rows = [{"test": 1}]
    mock_export.return_value = b"test_png_data"
    expected_b64 = base64.b64encode(b"test_png_data").decode("utf-8")

    with patch("phids.mcp_server._get_active_sim_loop", return_value=mock_loop):
        with patch("phids.telemetry.export.core.filter_telemetry_rows", return_value=[{"test": 1}]):
            res = export_telemetry_data("png", data_type="timeseries")
            assert res["status"] == "success"
            assert res["data"] == expected_b64


def test_export_telemetry_data_tex_table(mocker: MockerFixture) -> None:
    """Test LaTeX table export from the MCP tool."""
    mock_loop = mocker.Mock()
    mock_loop.telemetry._rows = [{"tick": 0, "Flora_A_Pop": 10}, {"tick": 1, "Flora_A_Pop": 20}]
    mock_loop.config.flora_species = []
    mock_loop.config.herbivore_species = []

    mocker.patch("phids.mcp_server._get_active_sim_loop", return_value=mock_loop)
    mocker.patch("phids.telemetry.export.core.filter_telemetry_rows", return_value=mock_loop.telemetry._rows)

    mock_export = mocker.patch("phids.telemetry.export.latex.export_bytes_tex_table", return_value=b"test_tex")

    from phids.mcp_server import export_telemetry_data

    result = export_telemetry_data("tex_table", "timeseries", 2, columns="tick")
    assert result["status"] == "success"
    assert result["format"] == "tex_table"
    assert result["data"] == "test_tex"
    mock_export.assert_called_once()


def test_export_telemetry_data_tex_tikz(mocker: MockerFixture) -> None:
    """Test LaTeX TikZ export from the MCP tool."""
    mock_loop = mocker.Mock()
    mock_loop.telemetry._rows = [{"tick": 0, "Flora_A_Pop": 10}]
    mock_loop.config.flora_species = []
    mock_loop.config.herbivore_species = []

    mocker.patch("phids.mcp_server._get_active_sim_loop", return_value=mock_loop)
    mocker.patch("phids.telemetry.export.core.filter_telemetry_rows", return_value=mock_loop.telemetry._rows)

    mock_export = mocker.patch("phids.telemetry.export.tikz.generate_tikz_str", return_value="tikz_code")

    from phids.mcp_server import export_telemetry_data

    result = export_telemetry_data("tex_tikz", "timeseries")
    assert result["status"] == "success"
    assert result["format"] == "tex_tikz"
    assert result["data"] == "tikz_code"
    mock_export.assert_called_once()


def test_export_telemetry_data_csv_phasespace(mocker: MockerFixture) -> None:
    """Test CSV export with decimation from the MCP tool."""
    mock_loop = mocker.Mock()
    mock_loop.telemetry._rows = [{"tick": 0, "Flora_A_Pop": 10}, {"tick": 1, "Flora_A_Pop": 20}]
    mock_loop.config.flora_species = []
    mock_loop.config.herbivore_species = []

    mocker.patch("phids.mcp_server._get_active_sim_loop", return_value=mock_loop)
    mocker.patch("phids.telemetry.export.core.filter_telemetry_rows", return_value=mock_loop.telemetry._rows)

    import pandas as pd

    mock_df = pd.DataFrame([{"tick": 0, "Flora_A_Pop": 10}, {"tick": 1, "Flora_A_Pop": 20}])
    mocker.patch("phids.telemetry.export.core.telemetry_to_dataframe", return_value=mock_df)
    mocker.patch("phids.telemetry.export.core.decimate_dataframe", return_value=mock_df)
    mocker.patch("phids.telemetry.export.core.filter_dataframe_columns", return_value=mock_df)

    from phids.mcp_server import export_telemetry_data

    result = export_telemetry_data("csv", "phasespace", tick_interval=2, columns="tick")
    assert result["status"] == "success"
    assert result["format"] == "csv"
    assert "tick" in result["data"]
