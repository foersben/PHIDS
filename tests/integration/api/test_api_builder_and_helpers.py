"""Experimental validation suite for test api builder and helpers.

This module defines hypothesis-driven checks for deterministic ecosystem behavior, API constraints, and simulation invariants. The tests map computational rules to biological interpretations, including metabolic attrition, trigger-gated signaling, and O(1) spatial locality assumptions, to ensure that implementation details remain aligned with the PHIDS scientific model.
"""

from __future__ import annotations

import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from httpx import AsyncClient
from starlette.requests import Request

from phids.api import main as api_main
from phids.api.main import app
from phids.api.presenters.dashboard import (
    build_draft_mycorrhizal_links,
    validate_cell_coordinates,
)
from phids.api.services.draft_service import DraftService
from phids.api.schemas import (
    DietCompatibilityMatrix,
    FloraSpeciesParams,
    InitialPlantPlacement,
    InitialSwarmPlacement,
    HerbivoreSpeciesParams,
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
from phids.api.routers.config import config_trigger_rule_condition_node_update

draft_service = DraftService()


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
        herbivore_species_id=0,
        min_herbivore_population=3,
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
        herbivore_species=[_herbivore(0)],
        diet_matrix=DietCompatibilityMatrix(rows=[[True]]),
        initial_plants=[InitialPlantPlacement(species_id=0, x=2, y=2, energy=10.0)],
        initial_swarms=[InitialSwarmPlacement(species_id=0, x=2, y=2, population=4, energy=5.0)],
        mycorrhizal_growth_interval_ticks=6,
    )


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    reset_draft()
    api_main._sim_loop = None
    api_main._sim_substance_names = {}


def test_main_substance_name_helpers_default_and_draft_overrides() -> None:
    """Verify substance naming helpers use defaults and honor draft-provided override labels."""
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


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("   ", None),
        (
            '{"kind":"herbivore_presence","herbivore_species_id":0,"min_herbivore_population":3}',
            {
                "kind": "herbivore_presence",
                "herbivore_species_id": 0,
                "min_herbivore_population": 3,
            },
        ),
        (
            '{"kind":"environmental_signal","signal_id":0,"min_concentration":0.2}',
            {
                "kind": "environmental_signal",
                "signal_id": 0,
                "min_concentration": 0.2,
            },
        ),
    ],
)
def test_main_activation_condition_json_parser_valid_cases(
    raw: str | None,
    expected: dict[str, object] | None,
) -> None:
    """Verify activation-condition parser returns normalized dicts for valid inputs."""
    assert api_main._parse_activation_condition_json(raw) == expected


@pytest.mark.parametrize("raw", ["{bad json", '{"kind":"substance_active"}'])
def test_main_activation_condition_json_parser_invalid_cases(raw: str) -> None:
    """Verify activation-condition parser raises on malformed JSON and invalid schemas."""
    with pytest.raises(HTTPException):
        api_main._parse_activation_condition_json(raw)


@pytest.mark.parametrize(
    ("condition", "herbivore_names", "substance_names", "expected"),
    [
        (None, None, None, "unconditional"),
        (
            {
                "kind": "herbivore_presence",
                "herbivore_species_id": 1,
                "min_herbivore_population": 4,
            },
            {1: "Beetles"},
            None,
            "Beetles ≥ 4",
        ),
        (
            {"kind": "substance_active", "substance_id": 7},
            None,
            {7: "Alarm"},
            "Alarm active",
        ),
        (
            {"kind": "environmental_signal", "signal_id": 0, "min_concentration": 0.25},
            None,
            {0: "Alarm"},
            "Alarm concentration ≥ 0.25",
        ),
        ({"kind": "all_of", "conditions": []}, None, None, "unconditional"),
        (
            {
                "kind": "any_of",
                "conditions": [
                    {
                        "kind": "herbivore_presence",
                        "herbivore_species_id": 0,
                        "min_herbivore_population": 2,
                    },
                    {"kind": "substance_active", "substance_id": 1},
                ],
            },
            {0: "Moths"},
            {1: "VOC"},
            "(Moths ≥ 2 OR VOC active)",
        ),
    ],
)
def test_main_activation_condition_descriptions(
    condition: dict[str, object] | None,
    herbivore_names: dict[int, str] | None,
    substance_names: dict[int, str] | None,
    expected: str,
) -> None:
    """Verify activation-condition description rendering for supported condition kinds."""
    assert (
        api_main._describe_activation_condition(
            condition,
            herbivore_names=herbivore_names,
            substance_names=substance_names,
        )
        == expected
    )


def test_main_trigger_rule_lookup_valid_and_missing_index() -> None:
    """Verify trigger-rule lookup returns existing entries and raises for missing indices."""
    draft = DraftState.default()
    draft.trigger_rules = [TriggerRule(flora_species_id=0, herbivore_species_id=0, substance_id=0)]
    assert api_main._trigger_rule_by_index(draft, 0).substance_id == 0
    with pytest.raises(HTTPException):
        api_main._trigger_rule_by_index(draft, 3)


@pytest.mark.parametrize(
    ("x", "y", "width", "height", "should_raise"),
    [(1, 1, 3, 3, False), (5, 1, 3, 3, True)],
)
def test_main_validate_cell_coordinates_cases(
    x: int,
    y: int,
    width: int,
    height: int,
    should_raise: bool,
) -> None:
    """Verify coordinate validation accepts in-bounds cells and rejects out-of-bounds cells."""
    if should_raise:
        with pytest.raises(HTTPException):
            validate_cell_coordinates(x, y, width, height)
        return
    validate_cell_coordinates(x, y, width, height)


@pytest.mark.parametrize(
    ("headers", "expected"),
    [([(b"hx-request", b"true")], True), ([], False)],
)
def test_main_is_htmx_request_cases(headers: list[tuple[bytes, bytes]], expected: bool) -> None:
    """Verify HTMX request detection for header-present and header-absent request scopes."""
    request = Request({"type": "http", "headers": headers})
    assert api_main._is_htmx_request(request) is expected


def test_main_build_draft_mycorrhizal_links_respects_interspecies_flag() -> None:
    """Verify draft link presenter marks inter-species links only when the feature flag is enabled."""
    draft = DraftState.default()
    draft.initial_plants = []
    draft_service.add_plant_placement(draft, 0, 1, 1, 10.0)
    draft_service.add_plant_placement(draft, 1, 2, 1, 10.0)
    assert build_draft_mycorrhizal_links(draft) == []
    draft.mycorrhizal_inter_species = True
    assert build_draft_mycorrhizal_links(draft)[0]["inter_species"] is True


@pytest.mark.parametrize(
    ("running", "paused", "terminated", "expected_label"),
    [
        (False, False, False, "Loaded"),
        (True, False, False, "Running"),
        (True, True, False, "Paused"),
        (False, False, True, "Terminated"),
    ],
)
def test_main_render_status_badge_states(
    running: bool,
    paused: bool,
    terminated: bool,
    expected_label: str,
) -> None:
    """Verify status badge labels map correctly to loaded-loop runtime flags."""
    loop = SimulationLoop(_config_with_trigger())
    api_main._sim_loop = loop
    loop.running = running
    loop.paused = paused
    loop.terminated = terminated
    assert expected_label in api_main._render_status_badge_html()


def test_main_request_helpers_get_loop_raises_when_unloaded_and_idle_badge_is_rendered() -> None:
    """Verify unloaded-loop helpers raise and render the Idle status badge."""
    with pytest.raises(HTTPException):
        api_main._get_loop()
    assert "Idle" in api_main._render_status_badge_html()


def test_main_live_summary_and_starving_swarm_helpers() -> None:
    """Test main live summary and starving swarm helpers.

    Asserts correct behavior of live summary and energy deficit swarm builders,
    ensuring they provide accurate ecological state information.
    """
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
    """Test condition node update for rules without conditions.

    Asserts that a root condition node is created with default settings when
    a trigger rule without an existing condition node is updated.
    """
    draft = get_draft()
    draft.substance_definitions = [SubstanceDefinition(substance_id=0, name="Signal A")]
    draft_service.add_trigger_rule(draft, 0, 0, 0)

    request = Request({"type": "http", "headers": []})
    response = await config_trigger_rule_condition_node_update(
        request,
        0,
        path="",
        kind="herbivore_presence",
        herbivore_species_id=0,
        min_herbivore_population=2,
        substance_id=None,
    )

    assert response.status_code == 200, response.body.decode()
    assert draft.trigger_rules[0].activation_condition == {
        "kind": "herbivore_presence",
        "herbivore_species_id": 0,
        "min_herbivore_population": 5,
    }


@pytest.mark.asyncio
async def test_builder_flora_routes_add_update_delete(api_client: AsyncClient) -> None:
    """Verify flora routes support add/update/delete and return 404 for missing species IDs."""
    add_resp = await api_client.post(
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
    update_resp = await api_client.put(
        "/api/config/flora/1",
        data={"name": "Oak Updated", "camouflage": "on", "camouflage_factor": -1.0},
    )
    delete_resp = await api_client.delete("/api/config/flora/1")
    delete_missing_resp = await api_client.delete("/api/config/flora/99")

    assert add_resp.status_code == 200, add_resp.text
    assert update_resp.status_code == 200, update_resp.text
    assert delete_resp.status_code == 200, delete_resp.text
    assert delete_missing_resp.status_code == 404, delete_missing_resp.text


@pytest.mark.asyncio
async def test_builder_herbivore_routes_add_update_delete(api_client: AsyncClient) -> None:
    """Verify herbivore routes support add/update/delete and return 404 for missing species IDs."""
    add_resp = await api_client.post(
        "/api/config/herbivores",
        data={"name": "Locust", "energy_min": 2.0, "velocity": 2, "consumption_rate": 3.5},
    )
    update_resp = await api_client.put(
        "/api/config/herbivores/1",
        data={"name": "Locust Updated", "velocity": 3},
    )
    delete_resp = await api_client.delete("/api/config/herbivores/1")
    delete_missing_resp = await api_client.delete("/api/config/herbivores/99")

    assert add_resp.status_code == 200, add_resp.text
    assert update_resp.status_code == 200, update_resp.text
    assert delete_resp.status_code == 200, delete_resp.text
    assert delete_missing_resp.status_code == 404, delete_missing_resp.text


@pytest.mark.asyncio
async def test_builder_substance_routes_and_diet_matrix_mutations(api_client: AsyncClient) -> None:
    """Verify substance CRUD routes and diet-matrix toggles mutate draft compatibility state."""
    add_resp = await api_client.post(
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
    update_resp = await api_client.put(
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
    toggle_resp = await api_client.post(
        "/api/matrices/diet",
        data={"herbivore_idx": 0, "flora_idx": 0, "compatible": "toggle"},
    )
    set_resp = await api_client.post(
        "/api/matrices/diet",
        data={"herbivore_idx": 0, "flora_idx": 0, "compatible": "false"},
    )
    out_of_range_resp = await api_client.post(
        "/api/matrices/diet",
        data={"herbivore_idx": 9, "flora_idx": 9, "compatible": "true"},
    )
    delete_resp = await api_client.delete("/api/config/substances/0")
    delete_missing_resp = await api_client.delete("/api/config/substances/99")

    assert add_resp.status_code == 200, add_resp.text
    assert update_resp.status_code == 200, update_resp.text
    assert toggle_resp.status_code == 200, toggle_resp.text
    assert set_resp.status_code == 200, set_resp.text
    assert out_of_range_resp.status_code == 200, out_of_range_resp.text
    assert delete_resp.status_code == 200, delete_resp.text
    assert delete_missing_resp.status_code == 404, delete_missing_resp.text
    assert get_draft().diet_matrix[0][0] is False


@pytest.mark.asyncio
async def test_builder_route_rule_of_16_branches(api_client: AsyncClient) -> None:
    """Test builder route rule with 16 branches.

    Asserts that adding new flora, herbivores, or substances beyond the 16 branch limit
    returns a 400 error, preventing overflow.
    """
    draft = get_draft()
    draft.flora_species = [_flora(i) for i in range(16)]
    draft.herbivore_species = [_herbivore(i) for i in range(16)]
    draft.substance_definitions = [
        SubstanceDefinition(substance_id=i, name=f"s{i}") for i in range(16)
    ]

    responses = {
        "/api/config/flora": await api_client.post("/api/config/flora", data={"name": "Overflow"}),
        "/api/config/herbivores": await api_client.post(
            "/api/config/herbivores", data={"name": "Overflow"}
        ),
        "/api/config/substances": await api_client.post(
            "/api/config/substances", data={"name": "Overflow"}
        ),
    }

    for path in ("/api/config/flora", "/api/config/herbivores", "/api/config/substances"):
        assert responses[path].status_code == 400, responses[path].text


@pytest.mark.asyncio
async def test_herbivore_routes_clamp_reproduction_divisor_to_physical_minimum(
    api_client: AsyncClient,
) -> None:
    """Herbivore add/update routes clamp reproduction divisor to avoid discounted offspring creation."""
    add_resp = await api_client.post(
        "/api/config/herbivores",
        data={
            "name": "ClampBug",
            "energy_min": 2.0,
            "velocity": 1,
            "consumption_rate": 1.0,
            "reproduction_energy_divisor": 0.25,
        },
    )

    update_resp = await api_client.put(
        "/api/config/herbivores/1",
        data={"reproduction_energy_divisor": 0.1},
    )

    assert add_resp.status_code == 200, add_resp.text
    assert update_resp.status_code == 200, update_resp.text
    draft = get_draft()
    herbivore = next(
        p
        for p in draft.herbivore_species
        if isinstance(p, HerbivoreSpeciesParams) and p.species_id == 1
    )
    assert herbivore.reproduction_energy_divisor == pytest.approx(1.0)


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
            "activation_condition_json": '{"kind":"herbivore_presence","herbivore_species_id":0,"min_herbivore_population":3}',
        },
    )
    update_resp = await api_client.put(
        "/api/config/trigger-rules/0",
        data={"substance_id": 1, "min_herbivore_population": 7},
    )
    update_missing_resp = await api_client.put(
        "/api/config/trigger-rules/9", data={"substance_id": 1}
    )
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
            "activation_condition_json": '{"kind":"herbivore_presence","herbivore_species_id":0,"min_herbivore_population":3}',
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


@pytest.mark.asyncio
async def test_scenario_import_reconstructs_triggers_and_substances(
    api_client: AsyncClient,
) -> None:
    """Test scenario import for triggers and substances reconstruction.

    Asserts that importing a scenario correctly reconstructs the associated triggers and
    substances, ensuring the ecological simulation can be accurately restored.
    """
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
    with client.websocket_connect("/ws/ui/stream") as websocket:
        payload = json.loads(websocket.receive_text())
    assert payload["tick"] == 0
    assert payload["grid_width"] == 8
    assert payload["grid_height"] == 8
    assert payload["all_flora_species"]
