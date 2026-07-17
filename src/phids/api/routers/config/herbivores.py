# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Herbivores configuration routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

import phids.api.main as api_main
from phids.api.schemas import HerbivoreSpeciesParams
from phids.api.services.draft.species import add_herbivore, remove_herbivore
from phids.api.ui_state import get_draft

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
    updates: dict[str, object] = {}
    if name is not None:
        updates["name"] = name
    if energy_min is not None:
        updates["energy_min"] = energy_min
    if velocity is not None:
        updates["velocity"] = velocity
    if consumption_rate is not None:
        updates["consumption_rate"] = consumption_rate
    if reproduction_energy_divisor is not None:
        updates["reproduction_energy_divisor"] = max(1.0, reproduction_energy_divisor)
    if energy_upkeep_per_individual is not None:
        updates["energy_upkeep_per_individual"] = energy_upkeep_per_individual
    if split_population_threshold is not None:
        updates["split_population_threshold"] = split_population_threshold

    # Handle nested resistances
    resistances_updates: dict[str, object] = {}
    if resistances_morphological_adaptation is not None:
        resistances_updates["morphological_adaptation"] = max(0.0, min(1.0, resistances_morphological_adaptation))
    if resistances_chemical_neutralization is not None:
        resistances_updates["chemical_neutralization"] = max(0.0, min(1.0, resistances_chemical_neutralization))
    if resistances_digestive_efficiency is not None:
        resistances_updates["digestive_efficiency"] = max(0.0, resistances_digestive_efficiency)
    if resistances_updates:
        updates["resistances"] = pp.resistances.model_copy(update=resistances_updates)

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
