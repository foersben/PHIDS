# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Coverage reinforcement tests for telemetry export API route branches.

This module adds targeted regression checks for the ``/api/export/*`` endpoints
and the ``/api/telemetry/*`` polling endpoints. All branches validated here are
operationally important but historically under-exercised by broad integration tests:
empty-state telemetry responses, client-cursor-ahead resynchronization, missing-loop
404s, invalid-request 400s, successful format responses, and renderer backend failures.

These checks improve statistical confidence that the operator-facing export
surface remains stable across edge-case parameterizations and absent-runtime states.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from phids.api import main as api_main
from phids.api.services.draft.placements import (
    add_plant_placement,
    add_swarm_placement,
)
from phids.api.ui_state.state import get_draft
from phids.engine.loop import SimulationLoop

if TYPE_CHECKING:
    from httpx import AsyncClient


def _build_loaded_loop() -> SimulationLoop:
    """Construct and register a minimal simulation loop with one plant and one swarm.

    Returns:
        The initialized simulation loop bound to ``api_main._sim_loop``.
    """
    draft = get_draft()
    add_plant_placement(draft, 0, 2, 2, 12.0)
    add_swarm_placement(draft, 0, 2, 2, 4, 8.0)
    loop = SimulationLoop(draft.build_sim_config())
    api_main._sim_loop = loop
    return loop


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
                "run_id": "",
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

    def _raise_tikz(*_args: object, **_kwargs: object) -> str:
        raise ValueError("tikz failed")

    def _raise_png(*_args: object, **_kwargs: object) -> bytes:
        raise ValueError("png failed")

    monkeypatch.setattr("phids.api.routers.telemetry.exports.generate_tikz_str", _raise_tikz)
    monkeypatch.setattr("phids.api.routers.telemetry.exports.generate_png_bytes", _raise_png)

    response = await api_client.get("/api/export/timeseries", params={"format": format_name})

    assert response.status_code == 400, response.text
    assert expected_message in response.text
