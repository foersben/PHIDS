"""Flora configuration routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

import phids.api.main as api_main
from phids.api.schemas import FloraSpeciesParams
from phids.api.services.draft_service import DraftService
from phids.api.ui_state import get_draft

router = APIRouter()
draft_service = DraftService()


@router.post("/api/config/flora", response_class=HTMLResponse, summary="Add flora species to draft")
async def config_flora_add(
    request: Request,
    name: Annotated[str, Form()] = "NewFlora",
    base_energy: Annotated[float, Form()] = 10.0,
    max_energy: Annotated[float, Form()] = 100.0,
    growth_rate: Annotated[float, Form()] = 5.0,
    survival_threshold: Annotated[float, Form()] = 1.0,
    reproduction_interval: Annotated[int, Form()] = 10,
    seed_min_dist: Annotated[float, Form()] = 1.0,
    seed_max_dist: Annotated[float, Form()] = 3.0,
    seed_energy_cost: Annotated[float, Form()] = 5.0,
    camouflage: Annotated[str, Form()] = "off",
    camouflage_factor: Annotated[float, Form()] = 1.0,
) -> Response:
    """Add one flora species to the draft and render the updated flora table."""
    draft = get_draft()
    if len(draft.flora_species) >= 16:
        api_main.logger.warning("Rule-of-16 rejected flora creation")
        raise HTTPException(status_code=400, detail="Rule of 16: maximum flora species reached.")
    new_id = len(draft.flora_species)
    params = FloraSpeciesParams(
        species_id=new_id,
        name=name,
        base_energy=base_energy,
        max_energy=max_energy,
        growth_rate=growth_rate,
        survival_threshold=survival_threshold,
        reproduction_interval=reproduction_interval,
        seed_min_dist=seed_min_dist,
        seed_max_dist=seed_max_dist,
        seed_energy_cost=seed_energy_cost,
        camouflage=camouflage == "on",
        camouflage_factor=max(0.0, min(1.0, camouflage_factor)),
        triggers=[],
    )
    draft_service.add_flora(draft, params)
    api_main.logger.info("Flora species added via API (species_id=%d, name=%s)", new_id, name)
    return api_main.templates.TemplateResponse(
        request,
        "partials/flora_config.html",
        {"flora_species": draft.flora_species},
    )


@router.put(
    "/api/config/flora/{species_id}",
    response_class=HTMLResponse,
    summary="Update flora species row",
)
async def config_flora_update(
    request: Request,
    species_id: int,
    view: str = "flora",
    name: Annotated[str | None, Form()] = None,
    base_energy: Annotated[float | None, Form()] = None,
    max_energy: Annotated[float | None, Form()] = None,
    growth_rate: Annotated[float | None, Form()] = None,
    survival_threshold: Annotated[float | None, Form()] = None,
    reproduction_interval: Annotated[int | None, Form()] = None,
    seed_min_dist: Annotated[float | None, Form()] = None,
    seed_max_dist: Annotated[float | None, Form()] = None,
    seed_energy_cost: Annotated[float | None, Form()] = None,
    camouflage: Annotated[str | None, Form()] = None,
    camouflage_factor: Annotated[float | None, Form()] = None,
    passive_defenses_mechanical_damage_per_bite: Annotated[
        float | None, Form(alias="passive_defenses.mechanical_damage_per_bite")
    ] = None,
    passive_defenses_digestibility_modifier: Annotated[
        float | None, Form(alias="passive_defenses.digestibility_modifier")
    ] = None,
) -> Response:
    """Patch one flora species in the draft and render the updated flora table."""
    draft = get_draft()
    idx = next(
        (
            i
            for i, fp in enumerate(draft.flora_species)
            if isinstance(fp, FloraSpeciesParams) and fp.species_id == species_id
        ),
        None,
    )
    if idx is None:
        api_main.logger.warning("Flora update requested for unknown species_id=%d", species_id)
        raise HTTPException(status_code=404, detail=f"Flora species {species_id} not found.")

    fp = draft.flora_species[idx]
    if not isinstance(fp, FloraSpeciesParams):
        raise HTTPException(status_code=400, detail="Invalid flora species entry in draft state.")
    updates: dict[str, object] = {}
    if name is not None:
        updates["name"] = name
    if base_energy is not None:
        updates["base_energy"] = base_energy
    if max_energy is not None:
        updates["max_energy"] = max_energy
    if growth_rate is not None:
        updates["growth_rate"] = growth_rate
    if survival_threshold is not None:
        updates["survival_threshold"] = survival_threshold
    if reproduction_interval is not None:
        updates["reproduction_interval"] = reproduction_interval
    if seed_min_dist is not None:
        updates["seed_min_dist"] = seed_min_dist
    if seed_max_dist is not None:
        updates["seed_max_dist"] = seed_max_dist
    if seed_energy_cost is not None:
        updates["seed_energy_cost"] = seed_energy_cost
    if camouflage is not None:
        updates["camouflage"] = camouflage == "on"
    if camouflage_factor is not None:
        updates["camouflage_factor"] = max(0.0, min(1.0, camouflage_factor))

    # Handle nested passive defenses
    passive_updates: dict[str, object] = {}
    if passive_defenses_mechanical_damage_per_bite is not None:
        passive_updates["mechanical_damage_per_bite"] = max(0.0, passive_defenses_mechanical_damage_per_bite)
    if passive_defenses_digestibility_modifier is not None:
        passive_updates["digestibility_modifier"] = max(0.0, min(1.0, passive_defenses_digestibility_modifier))
    if passive_updates:
        updates["passive_defenses"] = fp.passive_defenses.model_copy(update=passive_updates)

    draft.flora_species[idx] = fp.model_copy(update=updates)
    api_main.logger.debug("Flora species updated via API (species_id=%d, fields=%s)", species_id, sorted(updates))
    if view == "morphology":
        from phids.api.routers.config.trigger_rules import _render_trigger_rules_partial

        return _render_trigger_rules_partial(request, draft)

    return api_main.templates.TemplateResponse(
        request,
        "partials/flora_config.html",
        {"flora_species": draft.flora_species},
    )


@router.delete("/api/config/flora/{species_id}", response_class=HTMLResponse, summary="Delete flora species")
async def config_flora_delete(species_id: int) -> HTMLResponse:
    """Remove one flora species from the draft."""
    draft = get_draft()
    try:
        draft_service.remove_flora(draft, species_id)
    except ValueError as exc:
        api_main.logger.warning("Flora delete requested for unknown species_id=%d", species_id)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return HTMLResponse(content="")
