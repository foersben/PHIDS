# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for live and preview cell-details tooltip presenters."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from phids.api.presenters.dashboard import (
    build_draft_mycorrhizal_links,
    build_live_cell_details,
    build_preview_cell_details,
)
from phids.api.schemas.placement import InitialPlantPlacement, InitialSwarmPlacement
from phids.api.schemas.simulation import SimulationConfig
from phids.api.schemas.species import (
    DietCompatibilityMatrix,
    FloraSpeciesParams,
    HerbivoreResistancesSchema,
    HerbivoreSpeciesParams,
)
from phids.api.schemas.triggers import HerbivoreAttackInitiator, PassiveDefensesSchema, TriggerConditionSchema
from phids.api.services.draft.placements import add_plant_placement, add_swarm_placement
from phids.api.services.draft.trigger_rules import add_trigger_rule
from phids.api.ui_state.state import DraftState, reset_draft
from phids.api.ui_state.substances import SubstanceDefinition
from phids.engine.loop import SimulationLoop


def _flora(species_id: int, *, triggers: list[TriggerConditionSchema] | None = None) -> FloraSpeciesParams:
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
        passive_defenses=PassiveDefensesSchema(mechanical_damage_per_bite=0.0, digestibility_modifier=1.0),
    )


def _herbivore(species_id: int) -> HerbivoreSpeciesParams:
    return HerbivoreSpeciesParams(
        species_id=species_id,
        name=f"herbivore-{species_id}",
        energy_min=1.0,
        velocity=1,
        consumption_rate=1.0,
        reproduction_energy_divisor=1.0,
        resistances=HerbivoreResistancesSchema(),
    )


def _minimal_config(
    *,
    x: int = 2,
    y: int = 2,
    num_signals: int = 1,
    num_toxins: int = 1,
    triggers: list[TriggerConditionSchema] | None = None,
) -> SimulationConfig:
    return SimulationConfig(
        grid_width=8,
        grid_height=8,
        max_ticks=20,
        tick_rate_hz=20.0,
        num_signals=num_signals,
        num_toxins=num_toxins,
        flora_species=[_flora(0, triggers=triggers)],
        herbivore_species=[_herbivore(0)],
        diet_matrix=DietCompatibilityMatrix(rows=[[True]]),
        initial_plants=[InitialPlantPlacement(species_id=0, x=x, y=y, energy=10.0)],
        initial_swarms=[InitialSwarmPlacement(species_id=0, x=x, y=y, population=4, energy=5.0)],
        mycorrhizal_growth_interval_ticks=6,
    )


@pytest.fixture(autouse=True)
def _reset_draft() -> None:
    reset_draft()


def test_build_draft_mycorrhizal_links_empty_when_not_adjacent() -> None:
    """Verifies non-adjacent draft plants produce no root link candidates."""
    draft = DraftState.default()
    add_plant_placement(draft, 0, 0, 0, 10.0)
    add_plant_placement(draft, 0, 3, 3, 10.0)
    assert build_draft_mycorrhizal_links(draft) == []


def test_build_draft_mycorrhizal_links_adjacent_same_species() -> None:
    """Verifies two adjacent same-species plants produce one intra-species root link."""
    draft = DraftState.default()
    add_plant_placement(draft, 0, 2, 2, 10.0)
    add_plant_placement(draft, 0, 2, 3, 10.0)
    links = build_draft_mycorrhizal_links(draft)
    assert len(links) == 1
    assert links[0]["inter_species"] is False


def test_build_draft_mycorrhizal_links_inter_species_gated_by_flag() -> None:
    """Verifies inter-species links are generated only when flag is enabled."""
    draft = DraftState.default()
    add_plant_placement(draft, 0, 2, 2, 10.0)
    add_plant_placement(draft, 1, 2, 3, 10.0)

    draft.mycorrhizal_inter_species = False
    assert build_draft_mycorrhizal_links(draft) == []

    draft.mycorrhizal_inter_species = True
    links = build_draft_mycorrhizal_links(draft)
    assert len(links) == 1
    assert links[0]["inter_species"] is True


def test_build_live_cell_details_structural_contract() -> None:
    """Verifies live cell-details payload contains expected top-level keys."""
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


def test_build_live_cell_details_reports_plant_and_swarm_at_cell() -> None:
    """Verifies plant and swarm entities registered at (x, y) are included in payload."""
    config = _minimal_config(x=3, y=4)
    loop = SimulationLoop(config)
    payload = build_live_cell_details(loop, 3, 4, substance_names={})

    assert len(payload["plants"]) == 1
    assert len(payload["swarms"]) == 1


def test_build_live_cell_details_rejects_out_of_bounds() -> None:
    """Verifies out-of-bounds cell coordinate raises HTTP 404 in live presenter."""
    config = _minimal_config()
    loop = SimulationLoop(config)
    with pytest.raises(HTTPException) as exc_info:
        build_live_cell_details(loop, 99, 0, substance_names={})
    assert exc_info.value.status_code == 404


def test_build_live_cell_details_substance_name_injection() -> None:
    """Verifies explicitly injected substance names appear in substance payload."""
    from phids.api.schemas.triggers import SynthesizeSubstanceAction

    trigger = TriggerConditionSchema(
        initiator=HerbivoreAttackInitiator(herbivore_species_id=0, min_herbivore_population=1),
        aftereffect_ticks=2,
        action=SynthesizeSubstanceAction(
            substance_id=0,
            synthesis_duration=1,
            is_toxin=False,
            energy_cost_per_tick=0.1,
        ),
    )
    config = _minimal_config(triggers=[trigger])
    loop = SimulationLoop(config)
    asyncio.run(loop.step())

    payload = build_live_cell_details(loop, 2, 2, substance_names={0: "AlarmPheromone"})
    found_names = [s["name"] for plant in payload["plants"] for s in plant["active_substances"]] + [
        s["name"] for s in payload["signal_concentrations"]
    ]
    if found_names:
        assert any("AlarmPheromone" in n for n in found_names)


def test_build_preview_cell_details_structural_contract() -> None:
    """Verifies draft cell-details payload mirrors live payload key contract."""
    draft = DraftState.default()
    add_plant_placement(draft, 0, 1, 1, 10.0)
    add_swarm_placement(draft, 0, 1, 1, 3, 8.0)
    payload = build_preview_cell_details(1, 1, draft=draft, substance_names={})

    assert payload["mode"] == "draft"
    assert payload["tick"] is None
    assert payload["x"] == 1
    assert payload["y"] == 1


def test_build_preview_cell_details_reports_placed_entities() -> None:
    """Verifies draft-placed plants and swarms are correctly serialized."""
    draft = DraftState.default()
    add_plant_placement(draft, 0, 2, 2, 12.0)
    add_plant_placement(draft, 0, 5, 5, 10.0)
    add_swarm_placement(draft, 0, 2, 2, 5, 15.0)
    payload = build_preview_cell_details(2, 2, draft=draft)

    assert len(payload["plants"]) == 1
    assert payload["plants"][0]["energy"] == pytest.approx(12.0)
    assert len(payload["swarms"]) == 1


def test_build_preview_cell_details_rejects_out_of_bounds() -> None:
    """Verifies out-of-bounds draft cell coordinates raise HTTP 404."""
    draft = DraftState.default()
    with pytest.raises(HTTPException) as exc_info:
        build_preview_cell_details(draft.grid_width, 0, draft=draft)
    assert exc_info.value.status_code == 404


def test_build_preview_cell_details_includes_trigger_rules() -> None:
    """Verifies configured trigger rules are serialized for associated plant species."""
    draft = DraftState.default()
    add_plant_placement(draft, 0, 3, 3, 10.0)
    draft.substance_definitions.append(
        SubstanceDefinition(substance_id=0, name="VOC", is_toxin=False, synthesis_duration=1, aftereffect_ticks=0)
    )
    add_trigger_rule(
        draft,
        flora_species_id=0,
        herbivore_species_id=0,
        substance_id=0,
        min_herbivore_population=2,
    )

    payload = build_preview_cell_details(3, 3, draft=draft)
    plant = payload["plants"][0]
    assert len(plant["configured_trigger_rules"]) == 1
    assert plant["configured_trigger_rules"][0]["substance_id"] == 0
