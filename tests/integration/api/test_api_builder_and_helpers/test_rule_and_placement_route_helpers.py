# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Integration tests for PHIDS API trigger rule, placement, scenario, and websocket routes."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

if TYPE_CHECKING:
    from httpx import AsyncClient

from phids.api import main as api_main
from phids.api.main import app
from phids.api.presenters.dashboard import (
    build_live_dashboard_payload,
    extract_ui_snapshot,
)
from phids.api.schemas.placement import InitialPlantPlacement, InitialSwarmPlacement
from phids.api.schemas.simulation import SimulationConfig
from phids.api.schemas.species import DietCompatibilityMatrix, FloraSpeciesParams, HerbivoreSpeciesParams
from phids.api.schemas.triggers import HerbivoreAttackInitiator, SynthesizeSubstanceAction, TriggerConditionSchema
from phids.api.ui_state.state import DraftState, get_draft, reset_draft, set_draft
from phids.api.ui_state.substances import SubstanceDefinition
from phids.engine.loop import SimulationLoop


def _flora(species_id: int) -> FloraSpeciesParams:
    return FloraSpeciesParams(
        species_id=species_id,
        name=f"flora-{species_id}",
        base_energy=10.0,
        max_energy=20.0,
        growth_rate=2.0,
        survival_threshold=1.0,
        reproduction_interval=2,
        seed_min_dist=1.0,
        seed_max_dist=2.0,
        seed_energy_cost=1.0,
        triggers=[],
    )


def _herbivore(species_id: int) -> HerbivoreSpeciesParams:
    return HerbivoreSpeciesParams(
        species_id=species_id,
        name=f"herbivore-{species_id}",
        energy_min=1.0,
        velocity=1,
        consumption_rate=1.0,
        reproduction_energy_divisor=1.0,
    )


def _config_with_trigger() -> SimulationConfig:
    trigger = TriggerConditionSchema(
        initiator=HerbivoreAttackInitiator(herbivore_species_id=0, min_herbivore_population=3),
        aftereffect_ticks=2,
        action=SynthesizeSubstanceAction(
            substance_id=0,
            synthesis_duration=1,
            is_toxin=False,
            energy_cost_per_tick=0.4,
        ),
    )
    return SimulationConfig(
        grid_width=8,
        grid_height=8,
        max_ticks=20,
        tick_rate_hz=20.0,
        num_signals=2,
        num_toxins=2,
        flora_species=[_flora(0).model_copy(update={"triggers": [trigger]})],
        herbivore_species=[_herbivore(0)],
        diet_matrix=DietCompatibilityMatrix(rows=[[True]]),
        initial_plants=[InitialPlantPlacement(species_id=0, x=2, y=2, energy=10.0)],
        initial_swarms=[InitialSwarmPlacement(species_id=0, x=2, y=2, population=4, energy=5.0)],
        mycorrhizal_growth_interval_ticks=6,
    )


@pytest.mark.asyncio
async def test_trigger_rule_routes_add_update_and_delete(api_client: AsyncClient) -> None:
    """Verify trigger-rule add/update/delete routes and missing-rule handling."""
    draft = get_draft()
    draft.substance_definitions = [
        SubstanceDefinition(substance_id=0, name="Signal A"),
        SubstanceDefinition(substance_id=1, name="Signal B"),
    ]

    add_resp = await api_client.post(
        "/api/config/trigger-rules",
        data={
            "flora_species_id": 0,
            "herbivore_species_id": 0,
            "substance_id": 0,
            "min_herbivore_population": 0,
            "activation_condition_json": (
                '{"kind":"herbivore_presence","herbivore_species_id":0,"min_herbivore_population":2}'
            ),
        },
    )
    update_resp = await api_client.put(
        "/api/config/trigger-rules/0",
        data={"substance_id": 1, "min_herbivore_population": 7},
    )
    update_missing_resp = await api_client.put("/api/config/trigger-rules/9", data={"substance_id": 1})
    delete_resp = await api_client.delete("/api/config/trigger-rules/0")
    delete_missing_resp = await api_client.delete("/api/config/trigger-rules/9")

    assert add_resp.status_code == 200, add_resp.text
    assert update_resp.status_code == 200, update_resp.text
    assert update_missing_resp.status_code == 404, update_missing_resp.text
    assert delete_resp.status_code == 200, delete_resp.text
    assert delete_missing_resp.status_code == 404, delete_missing_resp.text


@pytest.mark.asyncio
async def test_trigger_rule_condition_node_routes_validate_parent_paths(
    api_client: AsyncClient,
) -> None:
    """Verify trigger-rule condition tree endpoints support valid edits and reject invalid parent paths."""
    draft = get_draft()
    draft.substance_definitions = [
        SubstanceDefinition(substance_id=0, name="Signal A"),
        SubstanceDefinition(substance_id=1, name="Signal B"),
    ]

    await api_client.post(
        "/api/config/trigger-rules",
        data={
            "flora_species_id": 0,
            "herbivore_species_id": 0,
            "substance_id": 0,
            "activation_condition_json": (
                '{"kind":"herbivore_presence","herbivore_species_id":0,"min_herbivore_population":3}'
            ),
        },
    )
    replace_root_resp = await api_client.post(
        "/api/config/trigger-rules/0/condition/root",
        data={"node_kind": "all_of"},
    )
    add_child_resp = await api_client.post(
        "/api/config/trigger-rules/0/condition/child",
        data={"node_kind": "substance_active", "parent_path": ""},
    )
    update_node_resp = await api_client.put(
        "/api/config/trigger-rules/0/condition/node",
        data={"path": "1", "substance_id": 1},
    )
    delete_child_resp = await api_client.post(
        "/api/config/trigger-rules/0/condition/delete",
        data={"path": "1"},
    )
    invalid_parent_resp = await api_client.post(
        "/api/config/trigger-rules/0/condition/child",
        data={"node_kind": "herbivore_presence", "parent_path": "0"},
    )

    assert replace_root_resp.status_code == 200, replace_root_resp.text
    assert add_child_resp.status_code == 200, add_child_resp.text
    assert update_node_resp.status_code == 200, update_node_resp.text
    assert delete_child_resp.status_code == 200, delete_child_resp.text
    assert invalid_parent_resp.status_code == 400, invalid_parent_resp.text


@pytest.mark.asyncio
async def test_placement_routes_add_remove_and_clear(api_client: AsyncClient) -> None:
    """Verify placement endpoints add clamped entries, remove existing entries, and clear all placements."""
    responses = {
        "plant_add": await api_client.post(
            "/api/config/placements/plant",
            data={"species_id": 0, "x": 999, "y": -5, "energy": -3.0},
        ),
        "swarm_add": await api_client.post(
            "/api/config/placements/swarm",
            data={"species_id": 0, "x": -2, "y": 999, "population": 0, "energy": -7.0},
        ),
        "plant_delete": await api_client.delete("/api/config/placements/plant/0"),
        "plant_delete_missing": await api_client.delete("/api/config/placements/plant/0"),
        "swarm_delete": await api_client.delete("/api/config/placements/swarm/0"),
        "swarm_delete_missing": await api_client.delete("/api/config/placements/swarm/0"),
        "clear": await api_client.post("/api/config/placements/clear"),
    }

    expected_statuses = {
        "plant_add": 200,
        "swarm_add": 200,
        "plant_delete": 200,
        "plant_delete_missing": 404,
        "swarm_delete": 200,
        "swarm_delete_missing": 404,
        "clear": 200,
    }
    for key, expected_status in expected_statuses.items():
        assert responses[key].status_code == expected_status, responses[key].text


@pytest.mark.asyncio
async def test_scenario_routes_reject_invalid_draft_or_import_payload(
    api_client: AsyncClient,
) -> None:
    """Verify scenario export/load reject invalid drafts and import rejects malformed JSON uploads."""
    set_draft(DraftState(flora_species=[], herbivore_species=[]))
    responses = {
        "export": await api_client.get("/api/scenario/export"),
        "load": await api_client.post("/api/scenario/load-draft"),
        "import": await api_client.post(
            "/api/scenario/import",
            files={"file": ("broken.json", b"{not-json", "application/json")},
        ),
    }

    assert responses["export"].status_code == 400, responses["export"].text
    assert responses["load"].status_code == 400, responses["load"].text
    assert responses["import"].status_code == 422, responses["import"].text
    reset_draft()


@pytest.mark.asyncio
async def test_scenario_import_reconstructs_triggers_and_substances(
    api_client: AsyncClient,
) -> None:
    """Test scenario import for triggers and substances reconstruction."""
    payload = _config_with_trigger().model_dump(mode="json")
    payload["flora_species"][0]["triggers"][0]["activation_condition"] = {
        "kind": "herbivore_presence",
        "herbivore_species_id": 0,
        "min_herbivore_population": 3,
    }
    content = json.dumps(payload).encode("utf-8")

    resp = await api_client.post(
        "/api/scenario/import",
        files={"file": ("triggered.json", content, "application/json")},
    )

    draft = get_draft()
    assert resp.status_code == 200, resp.text
    assert draft.mycorrhizal_growth_interval_ticks == 6
    assert len(draft.trigger_rules) == 1
    assert draft.trigger_rules[0].activation_condition == {
        "kind": "herbivore_presence",
        "herbivore_species_id": 0,
        "min_herbivore_population": 3,
    }
    assert draft.substance_definitions[0].name == "Substance 0"


def test_websocket_stream_endpoints_close_cleanly() -> None:
    """Verify websocket endpoints close correctly when idle and stream payloads once a loop exists."""
    client = TestClient(app)

    with client.websocket_connect("/ws/simulation/stream") as websocket:
        close_message = websocket.receive()
    assert close_message["type"] == "websocket.close"
    assert close_message["code"] == 1008

    loop = SimulationLoop(_config_with_trigger())
    api_main._sim_loop = loop
    expected_payload = build_live_dashboard_payload(extract_ui_snapshot(loop), substance_names={})
    with client.websocket_connect("/ws/ui/stream") as websocket:
        payload = json.loads(websocket.receive_text())

    assert payload["all_flora_species"]
    assert payload["tick"] == expected_payload["tick"]
    assert payload["grid_width"] == expected_payload["grid_width"]
    assert payload["grid_height"] == expected_payload["grid_height"]
