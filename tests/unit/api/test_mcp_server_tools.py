# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit test suite for PHIDS MCP Server tool handlers and resources."""

from __future__ import annotations

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


@patch("phids.telemetry.export.latex.export_bytes_tex_table")
def test_export_telemetry_data_tex_table(mock_export: MagicMock) -> None:
    """Test export_telemetry_data tex_table output."""
    from phids.mcp_server import export_telemetry_data

    mock_loop = MagicMock()
    mock_loop.telemetry._rows = [{"test": 1}]
    mock_export.return_value = b"test_tex_table_data"

    with patch("phids.mcp_server._get_active_sim_loop", return_value=mock_loop):
        with patch("phids.telemetry.export.core.filter_telemetry_rows", return_value=[{"test": 1}]):
            res = export_telemetry_data("tex_table", data_type="timeseries")
            assert res["status"] == "success"
            assert res["data"] == "test_tex_table_data"


@patch("phids.telemetry.export.tikz.generate_tikz_str")
def test_export_telemetry_data_tex_tikz(mock_export: MagicMock) -> None:
    """Test export_telemetry_data tex_tikz output."""
    from phids.mcp_server import export_telemetry_data

    mock_loop = MagicMock()
    mock_loop.telemetry._rows = [{"test": 1}]
    mock_export.return_value = "test_tikz_data"

    with patch("phids.mcp_server._get_active_sim_loop", return_value=mock_loop):
        with patch("phids.telemetry.export.core.filter_telemetry_rows", return_value=[{"test": 1}]):
            res = export_telemetry_data("tex_tikz", data_type="timeseries")
            assert res["status"] == "success"
            assert res["data"] == "test_tikz_data"


def test_export_telemetry_data_csv_branches() -> None:
    """Test export_telemetry_data csv output branches."""
    from phids.mcp_server import export_telemetry_data

    mock_loop = MagicMock()
    mock_loop.telemetry._rows = [{"test": 1}]

    with patch("phids.mcp_server._get_active_sim_loop", return_value=mock_loop):
        with patch("phids.telemetry.export.core.filter_telemetry_rows", return_value=[{"test": 1}]):
            mock_df = MagicMock()
            mock_df.to_csv.return_value = "test_csv_data"
            with patch("phids.telemetry.export.core.telemetry_to_dataframe", return_value=mock_df) as mock_tel_df:
                with patch("phids.telemetry.export.core.decimate_dataframe", return_value=mock_df) as mock_dec:
                    with patch("phids.telemetry.export.core.filter_dataframe_columns", return_value=mock_df) as m_filt:
                        res = export_telemetry_data("csv", data_type="phasespace", tick_interval=2, columns="test")
                        assert res["status"] == "success"
                        mock_tel_df.assert_called_once()
                        mock_dec.assert_called_once()
                        m_filt.assert_called_once()


def test_export_telemetry_data_csv_timeseries() -> None:
    """Test export_telemetry_data csv output branches."""
    from phids.mcp_server import export_telemetry_data

    mock_loop = MagicMock()
    mock_loop.telemetry._rows = [{"test": 1}]

    with patch("phids.mcp_server._get_active_sim_loop", return_value=mock_loop):
        with patch("phids.telemetry.export.core.filter_telemetry_rows", return_value=[{"test": 1}]):
            mock_df = MagicMock()
            mock_df.to_csv.return_value = "test_csv_data"
            with patch("phids.telemetry.export.core.aggregate_to_dataframe", return_value=mock_df) as mock_agg_df:
                with patch("phids.telemetry.export.core.decimate_dataframe", return_value=mock_df) as mock_dec:
                    with patch("phids.telemetry.export.core.filter_dataframe_columns", return_value=mock_df) as m_filt:
                        res = export_telemetry_data("csv", data_type="timeseries", tick_interval=2, columns="test")
                        assert res["status"] == "success"
                        mock_agg_df.assert_called_once()
                        mock_dec.assert_called_once()
                        m_filt.assert_called_once()


def test_export_telemetry_data_invalid_format_fallback() -> None:
    """Test export_telemetry_data unknown format branch."""
    from phids.mcp_server import export_telemetry_data

    mock_loop = MagicMock()
    with patch("phids.mcp_server._get_active_sim_loop", return_value=mock_loop):
        res = export_telemetry_data("unknown")
        assert res["status"] == "error"


def test_read_batch_summary_success() -> None:
    """Test read_batch_summary success branch."""
    import json

    from phids.mcp_server import read_batch_summary

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        with patch("phids.mcp_server._PROJECT_ROOT", tmp_path):
            # Create the mocked path
            batch_dir = tmp_path / "data" / "batches"
            batch_dir.mkdir(parents=True, exist_ok=True)
            summary_file = batch_dir / "test_job_summary.json"

            with open(summary_file, "w") as f:
                json.dump({"test": "data"}, f)

            res = read_batch_summary("test_job")
            assert res["status"] == "success"
            assert res["data"] == {"test": "data"}


def test_read_batch_summary_read_error() -> None:
    """Test read_batch_summary read error branch."""
    from phids.mcp_server import read_batch_summary

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        with patch("phids.mcp_server._PROJECT_ROOT", tmp_path):
            batch_dir = tmp_path / "data" / "batches"
            batch_dir.mkdir(parents=True, exist_ok=True)
            summary_file = batch_dir / "test_job_error_summary.json"

            # Create a directory instead of a file so read fails
            summary_file.mkdir()

            res = read_batch_summary("test_job_error")
            assert res["status"] == "error"
