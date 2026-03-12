"""Integration coverage for PHIDS HTMX/UI routes and dashboard helpers."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from phids.api import main as api_main
from phids.api.main import app
from phids.api.ui_state import SubstanceDefinition, get_draft, reset_draft


def _default_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    """Reset draft and live loop between UI tests."""
    reset_draft()
    api_main._sim_loop = None
    api_main._sim_task = None


@pytest.mark.asyncio
async def test_root_returns_full_html() -> None:
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
    ],
)
async def test_ui_partials_render(path: str, marker: str) -> None:
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
    async with _default_client() as client:
        resp = await client.get(path)

    assert resp.status_code == 200
    assert "diagnostics" in resp.text.lower()


@pytest.mark.asyncio
async def test_ui_status_helpers_render_without_loaded_simulation() -> None:
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
async def test_placement_preview_data_includes_root_links() -> None:
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
    assert "Starvation watch" in model_resp.text
    assert telemetry_resp.status_code == 200
    assert "tick 1" in telemetry_resp.text


@pytest.mark.asyncio
async def test_backend_diagnostics_shows_recent_logs() -> None:
    api_main.logger.info("UI diagnostics backend smoke test")

    async with _default_client() as client:
        resp = await client.get("/ui/diagnostics/backend")

    assert resp.status_code == 200
    assert "Recent logs" in resp.text
    assert "UI diagnostics backend smoke test" in resp.text


@pytest.mark.asyncio
async def test_scenario_export_and_import_round_trip_ui() -> None:
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
