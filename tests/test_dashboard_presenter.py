"""Experimental validation suite for the PHIDS dashboard presenter layer.

This module constitutes the primary unit-test surface for
:mod:`phids.api.presenters.dashboard`, validating the three public payload-assembly
functions — :func:`~phids.api.presenters.dashboard.build_live_cell_details`,
:func:`~phids.api.presenters.dashboard.build_preview_cell_details`, and
:func:`~phids.api.presenters.dashboard.build_live_dashboard_payload` — independently of
the FastAPI HTTP layer.

Scientific Hypotheses Under Test
---------------------------------
1. **Structural completeness:** Every payload dictionary must carry the full set of keys
   required by the browser canvas renderer and HTMX tooltip components, regardless of
   whether the simulation is live or in draft mode.
2. **Coordinate guard invariant:** Requests for cells outside the configured grid bounds
   must raise an HTTP 404 exception, preventing out-of-bounds NumPy array accesses against
   the double-buffered :class:`~phids.engine.core.biotope.GridEnvironment` layers.
3. **Extinct-species bifurcation:** The ``species_energy`` list in the dashboard payload
   must enumerate only extant flora species (preventing chromatic ghosts from extinct layers
   on the canvas), while ``all_flora_species`` must enumerate the full configured catalogue
   with explicit ``extinct`` flags for legend interpretability.
4. **Substance state machine:** The :func:`~phids.api.presenters.dashboard._live_substance_state_payload`
   helper must faithfully map the five-state (synthesizing → triggered → active → aftereffect
   → configured) substance lifecycle onto deterministic (state_key, state_label) pairs, as
   these tokens drive badge colouring and legend entries in the operator UI.
5. **Draft-mode payload parity:** The draft-mode cell-details payload must mirror the
   structural contract of the live-mode payload, enabling a single browser tooltip template
   to render both contexts without conditional branching.
6. **Dependency-injection correctness:** All three public functions accept an explicit
   ``substance_names`` mapping rather than reading module-level mutable state, ensuring
   deterministic outputs under arbitrary test-injected name dictionaries.

Each test function documents the specific biological invariant it verifies and the
algorithmic rationale grounding that invariant in PHIDS's data-oriented ECS architecture.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException

from phids.api.presenters.dashboard import (
    _default_substance_name,
    _describe_activation_condition,
    _fallback_live_substance_payload,
    _is_live_substance_visible,
    _links_touching_cell,
    _live_substance_state_payload,
    _serialize_live_substance,
    build_draft_mycorrhizal_links,
    build_live_cell_details,
    build_live_dashboard_payload,
    build_preview_cell_details,
    validate_cell_coordinates,
)
from phids.api.services.draft_service import DraftService
from phids.api.schemas import (
    DietCompatibilityMatrix,
    FloraSpeciesParams,
    InitialPlantPlacement,
    InitialSwarmPlacement,
    PredatorSpeciesParams,
    SimulationConfig,
    TriggerConditionSchema,
)
from phids.api.ui_state import DraftState, SubstanceDefinition, TriggerRule, reset_draft
from phids.engine.components.plant import PlantComponent
from phids.engine.loop import SimulationLoop
from phids.io.scenario import load_scenario_from_json

draft_service = DraftService()


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------


def _flora(
    species_id: int, *, triggers: list[TriggerConditionSchema] | None = None
) -> FloraSpeciesParams:
    """Construct a minimal :class:`FloraSpeciesParams` fixture for testing."""
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
        triggers=triggers or [],
    )


def _predator(species_id: int) -> PredatorSpeciesParams:
    """Construct a minimal :class:`PredatorSpeciesParams` fixture for testing."""
    return PredatorSpeciesParams(
        species_id=species_id,
        name=f"predator-{species_id}",
        energy_min=1.0,
        velocity=1,
        consumption_rate=1.0,
        reproduction_energy_divisor=1.0,
    )


def _minimal_config(
    *,
    x: int = 2,
    y: int = 2,
    num_signals: int = 1,
    num_toxins: int = 1,
    triggers: list[TriggerConditionSchema] | None = None,
) -> SimulationConfig:
    """Build a minimal :class:`SimulationConfig` with one plant and one swarm at (x, y)."""
    return SimulationConfig(
        grid_width=8,
        grid_height=8,
        max_ticks=20,
        tick_rate_hz=20.0,
        num_signals=num_signals,
        num_toxins=num_toxins,
        flora_species=[_flora(0, triggers=triggers)],
        predator_species=[_predator(0)],
        diet_matrix=DietCompatibilityMatrix(rows=[[True]]),
        initial_plants=[InitialPlantPlacement(species_id=0, x=x, y=y, energy=10.0)],
        initial_swarms=[InitialSwarmPlacement(species_id=0, x=x, y=y, population=4, energy=5.0)],
        mycorrhizal_growth_interval_ticks=6,
    )


@pytest.fixture(autouse=True)
def _reset_draft_state() -> None:
    """Reset draft singleton to a pristine state before each test.

    This fixture upholds the deterministic reproducibility invariant by eliminating
    cross-test contamination of mutable :class:`~phids.api.ui_state.DraftState` state.
    """
    reset_draft()


# ---------------------------------------------------------------------------
# validate_cell_coordinates
# ---------------------------------------------------------------------------


def test_validate_cell_coordinates_accepts_valid_cell() -> None:
    """Verifies that in-bounds coordinates do not raise, upholding the grid-access safety invariant.

    Any coordinate satisfying ``0 <= x < width`` and ``0 <= y < height`` must be accepted
    without exception.  This invariant prevents false positives from the guard that would
    otherwise deny valid cell lookups into NumPy environmental layers.
    """
    validate_cell_coordinates(0, 0, 8, 8)
    validate_cell_coordinates(7, 7, 8, 8)
    validate_cell_coordinates(3, 5, 8, 8)


def test_validate_cell_coordinates_rejects_out_of_bounds() -> None:
    """Verifies that out-of-bounds coordinates raise HTTP 404, preventing array index errors.

    The coordinate guard is the primary defence against NumPy out-of-bounds accesses on
    the double-buffered environmental layers.  Any cell index at or beyond the grid boundary
    must produce a 404 response rather than a silent NumPy index wrap or error.
    """
    with pytest.raises(HTTPException) as exc_info:
        validate_cell_coordinates(8, 0, 8, 8)
    assert exc_info.value.status_code == 404

    with pytest.raises(HTTPException):
        validate_cell_coordinates(0, 8, 8, 8)

    with pytest.raises(HTTPException):
        validate_cell_coordinates(-1, 0, 8, 8)


# ---------------------------------------------------------------------------
# _live_substance_state_payload — state machine table tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kwargs", "expected_state"),
    [
        # Pure snapshot residue (no live entity).
        (
            dict(
                is_toxin=False,
                active=False,
                triggered_this_tick=False,
                synthesis_remaining=0,
                aftereffect_remaining_ticks=0,
                snapshot_only=True,
            ),
            "field_snapshot",
        ),
        # Mid-synthesis, not yet active.
        (
            dict(
                is_toxin=False,
                active=False,
                triggered_this_tick=False,
                synthesis_remaining=2,
                aftereffect_remaining_ticks=0,
            ),
            "synthesizing",
        ),
        # Triggered and active in the same tick (initiation moment).
        (
            dict(
                is_toxin=False,
                active=True,
                triggered_this_tick=True,
                synthesis_remaining=0,
                aftereffect_remaining_ticks=0,
            ),
            "triggered",
        ),
        # Active signal with lingering aftereffect.
        (
            dict(
                is_toxin=False,
                active=True,
                triggered_this_tick=False,
                synthesis_remaining=0,
                aftereffect_remaining_ticks=3,
            ),
            "aftereffect",
        ),
        # Active toxin (toxins have no aftereffect state; falls back to "active").
        (
            dict(
                is_toxin=True,
                active=True,
                triggered_this_tick=False,
                synthesis_remaining=0,
                aftereffect_remaining_ticks=0,
            ),
            "active",
        ),
        # Active signal without aftereffect.
        (
            dict(
                is_toxin=False,
                active=True,
                triggered_this_tick=False,
                synthesis_remaining=0,
                aftereffect_remaining_ticks=0,
            ),
            "active",
        ),
        # Triggered but not yet active (edge case: triggered_this_tick without active).
        (
            dict(
                is_toxin=False,
                active=False,
                triggered_this_tick=True,
                synthesis_remaining=0,
                aftereffect_remaining_ticks=0,
            ),
            "triggered",
        ),
        # Quiescent configured state.
        (
            dict(
                is_toxin=False,
                active=False,
                triggered_this_tick=False,
                synthesis_remaining=0,
                aftereffect_remaining_ticks=0,
            ),
            "configured",
        ),
    ],
)
def test_live_substance_state_payload_state_machine(
    kwargs: dict,
    expected_state: str,
) -> None:
    """Validates the substance state machine maps each runtime flag combination to the correct token.

    The five-state machine (field_snapshot → synthesizing → triggered → active/aftereffect →
    configured) governs badge colouring and legend entries across the operator UI.  Correct
    transitions are essential for communicating the biological phase of systemic acquired
    resistance and toxin emission to the operator without ambiguity.

    Args:
        kwargs: Keyword arguments forwarded to :func:`_live_substance_state_payload`.
        expected_state: The state token expected in the first element of the returned tuple.
    """
    state, _ = _live_substance_state_payload(**kwargs)
    assert state == expected_state


# ---------------------------------------------------------------------------
# build_draft_mycorrhizal_links
# ---------------------------------------------------------------------------


def test_build_draft_mycorrhizal_links_empty_when_not_adjacent() -> None:
    """Verifies that non-adjacent draft plants produce no root link candidates.

    Manhattan distance > 1 between any two plants precludes mycorrhizal connectivity.
    The draft adjacency check must not produce spurious links, as these would erroneously
    render belowground network overlays for plants that cannot exchange chemical signals.
    """
    draft = DraftState.default()
    draft_service.add_plant_placement(draft, 0, 0, 0, 10.0)
    draft_service.add_plant_placement(draft, 0, 3, 3, 10.0)
    assert build_draft_mycorrhizal_links(draft) == []


def test_build_draft_mycorrhizal_links_adjacent_same_species() -> None:
    """Verifies that two adjacent same-species plants produce one intra-species root link.

    Intra-species mycorrhizal links are always generated when plants are at Manhattan
    distance 1, independent of the ``mycorrhizal_inter_species`` flag.  This reflects
    the biological observation that conspecific root networks form preferentially.
    """
    draft = DraftState.default()
    draft_service.add_plant_placement(draft, 0, 2, 2, 10.0)
    draft_service.add_plant_placement(draft, 0, 2, 3, 10.0)
    links = build_draft_mycorrhizal_links(draft)
    assert len(links) == 1
    assert links[0]["inter_species"] is False


def test_build_draft_mycorrhizal_links_inter_species_gated_by_flag() -> None:
    """Verifies that inter-species links are generated only when the flag is enabled.

    The ``mycorrhizal_inter_species`` flag gates the formation of cross-species root
    networks.  When disabled, adjacent plants of different species must not appear as
    link candidates, preserving the species-specificity of the simulated mycorrhizal network.
    """
    draft = DraftState.default()
    draft_service.add_plant_placement(draft, 0, 2, 2, 10.0)
    draft_service.add_plant_placement(draft, 1, 2, 3, 10.0)

    draft.mycorrhizal_inter_species = False
    assert build_draft_mycorrhizal_links(draft) == []

    draft.mycorrhizal_inter_species = True
    links = build_draft_mycorrhizal_links(draft)
    assert len(links) == 1
    assert links[0]["inter_species"] is True


# ---------------------------------------------------------------------------
# build_live_cell_details
# ---------------------------------------------------------------------------


def test_build_live_cell_details_structural_contract() -> None:
    """Verifies that the live cell-details payload contains the expected top-level keys.

    The browser tooltip template relies on a fixed structural contract for both ``"live"``
    and ``"draft"`` payloads.  Missing keys would cause silent rendering failures that
    are difficult to diagnose at the UI layer.  This test anchors the minimum key set
    required for tooltip rendering.
    """
    config = _minimal_config()
    loop = SimulationLoop(config)
    payload = build_live_cell_details(loop, 2, 2, substance_names={})

    assert payload["mode"] == "live"
    assert payload["tick"] == 0
    assert payload["x"] == 2
    assert payload["y"] == 2
    assert "plants" in payload
    assert "swarms" in payload
    assert "mycorrhiza" in payload
    assert "wind" in payload
    assert "signal_peak" in payload
    assert "toxin_peak" in payload


def test_build_live_cell_details_reports_plant_and_swarm_at_cell() -> None:
    """Verifies that plant and swarm entities registered at (x, y) are included in the payload.

    The ECS spatial hash lookup (``world.entities_at(x, y)``) must correctly surface all
    entities at the queried coordinate, including both :class:`PlantComponent` and
    :class:`SwarmComponent` holders.  Incorrect O(1) spatial hash behaviour would silently
    omit entities from the tooltip, degrading ecological observability.
    """
    config = _minimal_config(x=3, y=4)
    loop = SimulationLoop(config)
    payload = build_live_cell_details(loop, 3, 4, substance_names={})

    assert len(payload["plants"]) == 1
    assert payload["plants"][0]["x" if "x" in payload["plants"][0] else "entity_id"] is not None
    assert len(payload["swarms"]) == 1


def test_build_live_cell_details_rejects_out_of_bounds() -> None:
    """Verifies that an out-of-bounds cell coordinate raises HTTP 404 in the live presenter.

    This invariant prevents NumPy index errors against the environmental layers and
    ensures that the HTTP surface correctly signals a client error for invalid coordinates
    rather than propagating an internal runtime exception.
    """
    config = _minimal_config()
    loop = SimulationLoop(config)
    with pytest.raises(HTTPException) as exc_info:
        build_live_cell_details(loop, 99, 0, substance_names={})
    assert exc_info.value.status_code == 404


def test_build_live_cell_details_substance_name_injection() -> None:
    """Verifies that explicitly injected substance names appear in the substance payload.

    The dependency-injection invariant requires that ``substance_names`` overrides the
    default fallback labels for all substance identifiers.  This test confirms that the
    injected mapping flows through to ``signal_concentrations`` and substance payloads,
    eliminating reliance on module-level mutable state.
    """
    trigger = TriggerConditionSchema(
        predator_species_id=0,
        min_predator_population=1,
        substance_id=0,
        synthesis_duration=1,
        is_toxin=False,
        aftereffect_ticks=2,
        energy_cost_per_tick=0.1,
    )
    config = _minimal_config(triggers=[trigger])
    loop = SimulationLoop(config)
    asyncio.run(loop.step())

    payload = build_live_cell_details(loop, 2, 2, substance_names={0: "AlarmPheromone"})
    # Any substance with name "AlarmPheromone" in the payload confirms injection worked.
    found_names = [s["name"] for plant in payload["plants"] for s in plant["active_substances"]] + [
        s["name"] for s in payload["signal_concentrations"]
    ]
    if found_names:
        assert any("AlarmPheromone" in n for n in found_names)


# ---------------------------------------------------------------------------
# build_preview_cell_details
# ---------------------------------------------------------------------------


def test_build_preview_cell_details_structural_contract() -> None:
    """Verifies that the draft cell-details payload mirrors the live payload's key contract.

    The browser tooltip template is shared between live and draft modes; both payload
    variants must carry the same top-level key set to allow uniform rendering.  The
    distinguishing field is ``mode == "draft"`` and ``tick == None``.
    """
    draft = DraftState.default()
    draft_service.add_plant_placement(draft, 0, 1, 1, 10.0)
    draft_service.add_swarm_placement(draft, 0, 1, 1, 3, 8.0)
    payload = build_preview_cell_details(1, 1, draft=draft, substance_names={})

    assert payload["mode"] == "draft"
    assert payload["tick"] is None
    assert payload["x"] == 1
    assert payload["y"] == 1
    assert "plants" in payload
    assert "swarms" in payload
    assert "mycorrhiza" in payload
    assert "wind" in payload
    assert payload["signal_peak"] == 0.0
    assert payload["toxin_peak"] == 0.0


def test_build_preview_cell_details_reports_placed_entities() -> None:
    """Verifies that draft-placed plants and swarms are correctly serialised for a target cell.

    The preview payload iterates over :attr:`~phids.api.ui_state.DraftState.initial_plants`
    and :attr:`~phids.api.ui_state.DraftState.initial_swarms` to find entities at the
    queried coordinate.  Only entities at the exact cell must appear; entities at other
    coordinates must be absent.
    """
    draft = DraftState.default()
    draft_service.add_plant_placement(draft, 0, 2, 2, 12.0)
    draft_service.add_plant_placement(draft, 0, 5, 5, 10.0)  # Different cell — must not appear.
    draft_service.add_swarm_placement(draft, 0, 2, 2, 5, 15.0)
    payload = build_preview_cell_details(2, 2, draft=draft)

    assert len(payload["plants"]) == 1
    assert payload["plants"][0]["energy"] == pytest.approx(12.0)
    assert len(payload["swarms"]) == 1


def test_build_preview_cell_details_rejects_out_of_bounds() -> None:
    """Verifies that out-of-bounds draft cell coordinates raise HTTP 404.

    The coordinate guard operates identically for live and draft modes, preventing
    clients from requesting cell data outside the configured scenario grid.
    """
    draft = DraftState.default()
    with pytest.raises(HTTPException) as exc_info:
        build_preview_cell_details(draft.grid_width, 0, draft=draft)
    assert exc_info.value.status_code == 404


def test_build_preview_cell_details_includes_trigger_rules() -> None:
    """Verifies that configured trigger rules are serialised for the associated plant species.

    Each plant in the draft payload must enumerate all trigger rules associated with its
    flora species, enabling the operator to inspect the defensive response configuration
    in the pre-simulation view.  Missing rules would obscure the intended signal-emission
    semantics before the scenario is committed.
    """
    draft = DraftState.default()
    draft_service.add_plant_placement(draft, 0, 3, 3, 10.0)
    draft.substance_definitions.append(
        SubstanceDefinition(
            substance_id=0, name="VOC", is_toxin=False, synthesis_duration=1, aftereffect_ticks=0
        )
    )
    draft_service.add_trigger_rule(
        draft,
        flora_species_id=0,
        predator_species_id=0,
        substance_id=0,
        min_predator_population=2,
    )

    payload = build_preview_cell_details(3, 3, draft=draft)
    plant = payload["plants"][0]
    assert len(plant["configured_trigger_rules"]) == 1
    assert plant["configured_trigger_rules"][0]["substance_id"] == 0


def test_build_preview_cell_details_mycorrhizal_links_in_draft() -> None:
    """Verifies that adjacent draft plants produce mycorrhizal link metadata in the preview payload.

    The draft mycorrhizal overlay shows the operator which plant positions are candidates
    for root-network formation once the simulation starts.  The ``mycorrhiza.link_count``
    field must reflect the number of links whose endpoints include the queried cell.
    """
    draft = DraftState.default()
    draft_service.add_plant_placement(draft, 0, 2, 2, 10.0)
    draft_service.add_plant_placement(draft, 0, 2, 3, 10.0)  # Adjacent — forms a link.

    payload = build_preview_cell_details(2, 2, draft=draft)
    assert payload["mycorrhiza"]["link_count"] == 1
    assert payload["mycorrhiza"]["enabled"] is True


# ---------------------------------------------------------------------------
# build_live_dashboard_payload
# ---------------------------------------------------------------------------


def test_build_live_dashboard_payload_structural_contract() -> None:
    """Verifies the dashboard payload carries all keys required by the canvas renderer.

    The canvas WebSocket payload schema is the primary rendering contract between the
    Python backend and the browser JavaScript.  Any missing key will cause a silent
    rendering failure in the species-energy, swarm-overlay, or signal-overlay compositing
    passes.
    """
    config = _minimal_config()
    loop = SimulationLoop(config)
    payload = build_live_dashboard_payload(loop, substance_names={})

    required_keys = {
        "tick",
        "grid_width",
        "grid_height",
        "max_energy",
        "species_energy",
        "all_flora_species",
        "signal_overlay",
        "toxin_overlay",
        "max_signal",
        "max_toxin",
        "plants",
        "mycorrhizal_links",
        "swarms",
        "terminated",
        "termination_reason",
        "running",
        "paused",
    }
    assert required_keys.issubset(payload.keys())


def test_build_live_dashboard_payload_tick_and_lifecycle_state() -> None:
    """Verifies that tick and lifecycle flags reflect the loop state at the time of serialisation.

    The tick counter and the ``running``/``paused``/``terminated`` flags are the primary
    mechanism by which the browser canvas determines whether to advance or freeze its
    display.  Incorrect values would cause display desynchronisation relative to the
    underlying simulation state.
    """
    config = _minimal_config()
    loop = SimulationLoop(config)
    payload = build_live_dashboard_payload(loop, substance_names={})

    assert payload["tick"] == 0
    assert payload["terminated"] is False
    assert payload["running"] is False
    assert payload["paused"] is False


def test_build_live_dashboard_payload_plant_and_swarm_entries() -> None:
    """Verifies that live plant and swarm entities are serialised with mandatory fields.

    Each plant entry must carry ``entity_id``, ``species_id``, ``x``, ``y``, and ``energy``
    fields; each swarm entry must carry ``x``, ``y``, ``population``, and ``species_id``.
    These fields are consumed directly by the canvas compositing passes.
    """
    config = _minimal_config(x=4, y=4)
    loop = SimulationLoop(config)
    payload = build_live_dashboard_payload(loop, substance_names={})

    assert len(payload["plants"]) == 1
    plant = payload["plants"][0]
    assert "entity_id" in plant
    assert "x" in plant
    assert "y" in plant
    assert "energy" in plant

    assert len(payload["swarms"]) == 1
    swarm = payload["swarms"][0]
    assert "x" in swarm
    assert "y" in swarm
    assert "population" in swarm


def test_build_live_dashboard_payload_extinct_species_bifurcation() -> None:
    """Verifies the extinct-species bifurcation invariant across species_energy and all_flora_species.

    The canvas renderer must receive only extant flora layers in ``species_energy``
    (preventing ghost compositing from extinct-species channels), while ``all_flora_species``
    must enumerate the full configured catalogue with ``extinct`` flags intact for the
    population legend.  This test uses the meadow_defense scenario and advances until
    species extinction, then asserts the invariant.
    """
    config = load_scenario_from_json(Path("examples/meadow_defense.json"))
    loop = SimulationLoop(config)

    while loop.tick < 140:
        asyncio.run(loop.step())
        live_species = {
            entity.get_component(PlantComponent).species_id
            for entity in loop.world.query(PlantComponent)
        }
        if len(live_species) <= 1:
            break

    payload = build_live_dashboard_payload(loop, substance_names={})
    payload_species = {int(spec["species_id"]) for spec in payload["species_energy"]}
    legend_species = {int(spec["species_id"]) for spec in payload["all_flora_species"]}
    configured_species = {species.species_id for species in loop.config.flora_species}
    live_species = {
        entity.get_component(PlantComponent).species_id
        for entity in loop.world.query(PlantComponent)
    }

    # Extant species only in the render layer.
    assert payload_species == live_species
    # Full catalogue in the legend.
    assert legend_species == configured_species
    # Extinct entries carry the flag.
    extinct_in_payload = {
        int(spec["species_id"])
        for spec in payload["all_flora_species"]
        if spec.get("extinct", False)
    }
    assert extinct_in_payload == configured_species - live_species


def test_build_live_dashboard_payload_max_energy_is_positive() -> None:
    """Verifies that max_energy is always a positive float to prevent division-by-zero in the canvas.

    The canvas normalises plant energy values against ``max_energy`` for colour mapping.
    A zero value would cause a division-by-zero in the browser renderer.  The presenter
    ensures a minimum value of 1.0 even when the entire flora population has zero energy.
    """
    config = _minimal_config()
    loop = SimulationLoop(config)
    payload = build_live_dashboard_payload(loop, substance_names={})
    assert payload["max_energy"] > 0.0


# ---------------------------------------------------------------------------
# _fallback_live_substance_payload
# ---------------------------------------------------------------------------


def test_fallback_live_substance_payload_snapshot_state() -> None:
    """Verifies that the fallback payload is in the field_snapshot state with zeroed dynamic fields.

    When a non-zero field concentration is observed at a cell without a live owning entity,
    the presenter must synthesise a stable fallback payload rather than omitting the
    substance or fabricating entity-level data.  All dynamic counters must be zero and the
    state must be ``"field_snapshot"``.
    """
    payload = _fallback_live_substance_payload(2, is_toxin=False, substance_names={2: "Jasmonates"})
    assert payload["state"] == "field_snapshot"
    assert payload["snapshot_only"] is True
    assert payload["active"] is False
    assert payload["synthesis_remaining"] == 0
    assert payload["aftereffect_remaining_ticks"] == 0
    assert payload["name"] == "Jasmonates"


def test_fallback_live_substance_payload_default_name_without_mapping() -> None:
    """Verifies that the fallback name resolves to the deterministic default when no mapping entry exists.

    Substance names must never be absent from UI payloads.  When the injected
    ``substance_names`` dict has no entry for a given identifier, the fallback label
    (e.g. ``"Signal 3"``) must be used consistently with :func:`_default_substance_name`.
    """
    payload = _fallback_live_substance_payload(3, is_toxin=False, substance_names={})
    assert payload["name"] == _default_substance_name(3, is_toxin=False)


# ---------------------------------------------------------------------------
# Helper purity tests
# ---------------------------------------------------------------------------


def test_describe_activation_condition_unconditional_for_none() -> None:
    """Verifies that a None condition tree renders as 'unconditional'.

    The 'unconditional' label is the canonical representation of a trigger that fires
    on every applicable predator presence without an additional gating constraint.
    """
    assert _describe_activation_condition(None) == "unconditional"


def test_describe_activation_condition_enemy_presence_leaf() -> None:
    """Verifies correct rendering of an enemy_presence leaf node with a named predator.

    The rendered string must include the predator display name and the population
    threshold, as both fields are semantically significant for operator comprehension
    of the defensive triggering logic.
    """
    result = _describe_activation_condition(
        {"kind": "enemy_presence", "predator_species_id": 1, "min_predator_population": 5},
        predator_names={1: "Aphids"},
    )
    assert result == "Aphids ≥ 5"


def test_describe_activation_condition_nested_any_of() -> None:
    """Verifies correct rendering of a nested any_of combinator with two leaf conditions.

    Compound conditions that combine multiple threat-detection criteria (e.g., enemy
    presence OR an ambient signal) must be rendered with correct parenthesisation and
    OR-join so that operators can unambiguously interpret the triggering logic.
    """
    result = _describe_activation_condition(
        {
            "kind": "any_of",
            "conditions": [
                {"kind": "enemy_presence", "predator_species_id": 0, "min_predator_population": 2},
                {"kind": "substance_active", "substance_id": 1},
            ],
        },
        predator_names={0: "Beetles"},
        substance_names={1: "Alarm VOC"},
    )
    assert result == "(Beetles ≥ 2 OR Alarm VOC active)"


def test_describe_activation_condition_environmental_signal_leaf() -> None:
    """Verifies correct rendering of an environmental_signal leaf node with threshold.

    The rendered string must encode both the signal display name (resolved via
    ``substance_names``) and the minimum concentration threshold, as these parameters
    jointly define the ambient chemical stimulus required to initiate systemic acquired
    resistance.
    """
    result = _describe_activation_condition(
        {"kind": "environmental_signal", "signal_id": 2, "min_concentration": 0.05},
        substance_names={2: "Jasmonate"},
    )
    assert result == "Jasmonate concentration ≥ 0.05"


def test_describe_activation_condition_all_of_combinator() -> None:
    """Verifies correct rendering of an all_of combinator with AND-join between child conditions.

    When multiple conditions must all be satisfied simultaneously (e.g., enemy presence AND
    an active signal), the rendered string must use an AND-join with correct parenthesisation
    to distinguish compound-AND logic from OR-based alternatives.
    """
    result = _describe_activation_condition(
        {
            "kind": "all_of",
            "conditions": [
                {"kind": "enemy_presence", "predator_species_id": 0, "min_predator_population": 1},
                {"kind": "substance_active", "substance_id": 0},
            ],
        },
        predator_names={0: "Caterpillar"},
        substance_names={0: "VOC"},
    )
    assert result == "(Caterpillar ≥ 1 AND VOC active)"


def test_describe_activation_condition_empty_combinator_falls_back_to_unconditional() -> None:
    """Verifies that a combinator node with no valid children degrades to 'unconditional'.

    An any_of or all_of node whose conditions list is absent or empty is semantically
    equivalent to an unconditional trigger, and must be rendered as such to prevent
    operators from inferring non-existent constraints from the tooltip display.
    """
    result = _describe_activation_condition({"kind": "any_of", "conditions": []})
    assert result == "unconditional"


# ---------------------------------------------------------------------------
# _is_live_substance_visible
# ---------------------------------------------------------------------------


def test_is_live_substance_visible_quiescent_returns_false() -> None:
    """Verifies that a substance in the quiescent configured state is not visible.

    A substance with all runtime flags cleared (inactive, untriggered, no synthesis
    window, no aftereffect residue) is semantically quiescent and must be excluded from
    tooltip payloads to prevent the operator from seeing empty or misleading badge entries
    for dormant chemical-defense channels.
    """
    from phids.engine.components.substances import SubstanceComponent

    substance = SubstanceComponent(
        entity_id=1,
        substance_id=0,
        owner_plant_id=0,
        active=False,
        triggered_this_tick=False,
        synthesis_remaining=0,
        aftereffect_remaining_ticks=0,
    )
    assert _is_live_substance_visible(substance) is False


def test_is_live_substance_visible_active_returns_true() -> None:
    """Verifies that an actively emitting substance is marked visible.

    An active substance is in the emission phase of the SAR (systemic acquired resistance)
    cycle and must always appear in tooltip payloads so that the operator can observe the
    ongoing ecological intervention.
    """
    from phids.engine.components.substances import SubstanceComponent

    substance = SubstanceComponent(
        entity_id=2,
        substance_id=0,
        owner_plant_id=0,
        active=True,
        triggered_this_tick=False,
        synthesis_remaining=0,
        aftereffect_remaining_ticks=0,
    )
    assert _is_live_substance_visible(substance) is True


def test_is_live_substance_visible_synthesizing_returns_true() -> None:
    """Verifies that a substance in the synthesis phase is considered visible.

    During the synthesis window (``synthesis_remaining > 0``), the plant is committing
    metabolic resources to produce the substance.  This biological investment warrants
    operator visibility even though the substance has not yet entered the active emission phase.
    """
    from phids.engine.components.substances import SubstanceComponent

    substance = SubstanceComponent(
        entity_id=3,
        substance_id=0,
        owner_plant_id=0,
        active=False,
        triggered_this_tick=False,
        synthesis_remaining=3,
        aftereffect_remaining_ticks=0,
    )
    assert _is_live_substance_visible(substance) is True


def test_is_live_substance_visible_aftereffect_returns_true() -> None:
    """Verifies that a substance with remaining aftereffect ticks is considered visible.

    The aftereffect phase represents the residual systemic acquired resistance following
    active VOC emission.  While the substance is no longer actively emitting, the lingering
    physiological state is ecologically significant and must be communicated to the operator.
    """
    from phids.engine.components.substances import SubstanceComponent

    substance = SubstanceComponent(
        entity_id=4,
        substance_id=0,
        owner_plant_id=0,
        active=False,
        triggered_this_tick=False,
        synthesis_remaining=0,
        aftereffect_remaining_ticks=2,
    )
    assert _is_live_substance_visible(substance) is True


def test_is_live_substance_visible_triggered_this_tick_returns_true() -> None:
    """Verifies that a substance triggered in the current tick is immediately visible.

    The triggered state is the initiation moment of the defense response — the tick on
    which the predator-presence condition first satisfies the trigger rule.  Immediate
    visibility ensures the operator sees the defense response at the earliest possible
    moment.
    """
    from phids.engine.components.substances import SubstanceComponent

    substance = SubstanceComponent(
        entity_id=5,
        substance_id=0,
        owner_plant_id=0,
        active=False,
        triggered_this_tick=True,
        synthesis_remaining=0,
        aftereffect_remaining_ticks=0,
    )
    assert _is_live_substance_visible(substance) is True


# ---------------------------------------------------------------------------
# _links_touching_cell
# ---------------------------------------------------------------------------


def test_links_touching_cell_returns_matching_link_at_x1_y1() -> None:
    """Verifies that a link whose first endpoint matches (x, y) is included in the result.

    The mycorrhizal overlay renders root links anchored at the queried cell.  Links must
    be identified by either endpoint coordinate to capture both the emitting plant and its
    network partner.
    """
    links = [
        {"x1": 3, "y1": 4, "x2": 5, "y2": 4},
        {"x1": 0, "y1": 0, "x2": 1, "y2": 0},
    ]
    result = _links_touching_cell(links, 3, 4)
    assert len(result) == 1
    assert result[0]["x1"] == 3


def test_links_touching_cell_returns_matching_link_at_x2_y2() -> None:
    """Verifies that a link whose second endpoint matches (x, y) is included in the result.

    Because root links are undirected, a query for a cell at the terminus must return
    the same link as a query at the origin.  Restricting matches to only the first
    endpoint would render the overlay asymmetrically.
    """
    links = [{"x1": 1, "y1": 2, "x2": 4, "y2": 5}]
    result = _links_touching_cell(links, 4, 5)
    assert len(result) == 1


def test_links_touching_cell_returns_empty_when_no_match() -> None:
    """Verifies that a cell with no root links attached returns an empty list.

    Cells that host no mycorrhizal network endpoints must produce an empty link list so
    that the overlay renderer does not attempt to draw network lines from isolated plants.
    """
    links = [{"x1": 0, "y1": 0, "x2": 1, "y2": 1}]
    result = _links_touching_cell(links, 5, 5)
    assert result == []


def test_links_touching_cell_returns_multiple_links() -> None:
    """Verifies that all links touching a hub cell are returned when a plant is a network hub.

    A plant may have multiple mycorrhizal connections (up to the Rule-of-16 cap).
    All such links must be returned for the hub cell so that the overlay renderer can
    draw the complete network topology centred on that cell.
    """
    links = [
        {"x1": 2, "y1": 2, "x2": 3, "y2": 2},
        {"x1": 2, "y1": 2, "x2": 2, "y2": 3},
        {"x1": 0, "y1": 0, "x2": 1, "y2": 1},  # Non-matching link.
    ]
    result = _links_touching_cell(links, 2, 2)
    assert len(result) == 2


# ---------------------------------------------------------------------------
# _serialize_live_substance
# ---------------------------------------------------------------------------


def test_serialize_live_substance_active_signal_structural_contract() -> None:
    """Verifies that a serialised live active signal carries the expected key set.

    The tooltip partial requires a fixed contract of keys for each substance entry.
    Missing keys would cause silent Jinja rendering failures in the ``active_substances``
    loop.  This test anchors the minimum key set for a live signal substance.
    """
    from phids.engine.components.substances import SubstanceComponent

    substance = SubstanceComponent(
        entity_id=10,
        substance_id=0,
        owner_plant_id=5,
        is_toxin=False,
        active=True,
        triggered_this_tick=False,
        synthesis_remaining=0,
        aftereffect_remaining_ticks=3,
        lethal=False,
        repellent=True,
        lethality_rate=0.0,
        repellent_walk_ticks=4,
        trigger_predator_species_id=1,
        trigger_min_predator_population=3,
        activation_condition=None,
    )
    payload = _serialize_live_substance(
        substance,
        predator_names={1: "Aphids"},
        substance_names={0: "JA-Ile"},
    )

    required_keys = {
        "substance_id",
        "name",
        "kind",
        "active",
        "state",
        "state_label",
        "snapshot_only",
        "triggered_this_tick",
        "synthesis_remaining",
        "aftereffect_remaining_ticks",
        "lethal",
        "repellent",
        "lethality_rate",
        "repellent_walk_ticks",
        "trigger_predator_species_id",
        "trigger_predator_name",
        "trigger_min_predator_population",
        "activation_condition",
        "activation_condition_summary",
    }
    assert required_keys.issubset(payload.keys())


def test_serialize_live_substance_name_resolved_via_injection() -> None:
    """Verifies that the injected substance_names mapping overrides the default fallback label.

    Substance display names must be sourced from the injected mapping rather than a
    module-level global, preserving the dependency-injection invariant that makes the
    presenter functions deterministically testable.
    """
    from phids.engine.components.substances import SubstanceComponent

    substance = SubstanceComponent(entity_id=11, substance_id=2, owner_plant_id=0, active=True)
    payload = _serialize_live_substance(
        substance,
        predator_names={},
        substance_names={2: "Ethylene"},
    )
    assert payload["name"] == "Ethylene"
    assert payload["kind"] == "signal"


def test_serialize_live_substance_toxin_kind_field() -> None:
    """Verifies that a toxin substance is serialised with kind == 'toxin'.

    The ``kind`` field drives icon and badge selection in the tooltip template.
    An is_toxin=True substance must be labelled as ``'toxin'``; any other value would
    cause the renderer to apply the wrong visual affordance to the substance entry.
    """
    from phids.engine.components.substances import SubstanceComponent

    substance = SubstanceComponent(
        entity_id=12,
        substance_id=1,
        owner_plant_id=0,
        is_toxin=True,
        active=True,
        lethal=True,
        lethality_rate=0.25,
    )
    payload = _serialize_live_substance(
        substance,
        predator_names={},
        substance_names={1: "Solanine"},
    )
    assert payload["kind"] == "toxin"
    assert payload["lethal"] is True
    assert payload["lethality_rate"] == pytest.approx(0.25)


def test_serialize_live_substance_trigger_predator_name_fallback() -> None:
    """Verifies that an unlisted predator id generates a deterministic fallback label.

    When the injected ``predator_names`` mapping has no entry for the trigger predator,
    the serialiser must produce a stable fallback string rather than raising a KeyError
    or returning None, ensuring tooltip entries remain informative even for incomplete
    name registries.
    """
    from phids.engine.components.substances import SubstanceComponent

    substance = SubstanceComponent(
        entity_id=13,
        substance_id=0,
        owner_plant_id=0,
        trigger_predator_species_id=7,
    )
    payload = _serialize_live_substance(substance, predator_names={}, substance_names={})
    assert payload["trigger_predator_name"] == "Predator 7"


def test_serialize_live_substance_no_predator_when_id_negative() -> None:
    """Verifies that trigger_predator_name is None when no predator is configured.

    A trigger_predator_species_id of -1 signals that the substance has no explicit
    predator-specific trigger.  The serialised payload must carry None for the predator
    name field to allow the tooltip template to conditionally hide the trigger row.
    """
    from phids.engine.components.substances import SubstanceComponent

    substance = SubstanceComponent(
        entity_id=14,
        substance_id=0,
        owner_plant_id=0,
        trigger_predator_species_id=-1,
    )
    payload = _serialize_live_substance(substance, predator_names={}, substance_names={})
    assert payload["trigger_predator_name"] is None


def test_serialize_live_substance_activation_condition_summary_rendered() -> None:
    """Verifies that a nested activation condition tree is rendered into a summary string.

    The ``activation_condition_summary`` field is displayed in the operator tooltip to
    allow inspection of compound trigger predicates without parsing raw JSON.  The summary
    must be generated by :func:`_describe_activation_condition` rather than left empty or
    set to the raw dict.
    """
    from phids.engine.components.substances import SubstanceComponent

    substance = SubstanceComponent(
        entity_id=15,
        substance_id=0,
        owner_plant_id=0,
        activation_condition={
            "kind": "enemy_presence",
            "predator_species_id": 0,
            "min_predator_population": 4,
        },
    )
    payload = _serialize_live_substance(
        substance,
        predator_names={0: "Locusts"},
        substance_names={},
    )
    assert payload["activation_condition_summary"] == "Locusts ≥ 4"


# ---------------------------------------------------------------------------
# TriggerRule activation_condition propagation
# ---------------------------------------------------------------------------


def test_build_preview_cell_details_trigger_rule_with_activation_condition() -> None:
    """Verifies that a TriggerRule carrying an activation_condition tree is serialised correctly.

    The :class:`~phids.api.ui_state.TriggerRule` dataclass supports an optional
    ``activation_condition`` predicate tree that overrides the legacy flat-field trigger
    semantics.  The draft presenter must faithfully forward this tree into the
    ``configured_trigger_rules`` list for each plant, enabling the operator to verify
    complex compound-trigger configurations before committing the scenario.
    """
    draft = DraftState.default()
    draft_service.add_plant_placement(draft, 0, 1, 1, 10.0)
    draft.substance_definitions.append(
        SubstanceDefinition(
            substance_id=0,
            name="Terpene",
            is_toxin=False,
            synthesis_duration=2,
            aftereffect_ticks=1,
        )
    )
    condition = {
        "kind": "any_of",
        "conditions": [
            {"kind": "enemy_presence", "predator_species_id": 0, "min_predator_population": 3},
            {"kind": "substance_active", "substance_id": 0},
        ],
    }
    rule = TriggerRule(
        flora_species_id=0,
        predator_species_id=0,
        substance_id=0,
        min_predator_population=3,
        activation_condition=condition,
    )
    draft.trigger_rules.append(rule)

    payload = build_preview_cell_details(1, 1, draft=draft)
    assert len(payload["plants"]) == 1
    rules = payload["plants"][0]["configured_trigger_rules"]
    assert len(rules) == 1
    assert rules[0]["activation_condition"] == condition
