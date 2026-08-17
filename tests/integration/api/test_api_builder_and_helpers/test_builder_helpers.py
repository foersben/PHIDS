# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Integration tests for PHIDS scenario builder helpers and condition parsing."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from phids.api import main as api_main
from phids.api.presenters.dashboard import (
    _default_substance_name,
    _describe_activation_condition,
    validate_cell_coordinates,
)
from phids.api.presenters.diagnostics import build_energy_deficit_swarms, build_live_summary, render_status_badge_html
from phids.api.routers.config.trigger_rules import config_trigger_rule_condition_node_update
from phids.api.schemas.placement import InitialPlantPlacement, InitialSwarmPlacement
from phids.api.schemas.simulation import SimulationConfig
from phids.api.schemas.species import DietCompatibilityMatrix, FloraSpeciesParams, HerbivoreSpeciesParams
from phids.api.schemas.triggers import HerbivoreAttackInitiator, SynthesizeSubstanceAction, TriggerConditionSchema
from phids.api.services.draft.trigger_rules import (
    add_trigger_rule,
    parse_activation_condition_json,
    trigger_rule_by_index,
)
from phids.api.ui_state.state import DraftState, get_draft, reset_draft
from phids.api.ui_state.substances import SubstanceDefinition
from phids.api.ui_state.triggers import ActivationConditionNode, TriggerRule
from phids.engine.components.substances import SubstanceComponent
from phids.engine.components.swarm import SwarmComponent
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
        reproduction_energy_divisor=2.0,
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
        grid_width=16,
        grid_height=16,
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


def test_substance_name_helpers_default_and_draft_overrides() -> None:
    """Verify substance naming helpers use defaults and honor draft-provided override labels."""
    assert _default_substance_name(2, is_toxin=False) == "Signal 2"
    assert _default_substance_name(3, is_toxin=True) == "Toxin 3"

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
def test_activation_condition_json_parser_valid_cases(
    raw: str | None,
    expected: ActivationConditionNode | None,
) -> None:
    """Verify activation-condition parser returns normalized dicts for valid inputs."""
    assert parse_activation_condition_json(raw) == expected


@pytest.mark.parametrize("raw", ["{bad json", '{"kind":"substance_active"}'])
def test_activation_condition_json_parser_invalid_cases(raw: str) -> None:
    """Verify activation-condition parser raises on malformed JSON and invalid schemas."""
    with pytest.raises(HTTPException):
        parse_activation_condition_json(raw)


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
def test_activation_condition_descriptions(
    condition: ActivationConditionNode | None,
    herbivore_names: dict[int, str] | None,
    substance_names: dict[int, str] | None,
    expected: str,
) -> None:
    """Verify activation-condition description rendering for supported condition kinds."""
    assert (
        _describe_activation_condition(
            condition,
            herbivore_names=herbivore_names,
            substance_names=substance_names,
        )
        == expected
    )


def test_trigger_rule_lookup_valid_and_missing_index() -> None:
    """Verify trigger-rule lookup returns existing entries and raises for missing indices."""
    draft = DraftState.default()
    draft.trigger_rules = [TriggerRule(flora_species_id=0, herbivore_species_id=0, substance_id=0)]
    assert trigger_rule_by_index(draft, 0).substance_id == 0
    with pytest.raises(HTTPException):
        trigger_rule_by_index(draft, 3)


@pytest.mark.parametrize(
    ("x", "y", "width", "height", "should_raise"),
    [(1, 1, 3, 3, False), (5, 1, 3, 3, True)],
)
def test_validate_cell_coordinates_cases(
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
    ("running", "paused", "terminated", "expected_label"),
    [
        (False, False, False, "Loaded"),
        (True, False, False, "Running"),
        (True, True, False, "Paused"),
        (False, False, True, "Terminated"),
    ],
)
def test_render_status_badge_states(
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
    assert expected_label in render_status_badge_html(api_main._sim_loop)


def test_request_helpers_get_loop_raises_when_unloaded_and_idle_badge_is_rendered() -> None:
    """Verify unloaded-loop helpers raise and render the Idle status badge."""
    with pytest.raises(HTTPException):
        api_main._get_loop()
    assert "Idle" in render_status_badge_html(api_main._sim_loop)


def test_live_summary_and_starving_swarm_helpers() -> None:
    """Test main live summary and starving swarm helpers."""
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

    summary = build_live_summary(api_main._sim_loop)
    starving = build_energy_deficit_swarms(api_main._sim_loop)

    assert summary is not None
    assert summary["plants"] == 1
    assert summary["swarms"] == 2
    assert summary["active_substances"] == 1
    assert starving[0]["energy_deficit"] >= starving[1]["energy_deficit"]
    assert any(swarm_entry["repelled"] is True for swarm_entry in starving)


@pytest.mark.asyncio
async def test_condition_node_update_creates_root_when_rule_has_no_condition() -> None:
    """Test condition node update for rules without conditions."""
    draft = get_draft()
    draft.substance_definitions = [SubstanceDefinition(substance_id=0, name="Signal A")]
    add_trigger_rule(draft, 0, 0, 0)

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
