"""
Integration coverage for PHIDS HTMX/UI routes and dashboard helpers.

This module implements integration tests for the PHIDS HTMX-driven UI routes and dashboard helpers. The test suite verifies the correctness of server-side draft state mutation, scenario loading, placement editing, and dashboard rendering, ensuring compliance with deterministic simulation logic, double-buffered state management, and O(1) spatial hash invariants. Each test function is documented to state the invariant or biological behavior being verified and its scientific rationale, supporting reproducible and rigorous validation of emergent ecological dynamics and UI interactions. The module-level docstring is written in accordance with Google-style documentation standards, providing a comprehensive scholarly abstract of the test suite's scope and scientific rationale.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from phids.api import main as api_main
from phids.api.main import app
from phids.api.schemas import BatchJobState
from phids.api.ui_state import SubstanceDefinition, get_draft, reset_draft


def _default_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    """
    Resets the draft and live simulation loop state between UI tests to ensure deterministic reproducibility.

    This fixture enforces a clean simulation environment for each test, preventing cross-test contamination of mutable draft state and live simulation loop. By resetting the draft and nullifying the simulation loop and task, the fixture guarantees that each test operates on a pristine state, thereby upholding the scientific rigor required for reproducible validation of emergent ecological dynamics and UI interactions in PHIDS.
    """
    reset_draft()
    api_main._sim_loop = None
    api_main._sim_task = None


@pytest.mark.asyncio
async def test_root_returns_full_html() -> None:
    """
    Validates that the root endpoint returns a complete HTML workspace for the PHIDS UI.

    This test ensures that the main workspace, diagnostics rail, and upload scenario elements are present in the HTML response, confirming the integrity of the HTMX-driven UI. The presence of these elements is critical for user interaction, scenario management, and diagnostics, supporting the scientific workflow of ecosystem simulation and analysis.
    """
    async with _default_client() as client:
        resp = await client.get("/")

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert 'id="main-workspace"' in resp.text
    assert 'id="diagnostics-rail"' in resp.text
    assert 'id="diagnostics-content"' in resp.text
    assert "phidsUploadScenario" in resp.text
    assert "/api/scenario/load-draft" in resp.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "marker"),
    [
        ("/ui/dashboard", "biotope-canvas"),
        ("/ui/placements", "placement-canvas"),
        ("/ui/biotope", "biotope-config-view"),
        ("/ui/flora", "flora-config-view"),
        ("/ui/predators", "predator-config-view"),
        ("/ui/substances", "substance-config-view"),
        ("/ui/diet-matrix", "diet-matrix-view"),
        ("/ui/trigger-rules", "trigger-rules-view"),
        ("/ui/batch", "Monte Carlo Batch Runner"),
    ],
)
async def test_ui_partials_render(path: str, marker: str) -> None:
    """
    Verifies that each UI partial endpoint renders the expected canvas or configuration view.

    This test suite systematically checks the rendering of dashboard and configuration views for biotope, flora, predators, substances, diet matrix, and trigger rules. The presence of specific markers in the HTML response confirms that the UI correctly exposes the configuration and visualization surfaces necessary for deterministic scenario editing and ecological simulation, supporting rigorous scientific experimentation.
    """
    async with _default_client() as client:
        resp = await client.get(path)

    assert resp.status_code == 200
    assert marker in resp.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/ui/diagnostics/model",
        "/ui/diagnostics/frontend",
        "/ui/diagnostics/backend",
    ],
)
async def test_diagnostics_tabs_render(path: str) -> None:
    """
    Ensures that diagnostics tab endpoints render the diagnostics content for model, frontend, and backend.

    This test validates the accessibility and rendering of diagnostics views, which are essential for monitoring simulation health, model correctness, and backend/frontend integration. The presence of diagnostics content in the response supports the scientific requirement for transparent telemetry and error reporting in PHIDS.
    """
    async with _default_client() as client:
        resp = await client.get(path)

    assert resp.status_code == 200
    assert "diagnostics" in resp.text.lower()


@pytest.mark.asyncio
async def test_ui_status_helpers_render_without_loaded_simulation() -> None:
    """
    Confirms that UI status helpers render correctly when no simulation is loaded.

    This test checks the tick, status badge, and telemetry endpoints for correct responses in the absence of a loaded simulation. The test ensures that the UI accurately reflects the idle state, supporting the scientific principle of deterministic state reporting and user feedback in ecosystem simulation workflows.
    """
    async with _default_client() as client:
        tick_resp = await client.get("/api/ui/tick")
        status_resp = await client.get("/api/ui/status-badge")
        telemetry_resp = await client.get("/api/telemetry")

    assert tick_resp.status_code == 200
    assert tick_resp.text == "0"
    assert status_resp.status_code == 200
    assert "Idle" in status_resp.text
    assert telemetry_resp.status_code == 200
    assert "No telemetry data yet" in telemetry_resp.text


@pytest.mark.asyncio
async def test_table_preview_route_renders_empty_state_without_loaded_simulation() -> None:
    """Confirms telemetry table preview fragment reports an informative empty-state message."""
    async with _default_client() as client:
        resp = await client.get("/api/telemetry/table_preview")

    assert resp.status_code == 200
    assert "No telemetry data available" in resp.text


@pytest.mark.asyncio
async def test_dashboard_contains_extended_telemetry_canvases() -> None:
    """Ensures the dashboard partial exposes defense and biomass telemetry canvases."""
    async with _default_client() as client:
        resp = await client.get("/ui/dashboard")

    assert resp.status_code == 200
    assert 'id="ts-chart"' in resp.text
    assert 'id="defense-chart"' in resp.text
    assert 'id="biomass-chart"' in resp.text


@pytest.mark.asyncio
async def test_batch_view_renders_survival_chart_when_summary_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validates that the batch aggregate fragment includes the survival probability chart canvas."""
    job_id = "jobtest01"
    draft = get_draft()
    draft.active_batch_jobs[job_id] = BatchJobState(
        job_id=job_id,
        status="done",
        completed=2,
        total=2,
        scenario_name="smoke",
        started_at="now",
        max_ticks=4,
    )

    summary = {
        "ticks": [0, 1, 2, 3],
        "flora_population_mean": [10.0, 8.0, 6.0, 4.0],
        "flora_population_std": [0.0, 0.5, 0.5, 1.0],
        "predator_population_mean": [2.0, 3.0, 4.0, 5.0],
        "predator_population_std": [0.0, 0.5, 0.5, 1.0],
        "survival_probability_curve": [1.0, 1.0, 0.5, 0.5],
        "extinction_probability": 0.5,
        "runs_completed": 2,
    }
    batch_dir = tmp_path / "batches"
    batch_dir.mkdir(parents=True, exist_ok=True)
    (batch_dir / f"{job_id}_summary.json").write_text(json.dumps(summary), encoding="utf-8")
    monkeypatch.setattr(api_main, "_BATCH_DIR", batch_dir)

    async with _default_client() as client:
        resp = await client.get(f"/api/batch/view/{job_id}")

    assert resp.status_code == 200
    assert "batch-survival-chart" in resp.text
    assert "batch-table-preview" in resp.text
    assert "batch-export-stride" in resp.text


@pytest.mark.asyncio
async def test_export_route_accepts_metabolic_alias_and_returns_tikz() -> None:
    """Validates that the metabolic alias resolves to defense-economy export generation."""
    draft = get_draft()
    draft.add_plant_placement(0, 2, 2, 20.0)
    draft.add_swarm_placement(0, 2, 2, 5, 20.0)

    async with _default_client() as client:
        load_resp = await client.post("/api/scenario/load-draft")
        assert load_resp.status_code == 200
        await client.post("/api/simulation/step")
        resp = await client.get("/api/export/metabolic", params={"format": "tex_tikz"})

    assert resp.status_code == 200
    assert "Metabolic Defense Economy" in resp.text


@pytest.mark.asyncio
async def test_export_route_rejects_non_positive_tick_interval() -> None:
    """Ensures telemetry export returns HTTP 400 when tick_interval is below 1."""
    draft = get_draft()
    draft.add_plant_placement(0, 1, 1, 10.0)
    draft.add_swarm_placement(0, 1, 1, 3, 12.0)

    async with _default_client() as client:
        load_resp = await client.post("/api/scenario/load-draft")
        assert load_resp.status_code == 200
        resp = await client.get(
            "/api/export/timeseries",
            params={"format": "csv", "tick_interval": 0},
        )

    assert resp.status_code == 400
    assert "tick_interval" in resp.text


@pytest.mark.asyncio
async def test_placement_preview_data_includes_root_links() -> None:
    """
    Validates that placement preview data includes mycorrhizal root links and correct plant/swarm attributes.

    This test ensures that the placement preview endpoint returns data reflecting plant and swarm placements, including mycorrhizal links. The test supports the scientific requirement for accurate visualization and analysis of root network connectivity and population attributes in draft scenarios, facilitating reproducible ecological experimentation.
    """
    draft = get_draft()
    draft.add_plant_placement(0, 4, 4, 12.0)
    draft.add_plant_placement(0, 4, 5, 11.0)
    draft.add_swarm_placement(0, 4, 4, 7, 20.0)

    async with _default_client() as client:
        resp = await client.get("/api/config/placements/data")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["plants"][0]["x"] == 4
    assert payload["swarms"][0]["population"] == 7
    assert payload["mycorrhizal_links"][0]["x1"] == 4
    assert payload["mycorrhizal_links"][0]["y2"] == 5


@pytest.mark.asyncio
async def test_ui_cell_details_returns_draft_preview_payload_with_mycorrhiza() -> None:
    """
    Ensures that cell details endpoint returns draft preview payload including mycorrhizal connections.

    This test verifies that the cell details endpoint provides draft mode data with correct plant, swarm, and mycorrhizal connection attributes. The test supports the scientific requirement for transparent reporting of root network connectivity and population attributes in draft scenarios, facilitating rigorous ecological analysis and scenario design.
    """
    draft = get_draft()
    draft.add_plant_placement(0, 1, 2, 15.0)
    draft.add_plant_placement(0, 1, 3, 14.0)
    draft.add_swarm_placement(0, 1, 2, 7, 30.0)

    async with _default_client() as client:
        resp = await client.get("/api/ui/cell-details", params={"x": 1, "y": 2})

    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "draft"
    assert data["plants"][0]["name"] == "Grass"
    assert data["plants"][0]["mycorrhizal_connections"] == 1
    assert data["plants"][0]["mycorrhizal_neighbours"][0]["y"] == 3
    assert data["mycorrhiza"]["link_count"] == 1
    assert data["swarms"][0]["name"] == "Herbivore"


@pytest.mark.asyncio
async def test_biotope_config_updates_and_clamps_mycorrhizal_growth_interval() -> None:
    """
    Validates that biotope configuration updates clamp mycorrhizal growth interval to minimum value.

    This test ensures that the biotope configuration endpoint enforces a minimum value for mycorrhizal growth interval ticks, supporting the scientific requirement for deterministic parameter validation and ecological realism in simulation configuration.
    """
    async with _default_client() as client:
        resp = await client.post(
            "/api/config/biotope",
            data={
                "grid_width": 40,
                "grid_height": 40,
                "max_ticks": 1000,
                "tick_rate_hz": 10.0,
                "wind_x": 0.0,
                "wind_y": 0.0,
                "num_signals": 4,
                "num_toxins": 4,
                "mycorrhizal_connection_cost": 1.0,
                "mycorrhizal_growth_interval_ticks": 0,
                "mycorrhizal_signal_velocity": 1,
            },
        )

    assert resp.status_code == 200
    assert 'name="mycorrhizal_growth_interval_ticks"' in resp.text
    assert 'value="1"' in resp.text
    assert get_draft().mycorrhizal_growth_interval_ticks == 1


@pytest.mark.asyncio
async def test_live_dashboard_payload_and_cell_details_include_signals_and_links(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Validates that live dashboard payload and cell details include signals, mycorrhizal links, and triggered substances.

    This test simulates a live scenario with plant and swarm placements, trigger rules, and substance definitions. It verifies that the dashboard and cell details endpoints report active signals, mycorrhizal links, and triggered/aftereffect states for substances, supporting the scientific requirement for transparent reporting of emergent ecological dynamics and signal propagation in PHIDS.
    """
    monkeypatch.setattr(
        "phids.engine.systems.interaction._choose_neighbour_by_flow_probability",
        lambda x, y, flow_field, width, height, invert=False: (x, y),
    )

    draft = get_draft()
    draft.add_plant_placement(0, 2, 2, 18.0)
    draft.add_plant_placement(0, 2, 3, 16.0)
    draft.add_swarm_placement(0, 2, 2, 6, 24.0)
    draft.diet_matrix[0][0] = False
    draft.mycorrhizal_growth_interval_ticks = 1
    draft.substance_definitions.append(
        SubstanceDefinition(
            substance_id=0,
            name="Alarm Cloud",
            is_toxin=False,
            synthesis_duration=1,
            aftereffect_ticks=2,
        )
    )
    draft.add_trigger_rule(0, 0, 0, min_predator_population=5)

    async with _default_client() as client:
        load_resp = await client.post("/api/scenario/load-draft", headers={"HX-Request": "true"})
        assert load_resp.status_code == 200

        step_resp = await client.post("/api/simulation/step")
        assert step_resp.status_code == 200

        dashboard_payload = api_main._build_live_dashboard_payload(api_main._sim_loop)
        details_resp = await client.get("/api/ui/cell-details", params={"x": 2, "y": 2})

        from phids.engine.components.swarm import SwarmComponent

        loop = api_main._sim_loop
        assert loop is not None
        swarm_entity = next(iter(loop.world.query(SwarmComponent)))
        swarm = swarm_entity.get_component(SwarmComponent)
        loop.world.move_entity(swarm.entity_id, swarm.x, swarm.y, 0, 0)
        swarm.x = 0
        swarm.y = 0

        second_step_resp = await client.post("/api/simulation/step")
        assert second_step_resp.status_code == 200
        aftereffect_details_resp = await client.get("/api/ui/cell-details", params={"x": 2, "y": 2})

    assert dashboard_payload["tick"] == 1
    assert any(0 in plant["active_signal_ids"] for plant in dashboard_payload["plants"])
    assert dashboard_payload["mycorrhizal_links"]
    assert details_resp.status_code == 200
    details = details_resp.json()
    assert details["mode"] == "live"
    assert details["tick"] == 1
    assert details["signal_concentrations"]
    triggered_alarm_clouds = [
        substance
        for plant in details["plants"]
        for substance in plant["active_substances"]
        if substance["name"] == "Alarm Cloud"
    ]
    assert any(substance["state"] == "triggered" for substance in triggered_alarm_clouds)
    assert details["mycorrhiza"]["link_count"] == 1
    assert details["swarms"][0]["population"] >= 6

    assert aftereffect_details_resp.status_code == 200
    aftereffect_details = aftereffect_details_resp.json()
    assert aftereffect_details["tick"] == 2
    assert aftereffect_details["signal_concentrations"]
    lingering_alarm_clouds = [
        substance
        for plant in aftereffect_details["plants"]
        for substance in plant["active_substances"]
        if substance["name"] == "Alarm Cloud"
    ]
    assert any(substance["state"] == "aftereffect" for substance in lingering_alarm_clouds)
    assert any(
        substance["state"] == "aftereffect" and substance["aftereffect_remaining_ticks"] == 1
        for substance in lingering_alarm_clouds
    )


@pytest.mark.asyncio
async def test_ui_cell_details_rejects_stale_live_tick() -> None:
    """
    Ensures that cell details endpoint rejects requests with stale expected tick in live mode.

    This test verifies that the cell details endpoint returns a 409 status and correct tick information when the expected tick is stale, supporting the scientific requirement for deterministic state synchronization and error reporting in live simulation scenarios.
    """
    draft = get_draft()
    draft.add_plant_placement(0, 3, 3, 20.0)
    draft.add_swarm_placement(0, 3, 3, 5, 20.0)

    async with _default_client() as client:
        load_resp = await client.post("/api/scenario/load-draft")
        assert load_resp.status_code == 200

        step_resp = await client.post("/api/simulation/step")
        assert step_resp.status_code == 200

        resp = await client.get(
            "/api/ui/cell-details",
            params={"x": 3, "y": 3, "expected_tick": 0},
        )

    assert resp.status_code == 409
    data = resp.json()
    assert data["expected_tick"] == 0
    assert data["tick"] == 1


@pytest.mark.asyncio
async def test_model_diagnostics_and_telemetry_refresh_context() -> None:
    """
    Validates that model diagnostics and telemetry endpoints refresh context after simulation step.

    This test ensures that the diagnostics and telemetry endpoints report updated context after a simulation step, supporting the scientific requirement for transparent reporting of simulation progress, plant death diagnostics, and energy deficit watch in PHIDS.
    """
    draft = get_draft()
    draft.add_plant_placement(0, 5, 5, 17.0)
    draft.add_swarm_placement(0, 5, 5, 8, 32.0)

    async with _default_client() as client:
        await client.post("/api/scenario/load-draft")
        await client.post("/api/simulation/step")
        model_resp = await client.get("/ui/diagnostics/model")
        telemetry_resp = await client.get("/api/telemetry")

    assert model_resp.status_code == 200
    assert "Latest telemetry" in model_resp.text
    assert "Plant death diagnostics" in model_resp.text
    assert "Energy deficit watch" in model_resp.text
    assert telemetry_resp.status_code == 200
    assert "tick 1" in telemetry_resp.text


@pytest.mark.asyncio
async def test_backend_diagnostics_shows_recent_logs() -> None:
    """
    Ensures that backend diagnostics endpoint displays recent logs for UI diagnostics.

    This test validates that the backend diagnostics endpoint exposes recent log entries, supporting the scientific requirement for transparent error reporting and backend health monitoring in PHIDS UI diagnostics workflows.
    """
    api_main.logger.info("UI diagnostics backend smoke test")

    async with _default_client() as client:
        resp = await client.get("/ui/diagnostics/backend")

    assert resp.status_code == 200
    assert "Recent logs" in resp.text
    assert "UI diagnostics backend smoke test" in resp.text


@pytest.mark.asyncio
async def test_scenario_export_and_import_round_trip_ui() -> None:
    """
    Validates scenario export and import round-trip functionality via the UI endpoints.

    This test ensures that the scenario export and import endpoints correctly serialize and deserialize scenario state, preserving mycorrhizal growth interval and placement attributes. The test supports the scientific requirement for reproducible scenario management and state persistence in PHIDS ecosystem simulation workflows.
    """
    export_path = Path("/tmp/phids-ui-test.json")
    draft = get_draft()
    draft.add_plant_placement(0, 2, 2, 10.0)
    draft.add_swarm_placement(0, 2, 2, 5, 18.0)
    draft.mycorrhizal_growth_interval_ticks = 13

    async with _default_client() as client:
        export_resp = await client.get("/api/scenario/export")
        assert export_resp.status_code == 200
        export_path.write_bytes(export_resp.content)

        with export_path.open("rb") as fh:
            import_resp = await client.post(
                "/api/scenario/import",
                files={"file": ("roundtrip.json", fh, "application/json")},
            )

    assert import_resp.status_code == 200
    assert import_resp.json()["message"] == "Scenario imported."
    assert get_draft().mycorrhizal_growth_interval_ticks == 13
