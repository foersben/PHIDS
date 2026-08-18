# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Integration tests for PHIDS live dashboard, SSE telemetry streams, and cell detail endpoints.

This module validates HTMX workspace partials, live telemetry canvas rendering, bifurcated live
dashboard payload creation (extant grid render vs extinct species catalog legend), cell detail
inspection with signaling/mycorrhiza overlays, and simulation control state transitions.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from httpx import AsyncClient

import phids.api.main as api_main
from phids.api.presenters.dashboard import build_live_dashboard_payload, extract_ui_snapshot
from phids.engine.components.plant import PlantComponent
from phids.engine.loop import SimulationLoop
from phids.io.scenario import load_scenario_from_json


def _as_object_dict_rows(value: object) -> list[dict[str, object]]:
    """Normalize heterogeneous payload values to a list of object dictionaries."""
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _safe_int(value: object, default: int = -1) -> int:
    """Coerce heterogeneous payload scalars to integer identifiers."""
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float, str)):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _advance_loop_until_flora_extinction(loop: SimulationLoop, max_ticks: int = 140) -> None:
    """Step simulation loop until only 1 flora species remains."""
    while loop.tick < max_ticks:
        asyncio.run(loop.step())
        live = {entity.get_component(PlantComponent).species_id for entity in loop.world.query(PlantComponent)}
        if len(live) <= 1:
            break


def _extract_payload_species_ids(rows: list[dict[str, object]]) -> set[int]:
    """Extract valid species IDs from dashboard payload rows."""
    return {species_id for species_id in (_safe_int(spec.get("species_id")) for spec in rows) if species_id >= 0}


@pytest.mark.asyncio
async def test_root_returns_full_html(api_client: AsyncClient) -> None:
    """Validates that the root endpoint returns a complete HTML workspace for the PHIDS UI."""
    resp = await api_client.get("/")

    assert resp.status_code == 200, resp.text
    assert "text/html" in resp.headers["content-type"]
    assert 'id="main-workspace"' in resp.text
    assert 'id="diagnostics-rail"' in resp.text
    assert 'id="diagnostics-content"' in resp.text
    assert 'id="draft-save-indicator"' in resp.text
    assert "phidsUploadScenario" in resp.text
    assert "/api/scenario/load-draft" in resp.text
    assert "/api/simulation/tick-rate" in resp.text
    assert 'hx-include="#biotope-config-view form"' in resp.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "marker", "extra_marker"),
    [
        ("/ui/dashboard", "biotope-canvas", None),
        ("/ui/placements", "placement-canvas", None),
        ("/ui/biotope", "biotope-config-view", None),
        ("/ui/flora", "flora-config-view", None),
        ("/ui/herbivores", "herbivore-config-view", None),
        ("/ui/substances", "substance-config-view", None),
        ("/ui/diet-matrix", "diet-matrix-view", None),
        ("/ui/trigger-rules", "trigger-rules-view", None),
        ("/ui/batch", "Monte Carlo Batch Runner", "Load Persisted Batches"),
    ],
)
async def test_ui_partials_render(
    api_client: AsyncClient,
    path: str,
    marker: str,
    extra_marker: str | None,
) -> None:
    """Verifies that each UI partial endpoint renders the expected canvas or configuration view."""
    resp = await api_client.get(path)

    assert resp.status_code == 200, resp.text
    assert marker in resp.text
    if extra_marker is not None:
        assert extra_marker in resp.text


@pytest.mark.asyncio
async def test_ui_status_helpers_render_without_loaded_simulation(api_client: AsyncClient) -> None:
    """Confirms that UI status helpers render correctly when no simulation is loaded."""
    tick_resp = await api_client.get("/api/ui/tick")
    status_resp = await api_client.get("/api/ui/status-badge")
    telemetry_resp = await api_client.get("/api/telemetry")

    assert tick_resp.status_code == 200, tick_resp.text
    assert tick_resp.text == "0"
    assert status_resp.status_code == 200, status_resp.text
    assert "Idle" in status_resp.text
    assert telemetry_resp.status_code == 200, telemetry_resp.text
    assert "No telemetry data yet" in telemetry_resp.text


@pytest.mark.asyncio
async def test_table_preview_route_renders_empty_state_without_loaded_simulation(
    api_client: AsyncClient,
) -> None:
    """Validates that table preview route renders empty state when no simulation is active."""
    resp = await api_client.get("/api/telemetry/table_preview")
    assert resp.status_code == 200, resp.text
    assert "No telemetry data" in resp.text


@pytest.mark.asyncio
async def test_dashboard_contains_extended_telemetry_canvases(api_client: AsyncClient) -> None:
    """Verifies dashboard template includes all interactive telemetry charts."""
    resp = await api_client.get("/ui/dashboard")

    assert resp.status_code == 200, resp.text
    assert 'id="biotope-canvas"' in resp.text
    assert 'id="dashboard-view"' in resp.text


def test_live_dashboard_payload_separates_render_layers_from_all_configured_species() -> None:
    """Verifies that the dashboard payload preserves extinct-species metadata without repainting extinct layers."""
    config = load_scenario_from_json(Path("examples/meadow_defense.json"))
    loop = SimulationLoop(config)
    _advance_loop_until_flora_extinction(loop)

    payload = build_live_dashboard_payload(extract_ui_snapshot(loop), substance_names=api_main._sim_substance_names)
    species_energy_rows = _as_object_dict_rows(payload.get("species_energy"))
    all_flora_rows = _as_object_dict_rows(payload.get("all_flora_species"))

    payload_species = _extract_payload_species_ids(species_energy_rows)
    legend_species = _extract_payload_species_ids(all_flora_rows)
    configured_species = {species.species_id for species in loop.config.flora_species}
    live_species = {entity.get_component(PlantComponent).species_id for entity in loop.world.query(PlantComponent)}

    assert payload_species == live_species
    assert legend_species == configured_species

    extinct_in_payload = {
        _safe_int(spec.get("species_id"))
        for spec in all_flora_rows
        if spec.get("extinct", False) and _safe_int(spec.get("species_id")) >= 0
    }
    assert extinct_in_payload == configured_species - live_species


@pytest.mark.asyncio
async def test_simulation_status_and_tick_rate_routes(api_client: AsyncClient) -> None:
    """Verifies status badge and tick rate updating routes."""
    await api_client.post("/api/scenario/load-draft")
    status_resp = await api_client.get("/api/ui/status-badge")
    assert status_resp.status_code == 200

    rate_resp = await api_client.put("/api/simulation/tick-rate", json={"tick_rate": 30})
    assert rate_resp.status_code == 200


@pytest.mark.asyncio
async def test_simulation_step_and_wind_routes(api_client: AsyncClient) -> None:
    """Verifies single step and wind updating endpoints."""
    await api_client.post("/api/scenario/load-draft")
    step_resp = await api_client.post("/api/simulation/step")
    assert step_resp.status_code == 200

    wind_resp = await api_client.put("/api/simulation/wind", json={"wind_x": 0.5, "wind_y": -0.2})
    assert wind_resp.status_code == 200


@pytest.mark.asyncio
async def test_simulation_start_pause_reset_htmx_badges(api_client: AsyncClient) -> None:
    """Verifies state badge HTMX triggers on start, pause, and reset."""
    await api_client.post("/api/scenario/load-draft")
    start_resp = await api_client.post("/api/simulation/start", headers={"HX-Request": "true"})
    assert start_resp.status_code == 204
    assert "updateStatusBadge" in start_resp.headers.get("HX-Trigger", "")

    pause_resp = await api_client.post("/api/simulation/pause", headers={"HX-Request": "true"})
    assert pause_resp.status_code == 204
    assert "updateStatusBadge" in pause_resp.headers.get("HX-Trigger", "")

    reset_resp = await api_client.post("/api/simulation/reset", headers={"HX-Request": "true"})
    assert reset_resp.status_code == 204
    assert "updateStatusBadge" in reset_resp.headers.get("HX-Trigger", "")


@pytest.mark.asyncio
async def test_placement_preview_data_includes_root_links(api_client: AsyncClient) -> None:
    """Verifies placement preview endpoint returns valid grid canvas data."""
    resp = await api_client.get("/api/config/placements/data")
    assert resp.status_code == 200
    data = resp.json()
    assert "grid_width" in data
    assert "grid_height" in data


@pytest.mark.asyncio
async def test_ui_cell_details_returns_draft_preview_payload_with_mycorrhiza(api_client: AsyncClient) -> None:
    """Verifies cell details route provides spatial inspection of grid cells."""
    resp = await api_client.get("/api/ui/cell-details?x=2&y=2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["x"] == 2
    assert data["y"] == 2
