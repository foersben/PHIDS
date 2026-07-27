# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Placements configuration routes."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

if TYPE_CHECKING:
    from starlette.datastructures import FormData

import phids.api.main as api_main
from phids.api.presenters.dashboard import build_draft_mycorrhizal_links
from phids.api.services.draft.placements import (
    add_plant_placement,
    add_swarm_placement,
    remove_plant_placement,
    remove_swarm_placement,
)
from phids.api.ui_state.state import (
    DraftState,
    get_draft,
)
from phids.engine.core.placement import generate_banded, generate_clustered, generate_uniform

router = APIRouter()


def _render_placement_list_partial(request: Request, draft: DraftState) -> Response:
    """Render the canonical placement-ledger partial response."""
    return api_main.templates.TemplateResponse(
        request,
        "partials/placement_list.html",
        {
            "flora_species": draft.flora_species,
            "herbivore_species": draft.herbivore_species,
            "initial_plants": draft.initial_plants,
            "initial_swarms": draft.initial_swarms,
        },
    )


@router.get("/api/config/placements/data", summary="Get placement data as JSON")
async def placement_data() -> JSONResponse:
    """Return draft placement data and inferred root links for canvas rendering."""
    draft = get_draft()
    plants = [
        {"idx": i, "species_id": p.species_id, "x": p.x, "y": p.y, "energy": p.energy}
        for i, p in enumerate(draft.initial_plants)
    ]
    swarms = [
        {
            "idx": i,
            "species_id": s.species_id,
            "x": s.x,
            "y": s.y,
            "population": s.population,
            "energy": s.energy,
        }
        for i, s in enumerate(draft.initial_swarms)
    ]
    flora = [
        {"species_id": getattr(fp, "species_id", i), "name": getattr(fp, "name", f"Flora {i}")}
        for i, fp in enumerate(draft.flora_species)
    ]
    herbivores = [
        {
            "species_id": getattr(hp, "species_id", i),
            "name": getattr(hp, "name", f"Herb {i}"),
        }
        for i, hp in enumerate(draft.herbivore_species)
    ]
    mycorrhizal_links = build_draft_mycorrhizal_links(draft)
    return JSONResponse(
        content={
            "plants": plants,
            "swarms": swarms,
            "grid_width": draft.grid_width,
            "grid_height": draft.grid_height,
            "flora_species": flora,
            "herbivore_species": herbivores,
            "mycorrhizal_links": mycorrhizal_links,
        }
    )


@router.post("/api/config/placements/plant", response_class=HTMLResponse, summary="Place a plant on the grid")
async def config_placement_plant_add(
    request: Request,
    species_id: Annotated[int, Form()],
    x: Annotated[int, Form()],
    y: Annotated[int, Form()],
    energy: Annotated[float, Form()] = 10.0,
) -> Response:
    """Create one plant placement and render the updated placement ledger."""
    draft = get_draft()
    x = max(0, min(draft.grid_width - 1, x))
    y = max(0, min(draft.grid_height - 1, y))
    add_plant_placement(draft, species_id, x, y, max(0.1, energy))
    api_main.logger.info("Plant placement added via API (species_id=%d, x=%d, y=%d)", species_id, x, y)
    return _render_placement_list_partial(request, draft)


@router.post("/api/config/placements/swarm", response_class=HTMLResponse, summary="Place a swarm on the grid")
async def config_placement_swarm_add(
    request: Request,
    species_id: Annotated[int, Form()],
    x: Annotated[int, Form()],
    y: Annotated[int, Form()],
    population: Annotated[int, Form()] = 10,
    energy: Annotated[float, Form()] = 50.0,
) -> Response:
    """Create one swarm placement and render the updated placement ledger."""
    draft = get_draft()
    x = max(0, min(draft.grid_width - 1, x))
    y = max(0, min(draft.grid_height - 1, y))
    add_swarm_placement(
        draft,
        species_id,
        x,
        y,
        max(1, population),
        max(0.1, energy),
    )
    api_main.logger.info(
        "Swarm placement added via API (species_id=%d, x=%d, y=%d, population=%d)",
        species_id,
        x,
        y,
        max(1, population),
    )
    return _render_placement_list_partial(request, draft)


@router.delete(
    "/api/config/placements/plant/{index}",
    response_class=HTMLResponse,
    summary="Remove a placed plant",
)
async def config_placement_plant_delete(request: Request, index: int) -> Response:
    """Remove one plant placement and render the updated placement ledger."""
    draft = get_draft()
    try:
        remove_plant_placement(draft, index)
    except IndexError as exc:
        api_main.logger.warning("Plant placement delete requested for unknown index=%d", index)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _render_placement_list_partial(request, draft)


@router.delete(
    "/api/config/placements/swarm/{index}",
    response_class=HTMLResponse,
    summary="Remove a placed swarm",
)
async def config_placement_swarm_delete(request: Request, index: int) -> Response:
    """Remove one swarm placement and render the updated placement ledger."""
    draft = get_draft()
    try:
        remove_swarm_placement(draft, index)
    except IndexError as exc:
        api_main.logger.warning("Swarm placement delete requested for unknown index=%d", index)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _render_placement_list_partial(request, draft)


@router.post("/api/config/placements/clear", response_class=HTMLResponse, summary="Clear all placements")
async def config_placements_clear(request: Request) -> Response:
    """Clear all plant and swarm placements and render the updated placement ledger."""
    draft = get_draft()
    from phids.api.services.draft.placements import clear_placements as _clear_placements

    _clear_placements(draft)
    api_main.logger.info("All draft placements cleared via API")
    return _render_placement_list_partial(request, draft)


@router.post("/api/config/placements/clear-plants", response_class=HTMLResponse, summary="Clear all plant placements")
async def config_placements_clear_plants(request: Request) -> Response:
    """Clear all plant placements and render the updated placement ledger."""
    draft = get_draft()
    from phids.api.services.draft.placements import clear_plant_placements

    clear_plant_placements(draft)
    api_main.logger.info("All draft plant placements cleared via API")
    return _render_placement_list_partial(request, draft)


@router.post("/api/config/placements/clear-swarms", response_class=HTMLResponse, summary="Clear all swarm placements")
async def config_placements_clear_swarms(request: Request) -> Response:
    """Clear all swarm placements and render the updated placement ledger."""
    draft = get_draft()
    from phids.api.services.draft.placements import clear_swarm_placements

    clear_swarm_placements(draft)
    api_main.logger.info("All draft swarm placements cleared via API")
    return _render_placement_list_partial(request, draft)


def _generate_autoassign_coords(distribution: str, width: int, height: int, form: FormData) -> list[tuple[int, int]]:
    """Generate coordinate list based on procedural distribution type."""
    if distribution == "uniform":
        density = float(str(form.get("density", 0.05)))
        return generate_uniform(width, height, density)
    if distribution == "clustered":
        cluster_count = int(str(form.get("cluster_count", 5)))
        variance = float(str(form.get("variance", 2.0)))
        return generate_clustered(width, height, cluster_count, variance)
    if distribution == "banded":
        band_count = int(str(form.get("band_count", 3)))
        orientation = str(form.get("orientation", "horizontal"))
        return generate_banded(width, height, band_count, orientation)
    return []


def _extract_species_weights(form: FormData) -> tuple[list[int], list[float]]:
    """Extract species IDs and corresponding positive weights from form data."""
    weights: list[float] = []
    species_ids: list[int] = []
    for key, val in form.items():
        if key.startswith("weight_") and val:
            try:
                sid = int(key.split("_")[1])
                weight = float(str(val))
                if weight > 0:
                    species_ids.append(sid)
                    weights.append(weight)
            except ValueError:
                pass
    return species_ids, weights


@router.post("/api/config/placements/autoassign", response_class=HTMLResponse, summary="Autoassign placements")
async def config_placement_autoassign(request: Request) -> Response:
    """Generate manual placements using procedural logic."""
    draft = get_draft()
    form = await request.form()

    target_type = str(form.get("target_type", "plant"))
    distribution = str(form.get("distribution", "uniform"))
    coords = _generate_autoassign_coords(distribution, draft.grid_width, draft.grid_height, form)
    species_ids, weights = _extract_species_weights(form)

    if not coords or not species_ids:
        api_main.logger.warning("Autoassign skipped (no coords generated or no species weights > 0)")
        return _render_placement_list_partial(request, draft)

    # Assign coordinates based on weighted random selection
    assignments = random.choices(species_ids, weights=weights, k=len(coords))

    for (x, y), sid in zip(coords, assignments, strict=False):
        if target_type == "plant":
            add_plant_placement(draft, sid, x, y, energy=10.0)
        else:
            add_swarm_placement(draft, sid, x, y, population=10, energy=50.0)

    api_main.logger.info("Autoassigned %d %s(s) via %s distribution", len(coords), target_type, distribution)

    return _render_placement_list_partial(request, draft)
