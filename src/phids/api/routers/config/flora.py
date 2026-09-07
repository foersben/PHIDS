# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Flora configuration routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

import phids.api.main as api_main
from phids.api.schemas.species import FloraSpeciesParams
from phids.api.services.draft.species import add_flora, remove_flora
from phids.api.ui_state.state import DraftState, get_draft

router = APIRouter()


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
    seed_drop_height: Annotated[float, Form()] = 0.5,
    seed_terminal_velocity: Annotated[float, Form()] = 1.0,
    camouflage: Annotated[str, Form()] = "off",
    camouflage_factor: Annotated[float, Form()] = 1.0,
    translocation_rate: Annotated[float, Form()] = 0.2,
    mycorrhizal_tax_per_link: Annotated[float, Form()] = 0.0,
    structural_mass_max: Annotated[float, Form()] = 0.0,
    structural_growth_rate: Annotated[float, Form()] = 0.01,
) -> Response:
    """Add one flora species to the draft and render the updated flora table.

    Args:
        request: The HTTP request.
        name: The name of the flora species.
        base_energy: The base energy of the flora species.
        max_energy: The maximum energy of the flora species.
        growth_rate: The growth rate of the flora species.
        survival_threshold: The survival threshold of the flora species.
        reproduction_interval: The reproduction interval of the flora species.
        seed_min_dist: The minimum distance between seeds of the flora species.
        seed_max_dist: The maximum distance between seeds of the flora species.
        seed_energy_cost: The energy cost of seeding for the flora species.
        seed_drop_height: Canopy release height for wind advection.
        seed_terminal_velocity: Downward terminal fall velocity.
        camouflage: Whether the flora species has camouflage.
        camouflage_factor: The camouflage factor of the flora species.
        translocation_rate: Phloem nutrient translocation rate during withdrawal.
        mycorrhizal_tax_per_link: Energy upkeep tax per active root link per tick.
        structural_mass_max: Maximum structural dry mass ceiling (woodiness).
        structural_growth_rate: Fractional structural growth per slow loop.

    Returns:
        The updated flora table.
    """
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
        seed_min_dist=max(0.0, seed_min_dist),
        seed_max_dist=max(seed_min_dist, seed_max_dist),
        seed_energy_cost=max(0.0, seed_energy_cost),
        seed_drop_height=max(0.01, seed_drop_height),
        seed_terminal_velocity=max(0.01, seed_terminal_velocity),
        camouflage=camouflage == "on",
        camouflage_factor=max(0.0, min(1.0, camouflage_factor)),
        translocation_rate=max(0.0, min(1.0, translocation_rate)),
        mycorrhizal_tax_per_link=max(0.0, mycorrhizal_tax_per_link),
        structural_mass_max=max(0.0, structural_mass_max),
        structural_growth_rate=max(0.0, min(1.0, structural_growth_rate)),
        triggers=[],
    )
    add_flora(draft, params)
    api_main.logger.info("Flora species added via API (species_id=%d, name=%s)", new_id, name)
    return api_main.templates.TemplateResponse(
        request,
        "partials/flora_config.html",
        {"flora_species": draft.flora_species},
    )


def _find_flora_species(draft: DraftState, species_id: int) -> tuple[int, FloraSpeciesParams]:
    """Locate flora species by ID in draft state or raise HTTPException."""
    for i, fp in enumerate(draft.flora_species):
        if isinstance(fp, FloraSpeciesParams) and fp.species_id == species_id:
            return i, fp
    api_main.logger.warning("Flora update requested for unknown species_id=%d", species_id)
    raise HTTPException(status_code=404, detail=f"Flora species {species_id} not found.")


def _build_scalar_flora_updates(
    name: str | None,
    base_energy: float | None,
    max_energy: float | None,
    growth_rate: float | None,
    survival_threshold: float | None,
    reproduction_interval: int | None,
    seed_energy_cost: float | None,
) -> dict[str, object]:
    """Collect non-None primary energy and lifecycle scalars."""
    raw = {
        "name": name,
        "base_energy": base_energy,
        "max_energy": max_energy,
        "growth_rate": growth_rate,
        "survival_threshold": survival_threshold,
        "reproduction_interval": reproduction_interval,
        "seed_energy_cost": max(0.0, seed_energy_cost) if seed_energy_cost is not None else None,
    }
    return {k: v for k, v in raw.items() if v is not None}


def _build_spatial_and_morphological_updates(
    fp: FloraSpeciesParams,
    *,
    seed_min_dist: float | None,
    seed_max_dist: float | None,
    seed_drop_height: float | None,
    seed_terminal_velocity: float | None,
    structural_mass_max: float | None,
    structural_growth_rate: float | None,
    translocation_rate: float | None,
    mycorrhizal_tax_per_link: float | None,
    camouflage: str | None,
    camouflage_factor: float | None,
) -> dict[str, object]:
    """Collect spatial seed dispersal, woody structural, and phloem updates."""
    updates: dict[str, object] = {}
    if seed_min_dist is not None:
        updates["seed_min_dist"] = max(0.0, seed_min_dist)
    if seed_max_dist is not None:
        min_d = float(updates.get("seed_min_dist", fp.seed_min_dist))  # type: ignore[arg-type]
        updates["seed_max_dist"] = max(min_d, seed_max_dist)
    if seed_drop_height is not None:
        updates["seed_drop_height"] = max(0.01, seed_drop_height)
    if seed_terminal_velocity is not None:
        updates["seed_terminal_velocity"] = max(0.01, seed_terminal_velocity)
    if structural_mass_max is not None:
        updates["structural_mass_max"] = max(0.0, structural_mass_max)
    if structural_growth_rate is not None:
        updates["structural_growth_rate"] = max(0.0, min(1.0, structural_growth_rate))
    if translocation_rate is not None:
        updates["translocation_rate"] = max(0.0, min(1.0, translocation_rate))
    if mycorrhizal_tax_per_link is not None:
        updates["mycorrhizal_tax_per_link"] = max(0.0, mycorrhizal_tax_per_link)
    if camouflage is not None:
        updates["camouflage"] = camouflage == "on"
    if camouflage_factor is not None:
        updates["camouflage_factor"] = max(0.0, min(1.0, camouflage_factor))
    return updates


def _build_passive_defense_updates(
    fp: FloraSpeciesParams,
    mech_dmg: float | None,
    digest_mod: float | None,
) -> dict[str, object]:
    """Build passive defense nested model update if fields provided."""
    passive_updates: dict[str, object] = {}
    if mech_dmg is not None:
        passive_updates["mechanical_damage_per_bite"] = max(0.0, mech_dmg)
    if digest_mod is not None:
        passive_updates["digestibility_modifier"] = max(0.0, min(1.0, digest_mod))
    if passive_updates:
        return {"passive_defenses": fp.passive_defenses.model_copy(update=passive_updates)}
    return {}


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
    seed_drop_height: Annotated[float | None, Form()] = None,
    seed_terminal_velocity: Annotated[float | None, Form()] = None,
    camouflage: Annotated[str | None, Form()] = None,
    camouflage_factor: Annotated[float | None, Form()] = None,
    translocation_rate: Annotated[float | None, Form()] = None,
    mycorrhizal_tax_per_link: Annotated[float | None, Form()] = None,
    structural_mass_max: Annotated[float | None, Form()] = None,
    structural_growth_rate: Annotated[float | None, Form()] = None,
    passive_defenses_mechanical_damage_per_bite: Annotated[
        float | None, Form(alias="passive_defenses.mechanical_damage_per_bite")
    ] = None,
    passive_defenses_digestibility_modifier: Annotated[
        float | None, Form(alias="passive_defenses.digestibility_modifier")
    ] = None,
) -> Response:
    """Patch one flora species in the draft and render the updated flora table.

    Args:
        request: The HTTP request.
        species_id: The species ID.
        view: The view to render.
        name: The name of the flora species.
        base_energy: The base energy of the flora species.
        max_energy: The maximum energy of the flora species.
        growth_rate: The growth rate of the flora species.
        survival_threshold: The survival threshold of the flora species.
        reproduction_interval: The reproduction interval of the flora species.
        seed_min_dist: The minimum distance between seeds of the flora species.
        seed_max_dist: The maximum distance between seeds of the flora species.
        seed_energy_cost: The energy cost of seeding for the flora species.
        seed_drop_height: Canopy release height for wind advection.
        seed_terminal_velocity: Downward terminal fall velocity.
        camouflage: Whether the flora species has camouflage.
        camouflage_factor: The camouflage factor of the flora species.
        translocation_rate: Phloem nutrient translocation rate during withdrawal.
        mycorrhizal_tax_per_link: Energy upkeep tax per active root link per tick.
        structural_mass_max: Maximum structural dry mass ceiling (woodiness).
        structural_growth_rate: Fractional structural growth per slow loop.
        passive_defenses_mechanical_damage_per_bite: The mechanical damage per bite of the flora species.
        passive_defenses_digestibility_modifier: The digestibility modifier of the flora species.

    Returns:
        The updated flora table.
    """
    draft = get_draft()
    idx, fp = _find_flora_species(draft, species_id)

    updates = _build_scalar_flora_updates(
        name,
        base_energy,
        max_energy,
        growth_rate,
        survival_threshold,
        reproduction_interval,
        seed_energy_cost,
    )
    updates.update(
        _build_spatial_and_morphological_updates(
            fp,
            seed_min_dist=seed_min_dist,
            seed_max_dist=seed_max_dist,
            seed_drop_height=seed_drop_height,
            seed_terminal_velocity=seed_terminal_velocity,
            structural_mass_max=structural_mass_max,
            structural_growth_rate=structural_growth_rate,
            translocation_rate=translocation_rate,
            mycorrhizal_tax_per_link=mycorrhizal_tax_per_link,
            camouflage=camouflage,
            camouflage_factor=camouflage_factor,
        )
    )
    updates.update(
        _build_passive_defense_updates(
            fp,
            passive_defenses_mechanical_damage_per_bite,
            passive_defenses_digestibility_modifier,
        )
    )

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
    """Remove one flora species from the draft.

    Args:
        species_id: The species ID.

    Returns:
        The updated flora table.
    """
    draft = get_draft()
    try:
        remove_flora(draft, species_id)
    except ValueError as exc:
        api_main.logger.warning("Flora delete requested for unknown species_id=%d", species_id)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return HTMLResponse(content="")
