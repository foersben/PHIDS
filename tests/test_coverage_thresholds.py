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
from httpx import AsyncClient

from phids.api import main as api_main
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
)
from phids.engine.components.swarm import SwarmComponent
from phids.engine.loop import SimulationLoop

draft_service = DraftService()


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


@pytest.mark.parametrize(
    ("input_val", "kwargs", "expected"),
    [
        (True, {"default": -9}, -9),
        (7, {}, 7),
        (4.8, {}, 4),
        ("12", {}, 12),
        ("bad", {"default": 5}, 5),
    ],
)
def test_main_coerce_int_cases(input_val: object, kwargs: dict[str, int], expected: int) -> None:
    """Validate integer coercion behavior across valid, invalid, and boolean inputs."""
    assert api_main._coerce_int(input_val, **kwargs) == expected


@pytest.mark.parametrize(
    ("input_val", "kwargs", "expected"),
    [
        (False, {"default": 3.5}, 3.5),
        (2, {}, 2.0),
        (2.75, {}, 2.75),
        ("1.25", {}, 1.25),
        ("x", {"default": 9.0}, 9.0),
    ],
)
def test_main_coerce_float_cases(
    input_val: object,
    kwargs: dict[str, float],
    expected: float,
) -> None:
    """Validate floating-point coercion behavior across valid, invalid, and boolean inputs."""
    assert api_main._coerce_float(input_val, **kwargs) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("kind", "field", "expected", "secondary_field", "secondary_expected"),
    [
        (
            "environmental_signal",
            "kind",
            "environmental_signal",
            "signal_id",
            0,
        ),
        (
            "any_of",
            "kind",
            "any_of",
            "conditions.0.kind",
            "herbivore_presence",
        ),
        ("substance_active", "substance_id", 1, None, None),
    ],
)
def test_main_default_activation_condition_supported_kinds(
    kind: str,
    field: str,
    expected: str | int,
    secondary_field: str | None,
    secondary_expected: str | int | None,
) -> None:
    """Validate default-condition synthesis and index guarding for trigger-rule editing paths.

    The trigger-rule editor builds default condition nodes by kind and must reject unsupported
    node labels. The index accessor must raise a 404 sentinel for out-of-range references.
    """
    draft = DraftState.default()
    draft_service.add_trigger_rule(
        draft,
        flora_species_id=0,
        herbivore_species_id=0,
        substance_id=0,
        min_herbivore_population=2,
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

    condition = api_main._default_activation_condition_for_rule(draft, rule, kind)
    assert condition[field] == expected
    if secondary_field == "signal_id":
        assert condition[secondary_field] == secondary_expected
    elif secondary_field == "conditions.0.kind":
        assert condition["conditions"][0]["kind"] == secondary_expected


def test_main_default_activation_condition_invalid_kind_and_missing_trigger_index() -> None:
    """Validate unsupported condition kinds and out-of-range trigger indices raise HTTP errors."""
    draft = DraftState.default()
    draft_service.add_trigger_rule(
        draft,
        flora_species_id=0,
        herbivore_species_id=0,
        substance_id=0,
        min_herbivore_population=2,
    )
    rule = draft.trigger_rules[0]

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


def test_render_status_badge_idle_without_loaded_loop() -> None:
    """Validate that the status badge reports Idle when no loop is registered."""
    api_main._sim_loop = None
    assert "Idle" in api_main._render_status_badge_html()


@pytest.mark.parametrize(
    ("running", "paused", "terminated", "expected_label"),
    [
        (False, False, False, "Loaded"),
        (True, False, False, "Running"),
        (True, True, False, "Paused"),
        (True, True, True, "Terminated"),
    ],
)
def test_render_status_badge_loaded_loop_states(
    running: bool,
    paused: bool,
    terminated: bool,
    expected_label: str,
) -> None:
    """Validate status badge labels for loaded-loop runtime states."""
    loop = _build_loaded_loop()
    loop.running = running
    loop.paused = paused
    loop.terminated = terminated
    assert expected_label in api_main._render_status_badge_html()


@pytest.mark.parametrize(
    ("setup_mode", "path", "params", "expected_json", "expected_text"),
    [
        (
            "no_loop",
            "/api/telemetry/chartjs-data",
            None,
            {
                "labels": [],
                "flora_ids": [],
                "herbivore_ids": [],
                "series": {},
            },
            None,
        ),
        (
            "loaded_empty_rows",
            "/api/telemetry/table_preview",
            {"flora_ids": "99", "limit": 5},
            None,
            "No rows match current table filters",
        ),
    ],
)
@pytest.mark.asyncio
async def test_telemetry_empty_response_branches(
    api_client: AsyncClient,
    setup_mode: str,
    path: str,
    params: dict[str, str | int] | None,
    expected_json: dict[str, object] | None,
    expected_text: str | None,
) -> None:
    """Validate empty-state telemetry responses for no-loop and filtered-empty branches."""
    if setup_mode == "loaded_empty_rows":
        loop = _build_loaded_loop()
        loop.telemetry._rows = []

    response = await api_client.get(path, params=params)

    assert response.status_code == 200, response.text
    if expected_json is not None:
        assert response.json() == expected_json
    if expected_text is not None:
        assert expected_text in response.text


@pytest.mark.asyncio
async def test_telemetry_chartjs_since_tick_ahead_of_current_run_returns_full_rows(
    api_client: AsyncClient,
) -> None:
    """Validate chartjs polling resilience when client cursor is ahead after reset.

    The browser polls ``/api/telemetry/chartjs-data`` with ``since_tick`` from the previous
    run. After a reset, this cursor can exceed the latest tick of the new run. In that state,
    the endpoint must return full rows rather than an empty delta so charts can resynchronize.
    """
    loop = _build_loaded_loop()
    loop.telemetry._rows = [
        {
            "tick": 0,
            "flora_population": 1,
            "herbivore_population": 1,
            "total_flora_energy": 10.0,
            "plant_pop_by_species": {0: 1},
            "plant_energy_by_species": {0: 10.0},
            "defense_cost_by_species": {0: 0.0},
            "swarm_pop_by_species": {0: 1},
        },
        {
            "tick": 1,
            "flora_population": 1,
            "herbivore_population": 1,
            "total_flora_energy": 9.5,
            "plant_pop_by_species": {0: 1},
            "plant_energy_by_species": {0: 9.5},
            "defense_cost_by_species": {0: 0.2},
            "swarm_pop_by_species": {0: 1},
        },
    ]

    response = await api_client.get("/api/telemetry/chartjs-data", params={"since_tick": 99})

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["labels"] == [0, 1]
    assert payload["series"]["flora_population"] == [1.0, 1.0]


@pytest.mark.asyncio
async def test_export_route_returns_404_without_loaded_loop(api_client: AsyncClient) -> None:
    """Validate export endpoints reject requests when no simulation loop is loaded."""
    no_loop = await api_client.get("/api/export/timeseries", params={"format": "csv"})
    assert no_loop.status_code == 404, no_loop.text


@pytest.mark.parametrize(
    ("path", "params", "expected_status", "expected_text"),
    [
        ("/api/export/unknown", {"format": "csv"}, 400, "Unknown data_type"),
        ("/api/export/timeseries", {"format": "csv", "tick_interval": 0}, 400, None),
        ("/api/export/timeseries", {"format": "bad"}, 400, None),
    ],
)
@pytest.mark.asyncio
async def test_export_route_invalid_request_branches(
    api_client: AsyncClient,
    path: str,
    params: dict[str, str | int],
    expected_status: int,
    expected_text: str | None,
) -> None:
    """Validate deterministic 400-branch handling for malformed export requests."""
    loop = _build_loaded_loop()
    await loop.step()

    response = await api_client.get(path, params=params)

    assert response.status_code == expected_status
    if expected_text is not None:
        assert expected_text in response.text


@pytest.mark.parametrize(
    ("path", "params", "content_type_fragment", "disposition_fragment"),
    [
        (
            "/api/export/metabolic",
            {"format": "csv"},
            "text/csv",
            "phids_defense_economy.csv",
        ),
        (
            "/api/export/timeseries",
            {"format": "tex_table"},
            "text/plain",
            "phids_timeseries_table.tex",
        ),
    ],
)
@pytest.mark.asyncio
async def test_export_route_success_format_branches(
    api_client: AsyncClient,
    path: str,
    params: dict[str, str],
    content_type_fragment: str,
    disposition_fragment: str,
) -> None:
    """Validate successful export responses for supported CSV and TeX table formats."""
    loop = _build_loaded_loop()
    await loop.step()

    response = await api_client.get(path, params=params)

    assert response.status_code == 200, response.text
    assert content_type_fragment in response.headers["content-type"]
    assert disposition_fragment in response.headers["content-disposition"]


@pytest.mark.parametrize(
    ("format_name", "expected_message"),
    [("tex_tikz", "tikz failed"), ("png", "png failed")],
)
@pytest.mark.asyncio
async def test_export_route_backend_failure_branches(
    api_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    format_name: str,
    expected_message: str,
) -> None:
    """Validate renderer backend failures propagate as deterministic 400 responses."""
    loop = _build_loaded_loop()
    await loop.step()

    def _raise_tikz(*args: object, **kwargs: object) -> str:
        raise ValueError("tikz failed")

    def _raise_png(*args: object, **kwargs: object) -> bytes:
        raise ValueError("png failed")

    monkeypatch.setattr("phids.api.routers.telemetry.generate_tikz_str", _raise_tikz)
    monkeypatch.setattr("phids.api.routers.telemetry.generate_png_bytes", _raise_png)

    response = await api_client.get("/api/export/timeseries", params={"format": format_name})

    assert response.status_code == 400, response.text
    assert expected_message in response.text


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        ([(b"hx-request", b"true")], True),
        ([], False),
    ],
)
def test_htmx_request_detection_cases(
    headers: list[tuple[bytes, bytes]],
    expected: bool,
) -> None:
    """Validate HTMX request detection for both header-present and header-absent requests."""
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers,
    }

    async def _receive() -> dict[str, object]:
        return {"type": "http.request"}

    assert api_main._is_htmx_request(Request(scope, _receive)) is expected
