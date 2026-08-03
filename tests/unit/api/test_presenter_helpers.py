# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Coverage reinforcement tests for API presenter helpers and trigger-rule editor utilities.

This module adds targeted regression checks for dashboard presenter helpers
and trigger-rule editor branches that are operationally important but
historically under-exercised by broad integration tests. The hypotheses validate
that type-coercion helpers, status badge rendering, and trigger-rule editor
utilities preserve deterministic behavior under edge-case parameterizations.

# MUTATION_TESTING_EXEMPTION (status badge HTML, HTMX header rendering):
# These branches emit HTML strings for HTMX partial rendering. Mutation
# testing of string-assembly code is excluded per the project decision matrix.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from phids.api import main as api_main
from phids.api.presenters.dashboard import (
    build_live_cell_details,
    build_live_dashboard_payload,
    build_preview_cell_details,
    extract_ui_snapshot,
    shared,
)
from phids.api.presenters.diagnostics import build_energy_deficit_swarms, render_status_badge_html
from phids.api.services.draft.placements import (
    add_plant_placement,
    add_swarm_placement,
)
from phids.api.services.draft.trigger_rules import (
    add_trigger_rule,
    default_activation_condition_for_rule,
    trigger_rule_by_index,
)
from phids.api.ui_state.state import DraftState, get_draft
from phids.api.ui_state.substances import SubstanceDefinition
from phids.engine.components.swarm import SwarmComponent
from phids.engine.loop import SimulationLoop


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
    ("input_val", "kwargs", "expected"),
    [
        (True, {"default": -9}, -9),
        (7, {}, 7),
        (4.8, {}, 4),
        ("12", {}, 12),
        ("bad", {"default": 5}, 5),
    ],
)
def test_coerce_int_cases(input_val: object, kwargs: dict[str, int], expected: int) -> None:
    """Validate integer coercion behavior across valid, invalid, and boolean inputs."""
    assert shared._coerce_int(input_val, **kwargs) == expected


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
def test_coerce_float_cases(
    input_val: object,
    kwargs: dict[str, float],
    expected: float,
) -> None:
    """Validate floating-point coercion behavior across valid, invalid, and boolean inputs."""
    assert shared._coerce_float(input_val, **kwargs) == pytest.approx(expected)


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
def test_default_activation_condition_supported_kinds(
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
    add_trigger_rule(
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

    condition = default_activation_condition_for_rule(draft, rule, kind)
    assert condition[field] == expected
    if secondary_field == "signal_id":
        assert condition[secondary_field] == secondary_expected
    elif secondary_field == "conditions.0.kind":
        assert condition["conditions"][0]["kind"] == secondary_expected


def test_default_activation_condition_invalid_kind_and_missing_trigger_index() -> None:
    """Validate unsupported condition kinds and out-of-range trigger indices raise HTTP errors."""
    draft = DraftState.default()
    add_trigger_rule(
        draft,
        flora_species_id=0,
        herbivore_species_id=0,
        substance_id=0,
        min_herbivore_population=2,
    )
    rule = draft.trigger_rules[0]

    with pytest.raises(HTTPException) as unsupported:
        default_activation_condition_for_rule(draft, rule, "invalid")
    assert unsupported.value.status_code == 400

    with pytest.raises(HTTPException) as not_found:
        trigger_rule_by_index(draft, 99)
    assert not_found.value.status_code == 404


def test_presenter_payload_helpers_status_badge_and_energy_deficit() -> None:
    """Exercise presenter payload helpers and status/energy helper branches.

    The test verifies that presenter payload builders return structurally valid dictionaries
    and that swarm energy-deficit ranking excludes satiated swarms while retaining stressed ones.
    """
    draft = get_draft()
    add_plant_placement(draft, 0, 2, 2, 12.0)
    add_swarm_placement(draft, 0, 2, 2, 4, 30.0)
    add_swarm_placement(draft, 0, 3, 3, 4, 1.0)
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
    dashboard = build_live_dashboard_payload(extract_ui_snapshot(loop), substance_names=api_main._sim_substance_names)

    assert live_cell["mode"] == "live"
    assert preview_cell["mode"] == "draft"
    assert "species_energy" in dashboard

    stressed = build_energy_deficit_swarms(api_main._sim_loop)
    assert len(stressed) == 1
    assert stressed[0]["energy_deficit"] > 0.0


def test_render_status_badge_idle_without_loaded_loop() -> None:
    """Validate that the status badge reports Idle when no loop is registered."""
    api_main._sim_loop = None
    assert "Idle" in render_status_badge_html(api_main._sim_loop)


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
    assert expected_label in render_status_badge_html(api_main._sim_loop)


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
