"""Integration checks for simulation-control and scenario HTTP routes.

This module isolates API-surface regressions for simulation control, telemetry export, middleware
logging, and scenario import/export behavior. Each test validates one transition or one endpoint
contract so that failures localize to a single route family instead of cascading through unrelated
state mutations.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

import pytest
from httpx import AsyncClient

import phids.api.main as api_main
from phids.api.schemas import SimulationConfig


@pytest.mark.asyncio
async def test_api_root_contains_simulation_controls(api_client: AsyncClient) -> None:
    """Verify the root page renders the step and reset controls used by the simulation UI."""
    resp = await api_client.get("/")

    assert resp.status_code == 200, resp.text
    assert "⏭ Step" in resp.text
    assert "↺ Reset" in resp.text


@pytest.mark.asyncio
async def test_api_simulation_status_requires_loaded_loop(api_client: AsyncClient) -> None:
    """Verify simulation status returns 400 until a scenario has been loaded."""
    resp = await api_client.get("/api/simulation/status")

    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_api_simulation_start_pause_resume_flow(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify start/pause/status transitions and repeated start behavior are reported correctly."""
    config = config_builder()
    load_resp = await api_client.post("/api/scenario/load", json=config.model_dump(mode="json"))
    assert load_resp.status_code == 200, load_resp.text

    htmx_start_resp = await api_client.post("/api/simulation/start", headers={"HX-Request": "true"})
    assert htmx_start_resp.status_code == 200, htmx_start_resp.text
    assert "sim-status" in htmx_start_resp.text

    reset_loaded_resp = await api_client.post("/api/simulation/reset")
    assert reset_loaded_resp.status_code == 200, reset_loaded_resp.text
    assert reset_loaded_resp.json()["tick"] == 0

    start_resp = await api_client.post("/api/simulation/start")
    assert start_resp.status_code == 200, start_resp.text
    assert start_resp.json()["message"] == "Simulation started."

    reload_resp = await api_client.post("/api/scenario/load", json=config.model_dump(mode="json"))
    assert reload_resp.status_code == 200, reload_resp.text

    running_resp = await api_client.post("/api/simulation/start")
    assert running_resp.status_code == 200, running_resp.text
    assert running_resp.json()["message"] == "Simulation started."

    assert api_main._sim_loop is not None
    api_main._sim_loop.start()
    already_running_resp = await api_client.post("/api/simulation/start")
    assert already_running_resp.status_code == 200, already_running_resp.text
    assert already_running_resp.json()["message"] == "Simulation already running."

    pause_resp = await api_client.post("/api/simulation/pause")
    assert pause_resp.status_code == 200, pause_resp.text
    assert pause_resp.json()["message"] == "Simulation paused."

    status_resp = await api_client.get("/api/simulation/status")
    assert status_resp.status_code == 200, status_resp.text
    assert status_resp.json()["paused"] is True


@pytest.mark.asyncio
async def test_api_simulation_step_increments_tick(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify a manual step increments tick state once a scenario is loaded."""
    load_resp = await api_client.post(
        "/api/scenario/load", json=config_builder().model_dump(mode="json")
    )
    assert load_resp.status_code == 200, load_resp.text
    step_resp = await api_client.post("/api/simulation/step")

    assert step_resp.status_code == 200, step_resp.text
    assert step_resp.json()["tick"] >= 1


@pytest.mark.asyncio
async def test_api_simulation_reset_restores_tick_zero(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify reset returns tick zero and status reflects the reset state."""
    load_resp = await api_client.post(
        "/api/scenario/load", json=config_builder().model_dump(mode="json")
    )
    assert load_resp.status_code == 200, load_resp.text
    step_resp = await api_client.post("/api/simulation/step")
    assert step_resp.status_code == 200, step_resp.text
    reset_resp = await api_client.post("/api/simulation/reset")
    status_resp = await api_client.get("/api/simulation/status")

    assert reset_resp.status_code == 200, reset_resp.text
    assert reset_resp.json()["tick"] == 0
    assert status_resp.status_code == 200, status_resp.text
    assert status_resp.json()["tick"] == 0


@pytest.mark.asyncio
async def test_api_simulation_wind_update_round_trip(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify wind updates are applied and returned by the simulation control route."""
    load_resp = await api_client.post(
        "/api/scenario/load", json=config_builder().model_dump(mode="json")
    )
    assert load_resp.status_code == 200, load_resp.text
    wind_resp = await api_client.put("/api/simulation/wind", json={"wind_x": 1.5, "wind_y": -0.5})

    assert wind_resp.status_code == 200, wind_resp.text
    assert wind_resp.json()["wind_x"] == pytest.approx(1.5)
    assert wind_resp.json()["wind_y"] == pytest.approx(-0.5)


@pytest.mark.asyncio
async def test_api_telemetry_exports_include_tick_field(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify telemetry export endpoints return tick data once telemetry has been recorded."""
    load_resp = await api_client.post(
        "/api/scenario/load", json=config_builder().model_dump(mode="json")
    )
    assert load_resp.status_code == 200, load_resp.text
    assert api_main._sim_loop is not None
    api_main._sim_loop.telemetry.record(api_main._sim_loop.world, tick=0)
    csv_resp = await api_client.get("/api/telemetry/export/csv")
    json_resp = await api_client.get("/api/telemetry/export/json")

    assert csv_resp.status_code == 200, csv_resp.text
    assert "tick" in csv_resp.text
    assert json_resp.status_code == 200, json_resp.text
    assert '"tick":0' in json_resp.text.replace(" ", "")


@pytest.mark.asyncio
async def test_api_simulation_rejects_commands_when_terminated(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify start is rejected once the simulation loop has terminated."""
    load_resp = await api_client.post(
        "/api/scenario/load", json=config_builder().model_dump(mode="json")
    )
    assert load_resp.status_code == 200, load_resp.text
    assert api_main._sim_loop is not None
    api_main._sim_loop.terminated = True
    api_main._sim_loop.running = False
    api_main._sim_loop.termination_reason = "manual test"
    terminated_resp = await api_client.post("/api/simulation/start")

    assert terminated_resp.status_code == 400, terminated_resp.text


@pytest.mark.asyncio
async def test_http_middleware_logs_ui_and_api_requests(
    api_client: AsyncClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify middleware emits warning and request log lines for UI and unloaded API access."""
    with caplog.at_level(logging.WARNING):
        root_resp = await api_client.get("/")
        missing_resp = await api_client.get("/api/simulation/status")

    assert root_resp.status_code == 200, root_resp.text
    assert missing_resp.status_code == 400, missing_resp.text
    assert "Simulation access requested before a scenario was loaded" in caplog.text
    assert "HTTP GET /api/simulation/status -> 400" in caplog.text


@pytest.mark.asyncio
async def test_scenario_import_export_endpoints_roundtrip(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify scenario import accepts valid JSON and export returns expected core fields."""
    config = config_builder()
    import_resp = await api_client.post(
        "/api/scenario/import",
        files={
            "file": (
                "scenario.json",
                json.dumps(config.model_dump(mode="json")),
                "application/json",
            )
        },
    )
    assert import_resp.status_code == 200, import_resp.text

    export_resp = await api_client.get("/api/scenario/export")
    assert export_resp.status_code == 200, export_resp.text
    exported = json.loads(export_resp.text)
    assert exported["grid_width"] == config.grid_width
    assert exported["herbivore_species"][0]["name"] == "herbivore"


@pytest.mark.asyncio
async def test_scenario_import_rejects_invalid_json(api_client: AsyncClient) -> None:
    """Verify scenario import returns 422 for malformed JSON uploads."""
    resp = await api_client.post(
        "/api/scenario/import",
        files={"file": ("broken.json", "{not valid json", "application/json")},
    )

    assert resp.status_code == 422, resp.text
