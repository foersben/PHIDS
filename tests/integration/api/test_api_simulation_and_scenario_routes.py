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
from phids.api.schemas import SimulationConfig, TriggerConditionSchema
from phids.api.ui_state import DraftState, get_draft, set_draft


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
async def test_api_simulation_step_preserves_live_wind_update(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify a direct wind update remains active when stepping without form overrides."""
    load_resp = await api_client.post(
        "/api/scenario/load", json=config_builder().model_dump(mode="json")
    )
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
    """Verify tick-rate updates through the live route are retained when start applies draft sync."""
    load_resp = await api_client.post(
        "/api/scenario/load", json=config_builder().model_dump(mode="json")
    )
    assert load_resp.status_code == 200, load_resp.text

    tick_rate_resp = await api_client.put("/api/simulation/tick-rate", data={"tick_rate_hz": 22.5})
    assert tick_rate_resp.status_code == 200, tick_rate_resp.text

    start_resp = await api_client.post("/api/simulation/start")
    assert start_resp.status_code == 200, start_resp.text
    assert api_main._sim_loop is not None
    assert api_main._sim_loop.config.tick_rate_hz == pytest.approx(22.5)


@pytest.mark.asyncio
async def test_api_simulation_start_rejects_invalid_form_scalar(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify malformed form scalars on control routes produce a deterministic 422 response."""
    load_resp = await api_client.post(
        "/api/scenario/load", json=config_builder().model_dump(mode="json")
    )
    assert load_resp.status_code == 200, load_resp.text

    resp = await api_client.post("/api/simulation/start", data={"grid_width": "not-an-int"})

    assert resp.status_code == 422, resp.text
    assert "grid_width" in resp.text


@pytest.mark.asyncio
async def test_api_simulation_start_applies_valid_form_overrides_to_draft(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify valid scalar form fields on start are persisted into draft biotope state."""
    load_resp = await api_client.post(
        "/api/scenario/load", json=config_builder().model_dump(mode="json")
    )
    assert load_resp.status_code == 200, load_resp.text

    resp = await api_client.post(
        "/api/simulation/start",
        data={"grid_width": 17, "tick_rate_hz": 13.5, "mycorrhizal_inter_species": "on"},
    )

    assert resp.status_code == 200, resp.text
    draft = get_draft()
    assert draft.grid_width == 17
    assert draft.tick_rate_hz == pytest.approx(13.5)
    assert draft.mycorrhizal_inter_species is True


@pytest.mark.asyncio
async def test_api_simulation_start_htmx_when_already_running_returns_fragment(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify HTMX start requests while already running return the status-badge fragment path."""
    load_resp = await api_client.post(
        "/api/scenario/load", json=config_builder(max_ticks=200).model_dump(mode="json")
    )
    assert load_resp.status_code == 200, load_resp.text

    start_resp = await api_client.post("/api/simulation/start")
    assert start_resp.status_code == 200, start_resp.text
    assert api_main._sim_task is not None
    assert not api_main._sim_task.done()

    running_htmx = await api_client.post("/api/simulation/start", headers={"HX-Request": "true"})

    assert running_htmx.status_code == 200, running_htmx.text
    assert "sim-status" in running_htmx.text


@pytest.mark.asyncio
async def test_api_simulation_step_rejects_running_and_terminated_branches(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify single-step rejects active-running and terminated loop states with deterministic 400 errors."""
    load_resp = await api_client.post(
        "/api/scenario/load", json=config_builder(max_ticks=200).model_dump(mode="json")
    )
    assert load_resp.status_code == 200, load_resp.text

    start_resp = await api_client.post("/api/simulation/start")
    assert start_resp.status_code == 200, start_resp.text
    assert api_main._sim_task is not None
    assert not api_main._sim_task.done()

    running_step = await api_client.post("/api/simulation/step")
    assert running_step.status_code == 400, running_step.text
    assert "Pause the simulation before stepping" in running_step.text

    pause_resp = await api_client.post("/api/simulation/pause")
    assert pause_resp.status_code == 200, pause_resp.text
    assert api_main._sim_loop is not None
    api_main._sim_loop.terminated = True
    api_main._sim_loop.termination_reason = "test termination"

    terminated_step = await api_client.post("/api/simulation/step")
    assert terminated_step.status_code == 400, terminated_step.text
    assert "Simulation has terminated" in terminated_step.text


@pytest.mark.asyncio
async def test_api_simulation_start_rejects_invalid_float_form_scalar(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify malformed float form scalars on control routes produce deterministic 422 responses."""
    load_resp = await api_client.post(
        "/api/scenario/load", json=config_builder().model_dump(mode="json")
    )
    assert load_resp.status_code == 200, load_resp.text

    resp = await api_client.post("/api/simulation/start", data={"tick_rate_hz": "not-a-float"})

    assert resp.status_code == 422, resp.text
    assert "tick_rate_hz" in resp.text


@pytest.mark.asyncio
async def test_api_simulation_control_routes_return_htmx_status_fragments(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify HTMX control requests return status-badge fragments across pause/step/reset/tick-rate."""
    load_resp = await api_client.post(
        "/api/scenario/load", json=config_builder().model_dump(mode="json")
    )
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
async def test_scenario_import_materializes_trigger_rules_and_substances(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify scenario import reconstructs draft trigger rules and substance definitions from schema triggers."""
    config = config_builder()
    config.flora_species[0] = config.flora_species[0].model_copy(
        update={
            "triggers": [
                TriggerConditionSchema(
                    herbivore_species_id=0,
                    min_herbivore_population=2,
                    substance_id=1,
                    synthesis_duration=3,
                    is_toxin=False,
                )
            ]
        }
    )
    config.num_signals = 2

    import_resp = await api_client.post(
        "/api/scenario/import",
        files={
            "file": (
                "triggered.json",
                json.dumps(config.model_dump(mode="json")),
                "application/json",
            )
        },
    )

    assert import_resp.status_code == 200, import_resp.text

    export_resp = await api_client.get("/api/scenario/export")
    assert export_resp.status_code == 200, export_resp.text
    exported = json.loads(export_resp.text)
    assert len(exported["flora_species"][0]["triggers"]) == 1
    assert exported["flora_species"][0]["triggers"][0]["substance_id"] == 1


@pytest.mark.asyncio
async def test_scenario_export_and_load_draft_fail_for_invalid_draft(
    api_client: AsyncClient,
) -> None:
    """Verify export/load-draft fail with deterministic 400 responses when draft cannot build config."""
    set_draft(DraftState(flora_species=[], herbivore_species=[]))

    export_resp = await api_client.get("/api/scenario/export")
    assert export_resp.status_code == 400, export_resp.text

    load_resp = await api_client.post("/api/scenario/load-draft")
    assert load_resp.status_code == 400, load_resp.text


@pytest.mark.asyncio
async def test_scenario_load_draft_cancels_running_background_task(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify loading draft while a simulation task is running cancels it and returns fresh status HTML."""
    load_resp = await api_client.post(
        "/api/scenario/load", json=config_builder(max_ticks=200).model_dump(mode="json")
    )
    assert load_resp.status_code == 200, load_resp.text

    start_resp = await api_client.post("/api/simulation/start")
    assert start_resp.status_code == 200, start_resp.text
    assert api_main._sim_task is not None
    assert not api_main._sim_task.done()

    draft_load_resp = await api_client.post(
        "/api/scenario/load-draft",
        headers={"HX-Request": "true"},
    )

    assert draft_load_resp.status_code == 200, draft_load_resp.text
    assert "sim-status" in draft_load_resp.text
    assert api_main._sim_task is None
    assert api_main._sim_loop is not None


@pytest.mark.asyncio
async def test_scenario_import_rejects_invalid_json(api_client: AsyncClient) -> None:
    """Verify scenario import returns 422 for malformed JSON uploads."""
    resp = await api_client.post(
        "/api/scenario/import",
        files={"file": ("broken.json", "{not valid json", "application/json")},
    )

    assert resp.status_code == 422, resp.text
