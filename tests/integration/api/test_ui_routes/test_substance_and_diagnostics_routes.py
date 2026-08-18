# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Integration tests for PHIDS substances, trigger rules, diagnostics, and bio DB routes.

This module validates trigger rule matrices, substance definitions, diet matrix updates,
diagnostics tab rendering, backend log capture, and bio-database saving.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

import pytest
from httpx import AsyncClient

import phids.api.main as api_main
import phids.api.routers.ui
from phids.api.presenters.dashboard import build_live_dashboard_payload, extract_ui_snapshot
from phids.api.services.draft.placements import add_plant_placement, add_swarm_placement
from phids.api.services.draft.trigger_rules import add_trigger_rule
from phids.api.ui_state.state import get_draft
from phids.api.ui_state.substances import SubstanceDefinition
from phids.engine.components.swarm import SwarmComponent

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.asyncio
async def test_trigger_matrix_legacy_route_is_rejected(api_client: AsyncClient) -> None:
    """Verifies the removed legacy trigger-matrix URL is no longer routable.

    Args:
        api_client: Async HTTP client for API calls.
    """
    resp = await api_client.get("/ui/trigger-matrix")
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/ui/diagnostics/model",
        "/ui/diagnostics/frontend",
        "/ui/diagnostics/backend",
    ],
)
async def test_diagnostics_tabs_render(api_client: AsyncClient, path: str) -> None:
    """Ensures diagnostics tab endpoints render HTML diagnostics content.

    Args:
        api_client: Async HTTP client for API calls.
        path: The path to the diagnostics tab.
    """
    resp = await api_client.get(path)
    assert resp.status_code == 200, resp.text
    assert "diagnostics" in resp.text.lower()


@pytest.mark.asyncio
async def test_substance_and_diet_routes_delegate_to_service_and_compact_references(
    api_client: AsyncClient,
) -> None:
    """Validates builder routes preserve compact substance indexing and diet-matrix safety invariants.

    Args:
        api_client: Async HTTP client for API calls.
    """
    draft = get_draft()

    add_alarm = await api_client.post("/api/config/substances", data={"name": "Alarm"})
    add_shield = await api_client.post(
        "/api/config/substances",
        data={"name": "Shield", "is_toxin": "true", "lethal": "true"},
    )
    add_relay = await api_client.post("/api/config/substances", data={"name": "Relay"})

    update_resp = await api_client.put(
        "/api/config/substances/1",
        data={
            "name": "Shield+",
            "type_label": "Repellent Toxin",
            "synthesis_duration": 0,
            "aftereffect_ticks": -2,
            "repellent_walk_ticks": -3,
            "energy_cost_per_tick": -5.0,
            "irreversible": "on",
        },
    )
    toggle_diet = await api_client.post(
        "/api/matrices/diet",
        data={"herbivore_idx": 0, "flora_idx": 0, "compatible": "toggle"},
    )
    invalid_diet = await api_client.post(
        "/api/matrices/diet",
        data={"herbivore_idx": 9, "flora_idx": 9, "compatible": "true"},
    )

    missing_update = await api_client.put(
        "/api/config/substances/99",
        data={"name": "Missing"},
    )

    assert add_alarm.status_code == 200, add_alarm.text
    assert add_shield.status_code == 200, add_shield.text
    assert add_relay.status_code == 200, add_relay.text
    assert "Shield+" in update_resp.text
    assert toggle_diet.status_code == 200, toggle_diet.text
    assert invalid_diet.status_code == 200, invalid_diet.text
    assert missing_update.status_code == 404, missing_update.text
    assert draft.diet_matrix[0][0] is False
    assert draft.substance_definitions[1].repellent is True


@pytest.mark.asyncio
async def test_live_dashboard_payload_and_cell_details_include_signals_and_links(
    api_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validates live dashboard payload and cell details including signals and links.

    Args:
        api_client: Async HTTP client for API calls.
        monkeypatch: Monkeypatch fixture for asyncio.sleep.
    """
    monkeypatch.setattr(
        "phids.engine.systems.interaction.movement.core._choose_neighbour_by_flow_probability",
        lambda swarm, _flow_field, _width, _height, *_, **__: (swarm.x, swarm.y),
    )

    draft = get_draft()
    add_plant_placement(draft, 0, 2, 2, 18.0)
    add_plant_placement(draft, 0, 2, 3, 16.0)
    add_swarm_placement(draft, 0, 2, 2, 6, 24.0)
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
    add_trigger_rule(draft, 0, 0, 0, min_herbivore_population=5)

    load_resp = await api_client.post("/api/scenario/load-draft", headers={"HX-Request": "true"})
    assert load_resp.status_code == 204, load_resp.text

    step_resp = await api_client.post("/api/simulation/step", headers={"HX-Request": "true"})
    assert step_resp.status_code == 204, step_resp.text

    snapshot = extract_ui_snapshot(api_main._sim_loop)
    dashboard_payload = build_live_dashboard_payload(
        snapshot,
        substance_names=api_main._sim_substance_names,
    )
    details_resp = await api_client.get("/api/ui/cell-details", params={"x": 2, "y": 2})

    loop = api_main._sim_loop
    assert loop is not None
    swarm_entity = next(iter(loop.world.query(SwarmComponent)))
    swarm = swarm_entity.get_component(SwarmComponent)
    loop.world.move_entity(swarm.entity_id, swarm.x, swarm.y, 0, 0)
    swarm.x = 0
    swarm.y = 0

    second_step_resp = await api_client.post("/api/simulation/step", headers={"HX-Request": "true"})
    assert second_step_resp.status_code == 204, second_step_resp.text
    aftereffect_details_resp = await api_client.get("/api/ui/cell-details", params={"x": 2, "y": 2})

    assert dashboard_payload["tick"] == 1
    plants_table = cast("dict[str, object]", dashboard_payload["plants"])
    active_signal_ids = cast("list[list[int]]", plants_table["active_signal_ids"])
    assert any(0 in ids for ids in active_signal_ids)
    assert dashboard_payload["mycorrhizal_links"]
    assert details_resp.status_code == 200, details_resp.text
    details = details_resp.json()
    assert details["mode"] == "live"
    assert details["tick"] == 1
    assert details["signal_concentrations"]

    assert aftereffect_details_resp.status_code == 200, aftereffect_details_resp.text


@pytest.mark.asyncio
async def test_backend_diagnostics_shows_recent_logs(api_client: AsyncClient) -> None:
    """Ensures backend diagnostics endpoint displays recent logs for UI diagnostics.

    Args:
        api_client: Async HTTP client for API calls.
    """
    api_main.logger.info("UI diagnostics backend smoke test")
    resp = await api_client.get("/ui/diagnostics/backend")
    assert resp.status_code == 200, resp.text
    assert "Recent logs" in resp.text
    assert "UI diagnostics backend smoke test" in resp.text


@pytest.mark.asyncio
async def test_api_database_save_validates_payload(
    api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Validates that the database save endpoint requires a valid BioDatabaseModel payload.

    Args:
        api_client: Async HTTP client for API calls.
        monkeypatch: Monkeypatch fixture forBIO_DB_PATH.
        tmp_path: Temporary path for database file.
    """
    test_db_path = tmp_path / "bio_database.json"
    monkeypatch.setattr(phids.api.routers.ui, "BIO_DB_PATH", test_db_path)

    valid_payload = {
        "flora": {
            "TestPlant": {
                "growth_rate": 0.5,
                "max_energy": 100.0,
                "survival_threshold": 10.0,
                "seed_cost": 20.0,
                "seed_dispersion_radius": 5.0,
                "passive_defenses": {},
            }
        },
        "herbivores": {
            "TestBug": {
                "metabolism_upkeep": 1.0,
                "consumption_rate": 2.0,
                "mitosis_threshold": 50.0,
                "split_ratio": 0.5,
                "resistances": {},
            }
        },
    }

    invalid_payload = {
        "flora": {
            "TestPlant": {
                "growth_rate": "invalid_string",
            }
        },
        "herbivores": {},
    }

    malformed_json_payload = "not json"

    resp_valid = await api_client.post("/api/database/save", json=valid_payload)
    assert resp_valid.status_code == 200, resp_valid.text

    with open(test_db_path, encoding="utf-8") as f:
        saved_data = json.load(f)
    assert "TestPlant" in saved_data["flora"]

    resp_invalid = await api_client.post("/api/database/save", json=invalid_payload)
    assert resp_invalid.status_code == 422, resp_invalid.text

    resp_malformed = await api_client.post(
        "/api/database/save",
        content=malformed_json_payload,
        headers={"Content-Type": "application/json"},
    )
    assert resp_malformed.status_code == 422, resp_malformed.text
