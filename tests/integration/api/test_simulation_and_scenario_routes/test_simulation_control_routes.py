# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Integration checks for simulation-control HTTP routes.

This module isolates API-surface regressions for simulation control, telemetry export, middleware
logging, and scenario import/export behavior. Each test validates one transition or one endpoint
contract so that failures localize to a single route family instead of cascading through unrelated
state mutations.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

import phids.api.main as api_main
from phids.api.schemas.simulation import SimulationConfig

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient


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
    """Verify single-stepping advances simulation time and updates tick counts."""
    config = config_builder(max_ticks=5)
    load_resp = await api_client.post("/api/scenario/load", json=config.model_dump(mode="json"))
    assert load_resp.status_code == 200, load_resp.text

    step_resp = await api_client.post("/api/simulation/step")
    assert step_resp.status_code == 200, step_resp.text
    assert step_resp.json()["tick"] == 1


@pytest.mark.asyncio
async def test_api_simulation_reset_restores_tick_zero(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify reset restores the loaded configuration to tick 0."""
    config = config_builder(max_ticks=5)
    load_resp = await api_client.post("/api/scenario/load", json=config.model_dump(mode="json"))
    assert load_resp.status_code == 200, load_resp.text

    await api_client.post("/api/simulation/step")
    reset_resp = await api_client.post("/api/simulation/reset")
    assert reset_resp.status_code == 200, reset_resp.text
    assert reset_resp.json()["tick"] == 0

    status_resp = await api_client.get("/api/simulation/status")
    assert status_resp.status_code == 200, status_resp.text
    assert status_resp.json()["tick"] == 0


@pytest.mark.asyncio
async def test_api_simulation_wind_update_round_trip(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify wind updates are applied and returned by the simulation control route."""
    load_resp = await api_client.post("/api/scenario/load", json=config_builder().model_dump(mode="json"))
    assert load_resp.status_code == 200, load_resp.text
    wind_resp = await api_client.put("/api/simulation/wind", json={"wind_x": 1.5, "wind_y": -0.5})

    assert wind_resp.status_code == 200, wind_resp.text
    assert wind_resp.json()["wind_x"] == pytest.approx(1.5)
    assert wind_resp.json()["wind_y"] == pytest.approx(-0.5)


@pytest.mark.asyncio
async def test_api_simulation_step_preserves_live_wind_update(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify a direct wind update remains active when stepping without form overrides."""
    load_resp = await api_client.post("/api/scenario/load", json=config_builder().model_dump(mode="json"))
    assert load_resp.status_code == 200, load_resp.text
    wind_resp = await api_client.put("/api/simulation/wind", json={"wind_x": 1.25, "wind_y": -0.5})
    assert wind_resp.status_code == 200, wind_resp.text

    step_resp = await api_client.post("/api/simulation/step")

    assert step_resp.status_code == 200, step_resp.text
    assert api_main._sim_loop is not None
    assert float(api_main._sim_loop.env.wind_vector_x.mean()) == pytest.approx(1.25)
    assert float(api_main._sim_loop.env.wind_vector_y.mean()) == pytest.approx(-0.5)


@pytest.mark.asyncio
async def test_api_simulation_start_preserves_live_tick_rate_update(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify tick-rate changes apply during simulation execution."""
    load_resp = await api_client.post("/api/scenario/load", json=config_builder(max_ticks=5).model_dump(mode="json"))
    assert load_resp.status_code == 200, load_resp.text

    tick_resp = await api_client.put("/api/simulation/tick-rate", data={"tick_rate_hz": 10.0})
    assert tick_resp.status_code == 200, tick_resp.text

    start_resp = await api_client.post("/api/simulation/start")
    assert start_resp.status_code == 200, start_resp.text
    assert start_resp.json()["message"] == "Simulation started."


@pytest.mark.asyncio
async def test_api_simulation_start_rejects_invalid_form_scalar(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify invalid scalar inputs in simulation start form data return 422."""
    load_resp = await api_client.post("/api/scenario/load", json=config_builder(max_ticks=5).model_dump(mode="json"))
    assert load_resp.status_code == 200, load_resp.text

    start_resp = await api_client.post("/api/simulation/start", data={"max_ticks": "invalid"})
    assert start_resp.status_code == 422, start_resp.text


@pytest.mark.asyncio
async def test_api_simulation_start_applies_valid_form_overrides_to_draft(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify form parameters are correctly parsed and updated on start."""
    load_resp = await api_client.post("/api/scenario/load", json=config_builder(max_ticks=5).model_dump(mode="json"))
    assert load_resp.status_code == 200, load_resp.text

    start_resp = await api_client.post(
        "/api/simulation/start",
        data={
            "max_ticks": "15",
            "tick_rate_hz": "10.0",
            "wind_x": "2.0",
            "wind_y": "-1.0",
        },
    )
    assert start_resp.status_code == 200, start_resp.text


@pytest.mark.asyncio
async def test_api_simulation_start_htmx_when_already_running_returns_fragment(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify HTMX requests return HTML status badges when simulation is already running."""
    load_resp = await api_client.post("/api/scenario/load", json=config_builder().model_dump(mode="json"))
    assert load_resp.status_code == 200, load_resp.text

    assert api_main._sim_loop is not None
    api_main._sim_loop.start()

    start_resp = await api_client.post("/api/simulation/start", headers={"HX-Request": "true"})
    assert start_resp.status_code == 200, start_resp.text
    assert "Running" in start_resp.text


@pytest.mark.asyncio
async def test_api_simulation_step_rejects_running_and_terminated_branches(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify step requests are rejected when simulation is running or terminated."""
    load_resp = await api_client.post("/api/scenario/load", json=config_builder().model_dump(mode="json"))
    assert load_resp.status_code == 200, load_resp.text

    assert api_main._sim_loop is not None
    await api_client.post("/api/simulation/start")
    step_resp = await api_client.post("/api/simulation/step")
    assert step_resp.status_code == 400, step_resp.text

    api_main._sim_loop.pause()
    api_main._sim_loop.terminated = True
    term_step_resp = await api_client.post("/api/simulation/step")
    assert term_step_resp.status_code == 400, term_step_resp.text


@pytest.mark.asyncio
async def test_api_simulation_start_rejects_invalid_float_form_scalar(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify invalid float inputs in form payload fall back gracefully with 422."""
    load_resp = await api_client.post("/api/scenario/load", json=config_builder(max_ticks=5).model_dump(mode="json"))
    assert load_resp.status_code == 200, load_resp.text

    start_resp = await api_client.post("/api/simulation/start", data={"tick_rate_hz": "invalid"})
    assert start_resp.status_code == 422, start_resp.text


@pytest.mark.asyncio
async def test_api_simulation_control_routes_return_htmx_status_fragments(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify HTMX control requests return status-badge fragments across pause/step/reset/tick-rate."""
    load_resp = await api_client.post("/api/scenario/load", json=config_builder().model_dump(mode="json"))
    assert load_resp.status_code == 200, load_resp.text

    tick_rate_resp = await api_client.put(
        "/api/simulation/tick-rate",
        data={"tick_rate_hz": 12.0},
        headers={"HX-Request": "true"},
    )
    assert tick_rate_resp.status_code == 200, tick_rate_resp.text
    assert "sim-status" in tick_rate_resp.text

    pause_resp = await api_client.post("/api/simulation/pause", headers={"HX-Request": "true"})
    assert pause_resp.status_code == 200, pause_resp.text
    assert "sim-status" in pause_resp.text

    step_resp = await api_client.post("/api/simulation/step", headers={"HX-Request": "true"})
    assert step_resp.status_code == 200, step_resp.text
    assert "sim-status" in step_resp.text

    reset_resp = await api_client.post("/api/simulation/reset", headers={"HX-Request": "true"})
    assert reset_resp.status_code == 200, reset_resp.text
    assert "sim-status" in reset_resp.text


@pytest.mark.asyncio
async def test_api_telemetry_exports_include_tick_field(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify telemetry export endpoints return tick data once telemetry has been recorded."""
    load_resp = await api_client.post("/api/scenario/load", json=config_builder().model_dump(mode="json"))
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
    load_resp = await api_client.post("/api/scenario/load", json=config_builder().model_dump(mode="json"))
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
