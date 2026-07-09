"""Placements configuration routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

import phids.api.main as api_main
from phids.api.presenters.dashboard import build_draft_mycorrhizal_links
from phids.api.services.draft_service import DraftService
from phids.api.ui_state import DraftState, get_draft

router = APIRouter()
draft_service = DraftService()


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
    draft_service.add_plant_placement(draft, species_id, x, y, max(0.1, energy))
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
    draft_service.add_swarm_placement(
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
        draft_service.remove_plant_placement(draft, index)
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
        draft_service.remove_swarm_placement(draft, index)
    except IndexError as exc:
        api_main.logger.warning("Swarm placement delete requested for unknown index=%d", index)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _render_placement_list_partial(request, draft)


@router.post("/api/config/placements/clear", response_class=HTMLResponse, summary="Clear all placements")
async def config_placements_clear(request: Request) -> Response:
    """Clear all plant and swarm placements and render the updated placement ledger."""
    draft = get_draft()
    draft_service.clear_placements(draft)
    api_main.logger.info("All draft placements cleared via API")
    return _render_placement_list_partial(request, draft)
