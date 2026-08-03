# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for the MCP server resource and tool surfaces."""

import json
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


def test_live_simulation_resource_idle() -> None:
    """Test live simulation resource returns idle status when no loop loaded."""
    result = json.loads(live_simulation_resource())
    assert result["status"] == "idle"


def test_inspect_live_simulation_inactive() -> None:
    """Test inspect_live_simulation tool returns inactive status when no loop loaded."""
    result = inspect_live_simulation()
    assert result["status"] == "inactive"


def test_validate_biological_invariants_error() -> None:
    """Test validate_biological_invariants tool returns error when no loop loaded."""
    result = validate_biological_invariants()
    assert result["status"] == "error"


def test_live_simulation_tools_with_active_loop() -> None:
    """Test live simulation resource and tools with a mock SimulationLoop."""
    mock_loop = MagicMock()
    mock_loop.running = True
    mock_loop.paused = False
    mock_loop.tick = 168
    mock_loop.config.max_ticks = 1000
    mock_loop.terminated = False
    mock_loop.termination_reason = None

    mock_plant = MagicMock()
    mock_plant.energy = 50.0
    mock_plant.entity_id = 1
    mock_plant.mycorrhizal_connections = {2}

    mock_plant2 = MagicMock()
    mock_plant2.energy = 50.0
    mock_plant2.entity_id = 2
    mock_plant2.mycorrhizal_connections = {1}

    mock_swarm = MagicMock()
    mock_swarm.energy = 10.0
    mock_swarm.population = 5

    mock_entity1 = MagicMock()
    mock_entity1.get_component.return_value = mock_plant
    mock_entity2 = MagicMock()
    mock_entity2.get_component.return_value = mock_plant2
    mock_entity3 = MagicMock()
    mock_entity3.get_component.return_value = mock_swarm

    def query_mock(component_cls: type) -> list[MagicMock]:
        if "PlantComponent" in component_cls.__name__:
            return [mock_entity1, mock_entity2]
        return [mock_entity3]

    mock_loop.world.query.side_effect = query_mock
    mock_loop.world._entities = {1: mock_entity1, 2: mock_entity2, 3: mock_entity3}

    with patch("phids.mcp_server._get_active_sim_loop", return_value=mock_loop):
        res = json.loads(live_simulation_resource())
        assert res["status"] == "running"
        assert res["tick"] == 168
        assert res["active_plants"] == 2
        assert res["active_swarms"] == 1

        insp = inspect_live_simulation()
        assert insp["status"] == "active"
        assert insp["is_slow_tick"] is True
        assert insp["plant_count"] == 2
        assert insp["mycorrhizal_total_links"] == 1

        inv = validate_biological_invariants()
        assert inv["compliant"] is True
        assert inv["violations_count"] == 0


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


@patch("phids.mcp_server._PROJECT_ROOT")
def test_read_batch_summary_exception(mock_root: MagicMock) -> None:
    """Test read_batch_summary tool exception handling."""
    mock_path = MagicMock()
    mock_path.exists.return_value = True
    mock_root.__truediv__.return_value.__truediv__.return_value.__truediv__.return_value = mock_path

    with patch("builtins.open", side_effect=Exception("Read error")):
        result = read_batch_summary("job_123")
        assert result["status"] == "error"
        assert "Failed to read summary file: Read error" in result["message"]


def test_active_draft_resource_serialization() -> None:
    """Test serialization hooks for DraftState types."""
    from phids.api.schemas.species import FloraSpeciesParams
    from phids.api.ui_state.state import DraftState

    draft = DraftState()
    draft.flora_species.append(
        FloraSpeciesParams(
            species_id=1,
            name="Test",
            base_energy=1.0,
            max_energy=1.0,
            growth_rate=1.0,
            survival_threshold=1.0,
            reproduction_interval=1,
            seed_min_dist=1.0,
            seed_max_dist=1.0,
            seed_energy_cost=1.0,
            triggers=[],
        )
    )

    with patch("phids.mcp_server.get_draft", return_value=draft):
        result = active_draft_resource()
        assert "Test" in result


def test_analyze_simulation_drift() -> None:
    """Test prompt retrieval."""
    from phids.mcp_server import analyze_simulation_drift

    result = analyze_simulation_drift()
    assert "stochastic drift" in result


@patch("phids.mcp_server.mcp.run")
def test_run_mcp_server(mock_run: MagicMock) -> None:
    """Test MCP server entry point."""
    from phids.mcp_server import run_mcp_server

    run_mcp_server()
    mock_run.assert_called_once()


def test_active_draft_resource_serialization_error() -> None:
    """Test serialization hooks for DraftState types failure."""
    from phids.api.ui_state.state import DraftState

    draft = DraftState()
    draft.flora_placement_strategy = lambda x: x  # type: ignore  # Unserializable

    with patch("phids.mcp_server.get_draft", return_value=draft):
        import pytest

        with pytest.raises(TypeError):
            active_draft_resource()


def test_active_draft_resource_serialization_nested_dataclass() -> None:
    """Test serialization hooks for DraftState types success nested."""
    from phids.api.ui_state.state import DraftState

    draft = DraftState()
    import dataclasses

    @dataclasses.dataclass
    class Nested:
        value: str

    draft.flora_placement_strategy = Nested(value="test")  # type: ignore

    with patch("phids.mcp_server.get_draft", return_value=draft):
        result = active_draft_resource()
        assert "test" in result


def test_inspect_telemetry_schema_import_error() -> None:
    """Test telemetry schema import error."""
    import sys

    with patch.dict(sys.modules, {"zarr": None}):
        result = inspect_telemetry_schema("test")
        assert result["status"] == "error"
