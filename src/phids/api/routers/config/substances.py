"""Substances configuration routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

import phids.api.main as api_main
from phids.api.services.draft_service import DraftService
from phids.api.ui_state import SubstanceDefinition, get_draft

router = APIRouter()
draft_service = DraftService()


@router.post(
    "/api/config/substances",
    response_class=HTMLResponse,
    summary="Add substance definition to draft",
)
async def config_substance_add(
    request: Request,
    name: Annotated[str, Form()] = "Signal",
    is_toxin: Annotated[str, Form()] = "false",
    lethal: Annotated[str, Form()] = "false",
    repellent: Annotated[str, Form()] = "false",
    synthesis_duration: Annotated[int, Form()] = 3,
    aftereffect_ticks: Annotated[int, Form()] = 0,
    lethality_rate: Annotated[float, Form()] = 0.0,
    repellent_walk_ticks: Annotated[int, Form()] = 3,
    energy_cost_per_tick: Annotated[float, Form()] = 1.0,
    irreversible: Annotated[str, Form()] = "false",
) -> Response:
    """Add one substance definition to the draft and render the updated substance table."""
    draft = get_draft()
    try:
        definition: SubstanceDefinition = draft_service.add_substance(
            draft,
            name=name,
            is_toxin=is_toxin,
            lethal=lethal,
            repellent=repellent,
            synthesis_duration=synthesis_duration,
            aftereffect_ticks=aftereffect_ticks,
            lethality_rate=lethality_rate,
            repellent_walk_ticks=repellent_walk_ticks,
            energy_cost_per_tick=energy_cost_per_tick,
            irreversible=irreversible,
        )
    except ValueError as exc:
        api_main.logger.warning("Rule-of-16 rejected substance creation")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    api_main.logger.info(
        "Substance added via API (substance_id=%d, name=%s, is_toxin=%s)",
        definition.substance_id,
        definition.name,
        definition.is_toxin,
    )
    return api_main.templates.TemplateResponse(
        request,
        "partials/substance_config.html",
        {"substances": draft.substance_definitions},
    )


@router.put(
    "/api/config/substances/{substance_id}",
    response_class=HTMLResponse,
    summary="Update substance definition row",
)
async def config_substance_update(
    request: Request,
    substance_id: int,
    name: Annotated[str | None, Form()] = None,
    type_label: Annotated[str | None, Form()] = None,
    synthesis_duration: Annotated[int | None, Form()] = None,
    aftereffect_ticks: Annotated[int | None, Form()] = None,
    lethality_rate: Annotated[float | None, Form()] = None,
    repellent_walk_ticks: Annotated[int | None, Form()] = None,
    energy_cost_per_tick: Annotated[float | None, Form()] = None,
    irreversible: Annotated[str | None, Form()] = None,
) -> Response:
    """Patch one substance definition in the draft and render the updated table."""
    draft = get_draft()
    try:
        sd: SubstanceDefinition = draft_service.update_substance(
            draft,
            substance_id,
            name=name,
            type_label=type_label,
            synthesis_duration=synthesis_duration,
            aftereffect_ticks=aftereffect_ticks,
            lethality_rate=lethality_rate,
            repellent_walk_ticks=repellent_walk_ticks,
            energy_cost_per_tick=energy_cost_per_tick,
            irreversible=irreversible,
        )
    except ValueError as exc:
        api_main.logger.warning("Substance update requested for unknown substance_id=%d", substance_id)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    api_main.logger.debug("Substance updated via API (substance_id=%d, name=%s)", substance_id, sd.name)

    return api_main.templates.TemplateResponse(
        request,
        "partials/substance_config.html",
        {"substances": draft.substance_definitions},
    )


@router.delete(
    "/api/config/substances/{substance_id}",
    response_class=HTMLResponse,
    summary="Delete substance definition",
)
async def config_substance_delete(substance_id: int) -> HTMLResponse:
    """Remove one substance definition from the draft."""
    draft = get_draft()
    try:
        draft_service.remove_substance(draft, substance_id)
    except ValueError as exc:
        api_main.logger.warning("Substance delete requested for unknown substance_id=%d", substance_id)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    api_main.logger.info("Substance deleted via API (substance_id=%d)", substance_id)
    return HTMLResponse(content="")
