# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Integration tests for PHIDS API route handlers, HTMX requests, and species/substance builder routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from starlette.requests import Request

if TYPE_CHECKING:
    from httpx import AsyncClient

from phids.api import main as api_main
from phids.api.presenters.dashboard import build_draft_mycorrhizal_links
from phids.api.schemas.placement import InitialPlantPlacement, InitialSwarmPlacement
from phids.api.schemas.simulation import SimulationConfig
from phids.api.schemas.species import DietCompatibilityMatrix, FloraSpeciesParams, HerbivoreSpeciesParams
from phids.api.schemas.triggers import HerbivoreAttackInitiator, SynthesizeSubstanceAction, TriggerConditionSchema
from phids.api.services.draft.placements import add_plant_placement
from phids.api.ui_state.state import DraftState, get_draft
from phids.api.ui_state.substances import SubstanceDefinition


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


@pytest.mark.parametrize(
    ("headers", "expected"),
    [([(b"hx-request", b"true")], True), ([], False)],
)
def test_is_htmx_request_cases(headers: list[tuple[bytes, bytes]], expected: bool) -> None:
    """Verify HTMX request detection for header-present and header-absent request scopes."""
    request = Request({"type": "http", "headers": headers})
    assert api_main._is_htmx_request(request) is expected


def test_build_draft_mycorrhizal_links_respects_interspecies_flag() -> None:
    """Verify draft link presenter marks inter-species links only when the feature flag is enabled."""
    draft = DraftState.default()
    draft.initial_plants = []
    add_plant_placement(draft, 0, 1, 1, 10.0)
    add_plant_placement(draft, 1, 2, 1, 10.0)
    assert build_draft_mycorrhizal_links(draft) == []
    draft.mycorrhizal_inter_species = True
    assert build_draft_mycorrhizal_links(draft)[0]["inter_species"] is True


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
    assert add_resp.status_code == 200, add_resp.text

    draft = get_draft()
    added_flora = draft.flora_species[-1]
    assert isinstance(added_flora, FloraSpeciesParams)
    assert added_flora.camouflage is True
    assert added_flora.camouflage_factor == pytest.approx(1.0)

    added_id = added_flora.species_id
    update_resp = await api_client.put(
        f"/api/config/flora/{added_id}",
        data={
            "name": "Oak Updated",
            "camouflage": "off",
            "camouflage_factor": -1.0,
            "passive_defenses.mechanical_damage_per_bite": -5.0,
            "passive_defenses.digestibility_modifier": 2.0,
        },
    )
    assert update_resp.status_code == 200, update_resp.text

    updated_flora = draft.flora_species[-1]
    assert isinstance(updated_flora, FloraSpeciesParams)
    assert updated_flora.name == "Oak Updated"
    assert updated_flora.camouflage is False
    assert updated_flora.camouflage_factor == pytest.approx(0.0)
    assert updated_flora.passive_defenses.mechanical_damage_per_bite == pytest.approx(0.0)
    assert updated_flora.passive_defenses.digestibility_modifier == pytest.approx(1.0)

    delete_resp = await api_client.delete(f"/api/config/flora/{added_id}")
    delete_missing_resp = await api_client.delete("/api/config/flora/99")

    assert delete_resp.status_code == 200, delete_resp.text
    assert delete_missing_resp.status_code == 404, delete_missing_resp.text


@pytest.mark.asyncio
async def test_builder_herbivore_routes_add_update_delete(api_client: AsyncClient) -> None:
    """Verify herbivore routes support add/update/delete and return 404 for missing species IDs."""
    add_resp = await api_client.post(
        "/api/config/herbivores",
        data={
            "name": "Locust",
            "energy_min": 2.0,
            "velocity": 2,
            "consumption_rate": 3.5,
            "energy_upkeep_per_individual": 0.1,
            "split_population_threshold": 15,
        },
    )
    assert add_resp.status_code == 200, add_resp.text

    draft = get_draft()
    added_herbivore = draft.herbivore_species[-1]
    assert isinstance(added_herbivore, HerbivoreSpeciesParams)
    assert added_herbivore.energy_upkeep_per_individual == pytest.approx(0.1)
    assert added_herbivore.split_population_threshold == 15

    added_id = added_herbivore.species_id
    update_resp = await api_client.put(
        f"/api/config/herbivores/{added_id}",
        data={
            "name": "Locust Updated",
            "velocity": 3,
            "resistances.morphological_adaptation": 1.5,
            "resistances.chemical_neutralization": -0.5,
            "resistances.digestive_efficiency": 2.5,
        },
    )
    assert update_resp.status_code == 200, update_resp.text

    updated_herbivore = draft.herbivore_species[-1]
    assert isinstance(updated_herbivore, HerbivoreSpeciesParams)
    assert updated_herbivore.name == "Locust Updated"
    assert updated_herbivore.resistances.morphological_adaptation == pytest.approx(1.0)
    assert updated_herbivore.resistances.chemical_neutralization == pytest.approx(0.0)
    assert updated_herbivore.resistances.digestive_efficiency == pytest.approx(2.5)

    delete_resp = await api_client.delete(f"/api/config/herbivores/{added_id}")
    delete_missing_resp = await api_client.delete("/api/config/herbivores/99")

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
    """Test builder route rule with 16 branches."""
    draft = get_draft()
    draft.flora_species = [_flora(i) for i in range(16)]
    draft.herbivore_species = [_herbivore(i) for i in range(16)]
    draft.substance_definitions = [SubstanceDefinition(substance_id=i, name=f"s{i}") for i in range(16)]

    responses = {
        "/api/config/flora": await api_client.post("/api/config/flora", data={"name": "Overflow"}),
        "/api/config/herbivores": await api_client.post("/api/config/herbivores", data={"name": "Overflow"}),
        "/api/config/substances": await api_client.post("/api/config/substances", data={"name": "Overflow"}),
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
    herbivore = next(p for p in draft.herbivore_species if isinstance(p, HerbivoreSpeciesParams) and p.species_id == 1)
    assert herbivore.reproduction_energy_divisor == pytest.approx(1.0)
