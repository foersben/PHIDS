# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Herbivores configuration routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

import phids.api.main as api_main
from phids.api.schemas.species import HerbivoreSpeciesParams
from phids.api.services.draft.species import add_herbivore, remove_herbivore
from phids.api.ui_state.state import get_draft

router = APIRouter()


@router.post("/api/config/herbivores", response_class=HTMLResponse, summary="Add herbivore species to draft")
async def config_herbivore_add(
    request: Request,
    name: Annotated[str, Form()] = "NewHerbivore",
    energy_min: Annotated[float, Form()] = 5.0,
    velocity: Annotated[int, Form()] = 2,
    consumption_rate: Annotated[float, Form()] = 10.0,
    reproduction_energy_divisor: Annotated[float, Form()] = 1.0,
    energy_upkeep_per_individual: Annotated[float, Form()] = 0.05,
    split_population_threshold: Annotated[int, Form()] = 10,
) -> Response:
    """Add one herbivore species to the draft and render the updated herbivore table."""
    draft = get_draft()
    if len(draft.herbivore_species) >= 16:
        api_main.logger.warning("Rule-of-16 rejected herbivore creation")
        raise HTTPException(status_code=400, detail="Rule of 16: maximum herbivore species reached.")
    new_id = len(draft.herbivore_species)
    params = HerbivoreSpeciesParams(
        species_id=new_id,
        name=name,
        energy_min=energy_min,
        velocity=velocity,
        consumption_rate=consumption_rate,
        reproduction_energy_divisor=max(1.0, reproduction_energy_divisor),
        energy_upkeep_per_individual=energy_upkeep_per_individual,
        split_population_threshold=split_population_threshold,
    )
    add_herbivore(draft, params)
    api_main.logger.info("Herbivore species added via API (species_id=%d, name=%s)", new_id, name)
    return api_main.templates.TemplateResponse(
        request,
        "partials/herbivore_config.html",
        {"herbivore_species": draft.herbivore_species},
    )


def _build_herbivore_updates(
    name: str | None,
    energy_min: float | None,
    velocity: int | None,
    consumption_rate: float | None,
    reproduction_energy_divisor: float | None,
    energy_upkeep_per_individual: float | None,
    split_population_threshold: int | None,
    resistances_morph: float | None,
    resistances_chem: float | None,
    resistances_dig: float | None,
    current_resistances: object,
) -> dict[str, object]:
    """Build field update dictionary from form inputs."""
    updates: dict[str, object] = {}
    field_map = {
        "name": name,
        "energy_min": energy_min,
        "velocity": velocity,
        "consumption_rate": consumption_rate,
        "energy_upkeep_per_individual": energy_upkeep_per_individual,
        "split_population_threshold": split_population_threshold,
    }
    for key, val in field_map.items():
        if val is not None:
            updates[key] = val
    if reproduction_energy_divisor is not None:
        updates["reproduction_energy_divisor"] = max(1.0, reproduction_energy_divisor)

    res_updates: dict[str, object] = {}
    if resistances_morph is not None:
        res_updates["morphological_adaptation"] = max(0.0, min(1.0, resistances_morph))
    if resistances_chem is not None:
        res_updates["chemical_neutralization"] = max(0.0, min(1.0, resistances_chem))
    if resistances_dig is not None:
        res_updates["digestive_efficiency"] = max(0.0, resistances_dig)
    if res_updates and hasattr(current_resistances, "model_copy"):
        updates["resistances"] = current_resistances.model_copy(update=res_updates)
    return updates


@router.put(
    "/api/config/herbivores/{species_id}",
    response_class=HTMLResponse,
    summary="Update herbivore species row",
)
async def config_herbivore_update(
    request: Request,
    species_id: int,
    name: Annotated[str | None, Form()] = None,
    energy_min: Annotated[float | None, Form()] = None,
    velocity: Annotated[int | None, Form()] = None,
    consumption_rate: Annotated[float | None, Form()] = None,
    reproduction_energy_divisor: Annotated[float | None, Form()] = None,
    energy_upkeep_per_individual: Annotated[float | None, Form()] = None,
    split_population_threshold: Annotated[int | None, Form()] = None,
    resistances_morphological_adaptation: Annotated[
        float | None, Form(alias="resistances.morphological_adaptation")
    ] = None,
    resistances_chemical_neutralization: Annotated[
        float | None, Form(alias="resistances.chemical_neutralization")
    ] = None,
    resistances_digestive_efficiency: Annotated[float | None, Form(alias="resistances.digestive_efficiency")] = None,
) -> Response:
    """Patch one herbivore species in the draft and render the updated herbivore table."""
    draft = get_draft()
    idx = next(
        (
            i
            for i, pp in enumerate(draft.herbivore_species)
            if isinstance(pp, HerbivoreSpeciesParams) and pp.species_id == species_id
        ),
        None,
    )
    if idx is None:
        api_main.logger.warning("Herbivore update requested for unknown species_id=%d", species_id)
        raise HTTPException(status_code=404, detail=f"Herbivore species {species_id} not found.")

    pp = draft.herbivore_species[idx]
    if not isinstance(pp, HerbivoreSpeciesParams):
        raise HTTPException(status_code=400, detail="Invalid herbivore species entry in draft state.")

    updates = _build_herbivore_updates(
        name,
        energy_min,
        velocity,
        consumption_rate,
        reproduction_energy_divisor,
        energy_upkeep_per_individual,
        split_population_threshold,
        resistances_morphological_adaptation,
        resistances_chemical_neutralization,
        resistances_digestive_efficiency,
        pp.resistances,
    )

    draft.herbivore_species[idx] = pp.model_copy(update=updates)
    api_main.logger.debug("Herbivore species updated via API (species_id=%d, fields=%s)", species_id, sorted(updates))
    return api_main.templates.TemplateResponse(
        request,
        "partials/herbivore_config.html",
        {"herbivore_species": draft.herbivore_species},
    )


@router.delete(
    "/api/config/herbivores/{species_id}",
    response_class=HTMLResponse,
    summary="Delete herbivore species",
)
async def config_herbivore_delete(species_id: int) -> HTMLResponse:
    """Remove one herbivore species from the draft."""
    draft = get_draft()
    try:
        remove_herbivore(draft, species_id)
    except ValueError as exc:
        api_main.logger.warning("Herbivore delete requested for unknown species_id=%d", species_id)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return HTMLResponse(content="")
