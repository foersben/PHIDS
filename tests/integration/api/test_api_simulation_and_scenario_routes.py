"""Integration checks for simulation-control and scenario HTTP routes.

This module isolates API-surface regressions for simulation control, telemetry export, middleware
logging, and scenario import/export behavior. Each test validates one transition or one endpoint
contract so that failures localize to a single route family instead of cascading through unrelated
state mutations.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Callable
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

import phids.api.main as api_main
from phids.api.schemas import SimulationConfig


@pytest.fixture(autouse=True)
async def _reset_sim_state() -> AsyncGenerator[None, None]:
    task = api_main._sim_task
    if task is not None and not task.done():
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    api_main._sim_task = None
    api_main._sim_loop = None
    yield
    task = api_main._sim_task
    if task is not None and not task.done():
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    api_main._sim_task = None
    api_main._sim_loop = None


@pytest.fixture
def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=api_main.app), base_url="http://test")


@pytest.mark.asyncio
async def test_api_root_contains_simulation_controls(_client: AsyncClient) -> None:
    """Verify the root page renders the step and reset controls used by the simulation UI."""
    async with _client as client:
        resp = await client.get("/")

    assert resp.status_code == 200
    assert "⏭ Step" in resp.text
    assert "↺ Reset" in resp.text


@pytest.mark.asyncio
async def test_api_simulation_status_requires_loaded_loop(_client: AsyncClient) -> None:
    """Verify simulation status returns 400 until a scenario has been loaded."""
    async with _client as client:
        resp = await client.get("/api/simulation/status")

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_api_simulation_start_pause_resume_flow(
    _client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify start/pause/status transitions and repeated start behavior are reported correctly."""
    config = config_builder()
    async with _client as client:
        load_resp = await client.post("/api/scenario/load", json=config.model_dump(mode="json"))
        assert load_resp.status_code == 200

        htmx_start_resp = await client.post("/api/simulation/start", headers={"HX-Request": "true"})
        assert htmx_start_resp.status_code == 200
        assert "sim-status" in htmx_start_resp.text

        reset_loaded_resp = await client.post("/api/simulation/reset")
        assert reset_loaded_resp.status_code == 200
        assert reset_loaded_resp.json()["tick"] == 0

        start_resp = await client.post("/api/simulation/start")
        assert start_resp.status_code == 200
        assert start_resp.json()["message"] == "Simulation started."

        reload_resp = await client.post("/api/scenario/load", json=config.model_dump(mode="json"))
        assert reload_resp.status_code == 200

        running_resp = await client.post("/api/simulation/start")
        assert running_resp.status_code == 200
        assert running_resp.json()["message"] == "Simulation started."

        assert api_main._sim_loop is not None
        api_main._sim_loop.start()
        already_running_resp = await client.post("/api/simulation/start")
        assert already_running_resp.status_code == 200
        assert already_running_resp.json()["message"] == "Simulation already running."

        pause_resp = await client.post("/api/simulation/pause")
        assert pause_resp.status_code == 200
        assert pause_resp.json()["message"] == "Simulation paused."

        status_resp = await client.get("/api/simulation/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["paused"] is True


@pytest.mark.asyncio
async def test_api_simulation_step_increments_tick(
    _client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify a manual step increments tick state once a scenario is loaded."""
    async with _client as client:
        await client.post("/api/scenario/load", json=config_builder().model_dump(mode="json"))
        step_resp = await client.post("/api/simulation/step")

    assert step_resp.status_code == 200
    assert step_resp.json()["tick"] >= 1


@pytest.mark.asyncio
async def test_api_simulation_reset_restores_tick_zero(
    _client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify reset returns tick zero and status reflects the reset state."""
    async with _client as client:
        await client.post("/api/scenario/load", json=config_builder().model_dump(mode="json"))
        await client.post("/api/simulation/step")
        reset_resp = await client.post("/api/simulation/reset")
        status_resp = await client.get("/api/simulation/status")

    assert reset_resp.status_code == 200
    assert reset_resp.json()["tick"] == 0
    assert status_resp.status_code == 200
    assert status_resp.json()["tick"] == 0


@pytest.mark.asyncio
async def test_api_simulation_wind_update_round_trip(
    _client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify wind updates are applied and returned by the simulation control route."""
    async with _client as client:
        await client.post("/api/scenario/load", json=config_builder().model_dump(mode="json"))
        wind_resp = await client.put("/api/simulation/wind", json={"wind_x": 1.5, "wind_y": -0.5})

    assert wind_resp.status_code == 200
    assert wind_resp.json()["wind_x"] == pytest.approx(1.5)
    assert wind_resp.json()["wind_y"] == pytest.approx(-0.5)


@pytest.mark.asyncio
async def test_api_telemetry_exports_include_tick_field(
    _client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify telemetry export endpoints return tick data once telemetry has been recorded."""
    async with _client as client:
        await client.post("/api/scenario/load", json=config_builder().model_dump(mode="json"))
        assert api_main._sim_loop is not None
        api_main._sim_loop.telemetry.record(api_main._sim_loop.world, tick=0)
        csv_resp = await client.get("/api/telemetry/export/csv")
        json_resp = await client.get("/api/telemetry/export/json")

    assert csv_resp.status_code == 200
    assert "tick" in csv_resp.text
    assert json_resp.status_code == 200
    assert '"tick":0' in json_resp.text.replace(" ", "")


@pytest.mark.asyncio
async def test_api_simulation_rejects_commands_when_terminated(
    _client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify start is rejected once the simulation loop has terminated."""
    async with _client as client:
        await client.post("/api/scenario/load", json=config_builder().model_dump(mode="json"))
        assert api_main._sim_loop is not None
        api_main._sim_loop.terminated = True
        api_main._sim_loop.running = False
        api_main._sim_loop.termination_reason = "manual test"
        terminated_resp = await client.post("/api/simulation/start")

    assert terminated_resp.status_code == 400


@pytest.mark.asyncio
async def test_http_middleware_logs_ui_and_api_requests(
    _client: AsyncClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify middleware emits warning and request log lines for UI and unloaded API access."""
    with caplog.at_level(logging.WARNING):
        async with _client as client:
            root_resp = await client.get("/")
            missing_resp = await client.get("/api/simulation/status")

    assert root_resp.status_code == 200
    assert missing_resp.status_code == 400
    assert "Simulation access requested before a scenario was loaded" in caplog.text
    assert "HTTP GET /api/simulation/status -> 400" in caplog.text


@pytest.mark.asyncio
async def test_scenario_import_export_endpoints_roundtrip(
    _client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify scenario import accepts valid JSON and export returns expected core fields."""
    async with _client as client:
        config = config_builder()
        import_resp = await client.post(
            "/api/scenario/import",
            files={
                "file": (
                    "scenario.json",
                    json.dumps(config.model_dump(mode="json")),
                    "application/json",
                )
            },
        )
        assert import_resp.status_code == 200

        export_resp = await client.get("/api/scenario/export")
        assert export_resp.status_code == 200
        exported = json.loads(export_resp.text)
        assert exported["grid_width"] == config.grid_width
        assert exported["herbivore_species"][0]["name"] == "herbivore"


@pytest.mark.asyncio
async def test_scenario_import_rejects_invalid_json(_client: AsyncClient) -> None:
    """Verify scenario import returns 422 for malformed JSON uploads."""
    async with _client as client:
        resp = await client.post(
            "/api/scenario/import",
            files={"file": ("broken.json", "{not valid json", "application/json")},
        )

    assert resp.status_code == 422
