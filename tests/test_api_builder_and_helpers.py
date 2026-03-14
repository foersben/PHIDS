from __future__ import annotations

import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

from phids.api import main as api_main
from phids.api.main import app
from phids.api.schemas import (
    DietCompatibilityMatrix,
    FloraSpeciesParams,
    InitialPlantPlacement,
    InitialSwarmPlacement,
    PredatorSpeciesParams,
    SimulationConfig,
    TriggerConditionSchema,
)
from phids.api.ui_state import (
    DraftState,
    SubstanceDefinition,
    TriggerRule,
    get_draft,
    reset_draft,
    set_draft,
)
from phids.engine.components.substances import SubstanceComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.loop import SimulationLoop


def _default_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


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


def _predator(species_id: int) -> PredatorSpeciesParams:
    return PredatorSpeciesParams(
        species_id=species_id,
        name=f"predator-{species_id}",
        energy_min=1.0,
        velocity=1,
        consumption_rate=1.0,
        reproduction_energy_divisor=1.0,
    )


def _config_with_trigger() -> SimulationConfig:
    trigger = TriggerConditionSchema(
        predator_species_id=0,
        min_predator_population=3,
        substance_id=0,
        synthesis_duration=1,
        is_toxin=False,
        aftereffect_ticks=2,
        energy_cost_per_tick=0.4,
    )
    return SimulationConfig(
        grid_width=8,
        grid_height=8,
        max_ticks=20,
        tick_rate_hz=20.0,
        num_signals=2,
        num_toxins=2,
        flora_species=[_flora(0).model_copy(update={"triggers": [trigger]})],
        predator_species=[_predator(0)],
        diet_matrix=DietCompatibilityMatrix(rows=[[True]]),
        initial_plants=[InitialPlantPlacement(species_id=0, x=2, y=2, energy=10.0)],
        initial_swarms=[InitialSwarmPlacement(species_id=0, x=2, y=2, population=4, energy=5.0)],
        mycorrhizal_growth_interval_ticks=6,
    )


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    reset_draft()
    api_main._sim_loop = None
    api_main._sim_task = None
    api_main._sim_substance_names = {}


def test_main_helper_functions_cover_condition_and_status_logic() -> None:
    assert api_main._default_substance_name(2, is_toxin=False) == "Signal 2"
    assert api_main._default_substance_name(3, is_toxin=True) == "Toxin 3"

    config = _config_with_trigger()
    api_main._set_simulation_substance_names(config)
    assert api_main._substance_name(0, is_toxin=False) == "Signal 0"
    assert api_main._substance_name(99, is_toxin=True) == "Toxin 99"

    draft = DraftState.default()
    draft.substance_definitions = [SubstanceDefinition(substance_id=0, name="Alarm")]
    api_main._set_simulation_substance_names(config, draft=draft)
    assert api_main._substance_name(0, is_toxin=False) == "Alarm"

    assert api_main._parse_activation_condition_json(None) is None
    assert api_main._parse_activation_condition_json("   ") is None
    assert api_main._parse_activation_condition_json(
        '{"kind":"enemy_presence","predator_species_id":0,"min_predator_population":3}'
    ) == {
        "kind": "enemy_presence",
        "predator_species_id": 0,
        "min_predator_population": 3,
    }
    with pytest.raises(HTTPException):
        api_main._parse_activation_condition_json("{bad json")
    with pytest.raises(HTTPException):
        api_main._parse_activation_condition_json('{"kind":"substance_active"}')

    assert api_main._describe_activation_condition(None) == "unconditional"
    assert (
        api_main._describe_activation_condition(
            {"kind": "enemy_presence", "predator_species_id": 1, "min_predator_population": 4},
            predator_names={1: "Beetles"},
        )
        == "Beetles ≥ 4"
    )
    assert (
        api_main._describe_activation_condition(
            {"kind": "substance_active", "substance_id": 7},
            substance_names={7: "Alarm"},
        )
        == "Alarm active"
    )
    assert (
        api_main._describe_activation_condition({"kind": "all_of", "conditions": []})
        == "unconditional"
    )
    assert (
        api_main._describe_activation_condition(
            {
                "kind": "any_of",
                "conditions": [
                    {
                        "kind": "enemy_presence",
                        "predator_species_id": 0,
                        "min_predator_population": 2,
                    },
                    {"kind": "substance_active", "substance_id": 1},
                ],
            },
            predator_names={0: "Moths"},
            substance_names={1: "VOC"},
        )
        == "(Moths ≥ 2 OR VOC active)"
    )

    draft.trigger_rules = [TriggerRule(flora_species_id=0, predator_species_id=0, substance_id=0)]
    assert api_main._trigger_rule_by_index(draft, 0).substance_id == 0
    with pytest.raises(HTTPException):
        api_main._trigger_rule_by_index(draft, 3)

    api_main._validate_cell_coordinates(1, 1, 3, 3)
    with pytest.raises(HTTPException):
        api_main._validate_cell_coordinates(5, 1, 3, 3)

    draft.initial_plants = []
    draft.add_plant_placement(0, 1, 1, 10.0)
    draft.add_plant_placement(1, 2, 1, 10.0)
    assert api_main._build_draft_mycorrhizal_links(draft) == []
    draft.mycorrhizal_inter_species = True
    assert api_main._build_draft_mycorrhizal_links(draft)[0]["inter_species"] is True

    request = Request({"type": "http", "headers": [(b"hx-request", b"true")]})
    assert api_main._is_htmx_request(request) is True
    assert api_main._is_htmx_request(Request({"type": "http", "headers": []})) is False

    with pytest.raises(HTTPException):
        api_main._get_loop()

    assert "Idle" in api_main._render_status_badge_html()
    loop = SimulationLoop(_config_with_trigger())
    api_main._sim_loop = loop
    assert "Loaded" in api_main._render_status_badge_html()
    loop.running = True
    assert "Running" in api_main._render_status_badge_html()
    loop.paused = True
    assert "Paused" in api_main._render_status_badge_html()
    loop.terminated = True
    assert "Terminated" in api_main._render_status_badge_html()


def test_main_live_summary_and_starving_swarm_helpers() -> None:
    loop = SimulationLoop(_config_with_trigger())
    api_main._sim_loop = loop

    swarm = next(iter(loop.world.query(SwarmComponent))).get_component(SwarmComponent)
    swarm.energy = 0.0
    swarm.energy_min = 2.0
    swarm.repelled = True

    extra_swarm_entity = loop.world.create_entity()
    extra_swarm = SwarmComponent(
        entity_id=extra_swarm_entity.entity_id,
        species_id=0,
        x=1,
        y=1,
        population=2,
        initial_population=1,
        energy=1.0,
        energy_min=1.0,
        velocity=1,
        consumption_rate=1.0,
        energy_upkeep_per_individual=0.05,
        split_population_threshold=0,
    )
    loop.world.add_component(extra_swarm_entity.entity_id, extra_swarm)
    loop.world.register_position(extra_swarm_entity.entity_id, 1, 1)

    substance_entity = loop.world.create_entity()
    loop.world.add_component(
        substance_entity.entity_id,
        SubstanceComponent(
            entity_id=substance_entity.entity_id,
            substance_id=0,
            owner_plant_id=0,
            active=True,
            aftereffect_remaining_ticks=1,
        ),
    )

    summary = api_main._build_live_summary()
    starving = api_main._build_energy_deficit_swarms()

    assert summary is not None
    assert summary["plants"] == 1
    assert summary["swarms"] == 2
    assert summary["active_substances"] == 1
    assert starving[0]["energy_deficit"] >= starving[1]["energy_deficit"]
    assert any(swarm_entry["repelled"] is True for swarm_entry in starving)


@pytest.mark.asyncio
async def test_condition_node_update_creates_root_when_rule_has_no_condition() -> None:
    draft = get_draft()
    draft.substance_definitions = [SubstanceDefinition(substance_id=0, name="Signal A")]
    draft.add_trigger_rule(0, 0, 0)

    request = Request({"type": "http", "headers": []})
    response = await api_main.config_trigger_rule_condition_node_update(
        request,
        0,
        path="",
        kind="enemy_presence",
        predator_species_id=0,
        min_predator_population=2,
        substance_id=None,
    )

    assert response.status_code == 200
    assert draft.trigger_rules[0].activation_condition == {
        "kind": "enemy_presence",
        "predator_species_id": 0,
        "min_predator_population": 5,
    }


@pytest.mark.asyncio
async def test_builder_crud_routes_cover_flora_predators_substances_and_diet_matrix() -> None:
    async with _default_client() as client:
        flora_add = await client.post(
            "/api/config/flora",
            data={
                "name": "Oak",
                "base_energy": 12.0,
                "max_energy": 30.0,
                "growth_rate": 4.0,
                "survival_threshold": 1.2,
                "reproduction_interval": 5,
                "seed_min_dist": 1.0,
                "seed_max_dist": 2.0,
                "seed_energy_cost": 1.5,
                "camouflage": "on",
                "camouflage_factor": 5.0,
            },
        )
        flora_update = await client.put(
            "/api/config/flora/1",
            data={"name": "Oak Updated", "camouflage": "on", "camouflage_factor": -1.0},
        )
        flora_delete = await client.delete("/api/config/flora/1")
        flora_delete_missing = await client.delete("/api/config/flora/99")

        predator_add = await client.post(
            "/api/config/predators",
            data={"name": "Locust", "energy_min": 2.0, "velocity": 2, "consumption_rate": 3.5},
        )
        predator_update = await client.put(
            "/api/config/predators/1",
            data={"name": "Locust Updated", "velocity": 3},
        )
        predator_delete = await client.delete("/api/config/predators/1")
        predator_delete_missing = await client.delete("/api/config/predators/99")

        substance_add = await client.post(
            "/api/config/substances",
            data={
                "name": "Repellent",
                "is_toxin": "true",
                "repellent": "yes",
                "synthesis_duration": 0,
                "aftereffect_ticks": -1,
                "repellent_walk_ticks": -5,
                "energy_cost_per_tick": -1.0,
            },
        )
        substance_update = await client.put(
            "/api/config/substances/0",
            data={
                "name": "Repellent Updated",
                "type_label": "Repellent Toxin",
                "synthesis_duration": 0,
                "aftereffect_ticks": -5,
                "repellent_walk_ticks": -3,
                "energy_cost_per_tick": -2.0,
            },
        )
        matrix_toggle = await client.post(
            "/api/matrices/diet",
            data={"predator_idx": 0, "flora_idx": 0, "compatible": "toggle"},
        )
        matrix_set = await client.post(
            "/api/matrices/diet",
            data={"predator_idx": 0, "flora_idx": 0, "compatible": "false"},
        )
        matrix_out_of_range = await client.post(
            "/api/matrices/diet",
            data={"predator_idx": 9, "flora_idx": 9, "compatible": "true"},
        )
        substance_delete = await client.delete("/api/config/substances/0")
        substance_delete_missing = await client.delete("/api/config/substances/99")

    draft = get_draft()
    assert flora_add.status_code == 200
    assert flora_update.status_code == 200
    assert flora_delete.status_code == 200
    assert flora_delete_missing.status_code == 404
    assert predator_add.status_code == 200
    assert predator_update.status_code == 200
    assert predator_delete.status_code == 200
    assert predator_delete_missing.status_code == 404
    assert substance_add.status_code == 200
    assert substance_update.status_code == 200
    assert matrix_toggle.status_code == 200
    assert matrix_set.status_code == 200
    assert matrix_out_of_range.status_code == 200
    assert substance_delete.status_code == 200
    assert substance_delete_missing.status_code == 404
    assert draft.diet_matrix[0][0] is False


@pytest.mark.asyncio
async def test_builder_route_rule_of_16_branches() -> None:
    draft = get_draft()
    draft.flora_species = [_flora(i) for i in range(16)]
    draft.predator_species = [_predator(i) for i in range(16)]
    draft.substance_definitions = [
        SubstanceDefinition(substance_id=i, name=f"s{i}") for i in range(16)
    ]

    async with _default_client() as client:
        flora_resp = await client.post("/api/config/flora", data={"name": "Overflow"})
        predator_resp = await client.post("/api/config/predators", data={"name": "Overflow"})
        substance_resp = await client.post("/api/config/substances", data={"name": "Overflow"})

    assert flora_resp.status_code == 400
    assert predator_resp.status_code == 400
    assert substance_resp.status_code == 400


@pytest.mark.asyncio
async def test_trigger_rule_placement_and_scenario_routes_cover_success_and_error_paths() -> None:
    draft = get_draft()
    draft.substance_definitions = [
        SubstanceDefinition(substance_id=0, name="Signal A"),
        SubstanceDefinition(substance_id=1, name="Signal B"),
    ]

    async with _default_client() as client:
        add_rule = await client.post(
            "/api/config/trigger-rules",
            data={
                "flora_species_id": 0,
                "predator_species_id": 0,
                "substance_id": 0,
                "min_predator_population": 0,
                "activation_condition_json": '{"kind":"enemy_presence","predator_species_id":0,"min_predator_population":3}',
            },
        )
        update_rule = await client.put(
            "/api/config/trigger-rules/0",
            data={"substance_id": 1, "min_predator_population": 7},
        )
        update_rule_missing = await client.put(
            "/api/config/trigger-rules/9",
            data={"substance_id": 1},
        )
        replace_root = await client.post(
            "/api/config/trigger-rules/0/condition/root",
            data={"node_kind": "all_of"},
        )
        add_child = await client.post(
            "/api/config/trigger-rules/0/condition/child",
            data={"node_kind": "substance_active", "parent_path": ""},
        )
        update_node = await client.put(
            "/api/config/trigger-rules/0/condition/node",
            data={"path": "1", "substance_id": 1},
        )
        delete_child = await client.post(
            "/api/config/trigger-rules/0/condition/delete",
            data={"path": "1"},
        )
        bad_child = await client.post(
            "/api/config/trigger-rules/0/condition/child",
            data={"node_kind": "enemy_presence", "parent_path": "0"},
        )
        delete_rule = await client.delete("/api/config/trigger-rules/0")
        delete_rule_missing = await client.delete("/api/config/trigger-rules/9")

        plant_add = await client.post(
            "/api/config/placements/plant",
            data={"species_id": 0, "x": 999, "y": -5, "energy": -3.0},
        )
        swarm_add = await client.post(
            "/api/config/placements/swarm",
            data={"species_id": 0, "x": -2, "y": 999, "population": 0, "energy": -7.0},
        )
        plant_delete = await client.delete("/api/config/placements/plant/0")
        plant_delete_missing = await client.delete("/api/config/placements/plant/0")
        swarm_delete = await client.delete("/api/config/placements/swarm/0")
        swarm_delete_missing = await client.delete("/api/config/placements/swarm/0")
        clear_resp = await client.post("/api/config/placements/clear")

        set_draft(DraftState(flora_species=[], predator_species=[]))
        export_invalid = await client.get("/api/scenario/export")
        load_invalid = await client.post("/api/scenario/load-draft")
        import_invalid = await client.post(
            "/api/scenario/import",
            files={"file": ("broken.json", b"{not-json", "application/json")},
        )

    assert add_rule.status_code == 200
    assert update_rule.status_code == 200
    assert update_rule_missing.status_code == 404
    assert replace_root.status_code == 200
    assert add_child.status_code == 200
    assert update_node.status_code == 200
    assert delete_child.status_code == 200
    assert bad_child.status_code == 400
    assert delete_rule.status_code == 200
    assert delete_rule_missing.status_code == 404
    assert plant_add.status_code == 200
    assert swarm_add.status_code == 200
    assert plant_delete.status_code == 200
    assert plant_delete_missing.status_code == 404
    assert swarm_delete.status_code == 200
    assert swarm_delete_missing.status_code == 404
    assert clear_resp.status_code == 200
    assert export_invalid.status_code == 400
    assert load_invalid.status_code == 400
    assert import_invalid.status_code == 422


@pytest.mark.asyncio
async def test_scenario_import_reconstructs_triggers_and_substances() -> None:
    payload = _config_with_trigger().model_dump(mode="json")
    payload["flora_species"][0]["triggers"][0]["activation_condition"] = {
        "kind": "enemy_presence",
        "predator_species_id": 0,
        "min_predator_population": 3,
    }
    content = json.dumps(payload).encode("utf-8")

    async with _default_client() as client:
        resp = await client.post(
            "/api/scenario/import",
            files={"file": ("triggered.json", content, "application/json")},
        )

    draft = get_draft()
    assert resp.status_code == 200
    assert draft.mycorrhizal_growth_interval_ticks == 6
    assert len(draft.trigger_rules) == 1
    assert draft.trigger_rules[0].activation_condition == {
        "kind": "enemy_presence",
        "predator_species_id": 0,
        "min_predator_population": 3,
    }
    assert draft.substance_definitions[0].name == "Substance 0"


def test_websocket_stream_endpoints_close_cleanly() -> None:
    client = TestClient(app)

    with client.websocket_connect("/ws/simulation/stream") as websocket:
        close_message = websocket.receive()
    assert close_message["type"] == "websocket.close"
    assert close_message["code"] == 1008

    loop = SimulationLoop(_config_with_trigger())
    api_main._sim_loop = loop
    with client.websocket_connect("/ws/ui/stream") as websocket:
        payload = json.loads(websocket.receive_text())
    assert payload["tick"] == 0
    assert payload["grid_width"] == 8
