"""Coverage reinforcement tests for presenter helpers and telemetry export branches.

This module adds targeted regression checks for branches that are operationally important
but historically under-exercised by broad integration tests. The hypotheses validate that
dashboard presenter helpers preserve deterministic behavior, and that
telemetry export endpoints handle both nominal and failure conditions with explicit HTTP
semantics. These checks improve statistical confidence that operator-facing analytical
surfaces remain stable under edge-case parameterizations and absent-runtime states.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from phids.api import main as api_main
from phids.api.main import app
from phids.api.presenters.dashboard import (
    build_live_cell_details,
    build_live_dashboard_payload,
    build_preview_cell_details,
)
from phids.api.services.draft_service import DraftService
from phids.api.ui_state import (
    DraftState,
    SubstanceDefinition,
    get_draft,
    reset_draft,
)
from phids.engine.components.swarm import SwarmComponent
from phids.engine.loop import SimulationLoop

draft_service = DraftService()


@pytest.fixture(autouse=True)
def _reset_global_state() -> None:
    """Reset mutable API singletons between tests.

    The API layer maintains process-global references for the draft state and active simulation
    loop. Resetting these references before each test preserves deterministic reproducibility and
    prevents cross-test leakage in route behavior.
    """
    reset_draft()
    api_main._sim_loop = None
    api_main._sim_task = None


def _default_client() -> AsyncClient:
    """Create an in-process HTTP client bound to the FastAPI application."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _build_loaded_loop() -> SimulationLoop:
    """Construct and register a minimal simulation loop with one plant and one swarm.

    Returns:
        The initialized simulation loop bound to ``api_main._sim_loop``.
    """
    draft = get_draft()
    draft_service.add_plant_placement(draft, 0, 2, 2, 12.0)
    draft_service.add_swarm_placement(draft, 0, 2, 2, 4, 8.0)
    loop = SimulationLoop(draft.build_sim_config())
    api_main._sim_loop = loop
    return loop


def test_main_numeric_coercion_helpers_cover_all_input_branches() -> None:
    """Validate coercion behavior across bool, numeric, parsable string, and invalid inputs.

    These helper functions are used in ranking and payload sanitation paths. Deterministic
    coercion avoids unstable ordering or serialization errors when optional fields include
    heterogeneous scalar values.
    """
    assert api_main._coerce_int(True, default=-9) == -9
    assert api_main._coerce_int(7) == 7
    assert api_main._coerce_int(4.8) == 4
    assert api_main._coerce_int("12") == 12
    assert api_main._coerce_int("bad", default=5) == 5

    assert api_main._coerce_float(False, default=3.5) == 3.5
    assert api_main._coerce_float(2) == pytest.approx(2.0)
    assert api_main._coerce_float(2.75) == pytest.approx(2.75)
    assert api_main._coerce_float("1.25") == pytest.approx(1.25)
    assert api_main._coerce_float("x", default=9.0) == pytest.approx(9.0)


def test_main_default_activation_condition_and_trigger_index_branches() -> None:
    """Validate default-condition synthesis and index guarding for trigger-rule editing paths.

    The trigger-rule editor builds default condition nodes by kind and must reject unsupported
    node labels. The index accessor must raise a 404 sentinel for out-of-range references.
    """
    draft = DraftState.default()
    draft_service.add_trigger_rule(
        draft,
        flora_species_id=0,
        predator_species_id=0,
        substance_id=0,
        min_predator_population=2,
    )
    draft.substance_definitions.append(
        SubstanceDefinition(
            substance_id=1,
            name="Signal-1",
            is_toxin=False,
            synthesis_duration=1,
            aftereffect_ticks=0,
        )
    )
    rule = draft.trigger_rules[0]

    env_signal = api_main._default_activation_condition_for_rule(
        draft, rule, "environmental_signal"
    )
    assert env_signal["kind"] == "environmental_signal"
    assert env_signal["signal_id"] == 0

    any_of = api_main._default_activation_condition_for_rule(draft, rule, "any_of")
    assert any_of["kind"] == "any_of"
    assert any_of["conditions"][0]["kind"] == "enemy_presence"

    substance_active = api_main._default_activation_condition_for_rule(
        draft,
        rule,
        "substance_active",
    )
    assert substance_active["substance_id"] == 1

    with pytest.raises(HTTPException) as unsupported:
        api_main._default_activation_condition_for_rule(draft, rule, "invalid")
    assert unsupported.value.status_code == 400

    with pytest.raises(HTTPException) as not_found:
        api_main._trigger_rule_by_index(draft, 99)
    assert not_found.value.status_code == 404


def test_presenter_payload_helpers_status_badge_and_energy_deficit() -> None:
    """Exercise presenter payload helpers and status/energy helper branches.

    The test verifies that presenter payload builders return structurally valid dictionaries
    and that swarm energy-deficit ranking excludes satiated swarms while retaining stressed ones.
    """
    draft = get_draft()
    draft_service.add_plant_placement(draft, 0, 2, 2, 12.0)
    draft_service.add_swarm_placement(draft, 0, 2, 2, 4, 30.0)
    draft_service.add_swarm_placement(draft, 0, 3, 3, 4, 1.0)
    loop = SimulationLoop(draft.build_sim_config())
    api_main._sim_loop = loop

    for entity in loop.world.query(SwarmComponent):
        swarm = entity.get_component(SwarmComponent)
        if swarm.x == 3 and swarm.y == 3:
            swarm.energy = 0.0

    live_cell = build_live_cell_details(loop, 2, 2, substance_names=api_main._sim_substance_names)
    preview_cell = build_preview_cell_details(
        2,
        2,
        draft=get_draft(),
        substance_names=api_main._sim_substance_names,
    )
    dashboard = build_live_dashboard_payload(loop, substance_names=api_main._sim_substance_names)

    assert live_cell["mode"] == "live"
    assert preview_cell["mode"] == "draft"
    assert "species_energy" in dashboard

    stressed = api_main._build_energy_deficit_swarms()
    assert len(stressed) == 1
    assert stressed[0]["energy_deficit"] > 0.0

    api_main._sim_loop = None
    assert api_main._render_status_badge_html().find("Idle") != -1

    api_main._sim_loop = loop
    assert "Loaded" in api_main._render_status_badge_html()
    loop.running = True
    assert "Running" in api_main._render_status_badge_html()
    loop.paused = True
    assert "Paused" in api_main._render_status_badge_html()
    loop.terminated = True
    assert "Terminated" in api_main._render_status_badge_html()


@pytest.mark.asyncio
async def test_telemetry_chartjs_and_table_preview_empty_branches() -> None:
    """Cover no-loop chart JSON and filtered-empty table preview response branches.

    The telemetry API must return explicit empty payloads when no loop is loaded and provide
    informative empty-state HTML when filters remove all candidate rows.
    """
    async with _default_client() as client:
        no_loop_chart = await client.get("/api/telemetry/chartjs-data")
    assert no_loop_chart.status_code == 200
    assert no_loop_chart.json() == {"labels": [], "flora_ids": [], "predator_ids": [], "series": {}}

    loop = _build_loaded_loop()
    loop.telemetry._rows = []

    async with _default_client() as client:
        filtered_empty = await client.get(
            "/api/telemetry/table_preview",
            params={"flora_ids": "99", "limit": 5},
        )
    assert filtered_empty.status_code == 200
    assert "No rows match current table filters" in filtered_empty.text


@pytest.mark.asyncio
async def test_export_route_error_and_format_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate export error semantics and multi-format response branches.

    The export endpoint must provide deterministic HTTP errors for invalid runtime state,
    analytical projections, and rendering backends, while still producing file attachments
    for supported formats.
    """
    async with _default_client() as client:
        no_loop = await client.get("/api/export/timeseries", params={"format": "csv"})
    assert no_loop.status_code == 404

    loop = _build_loaded_loop()
    await loop.step()

    async with _default_client() as client:
        bad_type = await client.get("/api/export/unknown", params={"format": "csv"})
        bad_interval = await client.get(
            "/api/export/timeseries", params={"format": "csv", "tick_interval": 0}
        )
        csv_resp = await client.get("/api/export/metabolic", params={"format": "csv"})
        tex_table_resp = await client.get("/api/export/timeseries", params={"format": "tex_table"})
        bad_format = await client.get("/api/export/timeseries", params={"format": "bad"})

    assert bad_type.status_code == 400
    assert "Unknown data_type" in bad_type.text
    assert bad_interval.status_code == 400
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["content-type"]
    assert "phids_defense_economy.csv" in csv_resp.headers["content-disposition"]
    assert tex_table_resp.status_code == 200
    assert "phids_timeseries_table.tex" in tex_table_resp.headers["content-disposition"]
    assert bad_format.status_code == 400

    def _raise_tikz(*args: object, **kwargs: object) -> str:
        raise ValueError("tikz failed")

    def _raise_png(*args: object, **kwargs: object) -> bytes:
        raise ValueError("png failed")

    monkeypatch.setattr("phids.api.routers.telemetry.generate_tikz_str", _raise_tikz)
    monkeypatch.setattr("phids.api.routers.telemetry.generate_png_bytes", _raise_png)

    async with _default_client() as client:
        tikz_fail = await client.get("/api/export/timeseries", params={"format": "tex_tikz"})
        png_fail = await client.get("/api/export/timeseries", params={"format": "png"})

    assert tikz_fail.status_code == 400
    assert "tikz failed" in tikz_fail.text
    assert png_fail.status_code == 400
    assert "png failed" in png_fail.text


def test_htmx_request_detection_branch() -> None:
    """Validate HTMX request detection for true and false header states."""
    from starlette.requests import Request

    true_scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"hx-request", b"true")],
    }
    false_scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
    }

    async def _receive() -> dict[str, object]:
        return {"type": "http.request"}

    assert api_main._is_htmx_request(Request(true_scope, _receive)) is True
    assert api_main._is_htmx_request(Request(false_scope, _receive)) is False
