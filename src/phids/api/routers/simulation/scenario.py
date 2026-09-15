# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Scenario management endpoints for PHIDS.

This module groups the routes that transition validated configuration data into a live
`SimulationLoop` and then control that runtime through deterministic lifecycle operations. The
endpoints preserve the draft-versus-live boundary: draft editing occurs in separate builder routes,
while this surface performs scenario loading, single-loop execution control, wind mutation, and
serialization import/export. The computational objective is strict reproducibility of ecological
state trajectories, and the biological objective is controlled experimentation over trophic,
signaling, and metabolic dynamics without introducing ad hoc client-side state transitions.
"""

from __future__ import annotations

import asyncio
import contextlib
import json

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse

import phids.api.main as api_main
from phids.api.routers.simulation.helpers import _apply_optional_biotope_overrides_from_form, _status_badge_fragment
from phids.api.schemas.simulation import SimulationConfig
from phids.api.ui_state.state import DraftState, get_draft, set_draft
from phids.engine.loop import SimulationLoop

router = APIRouter()


@router.post("/api/scenario/load", summary="Load simulation scenario")
async def load_scenario(config: SimulationConfig) -> dict[str, int | str]:
    """Initialize live runtime state from a validated scenario payload.

    The endpoint is the strict ingress boundary between static configuration and executable
    ecological dynamics. Existing background execution is cancelled before loop replacement so
    trophic and signaling trajectories remain single-source and deterministic.

    Args:
        config: Validated simulation configuration crossing the API boundary.

    Returns:
        Confirmation payload containing loaded grid dimensions.
    """
    if api_main._sim_task is not None and not api_main._sim_task.done():
        api_main.logger.info("Cancelling existing background simulation task before loading a new scenario")
        api_main._sim_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await api_main._sim_task

    api_main._sim_loop = SimulationLoop(config)
    api_main._set_simulation_substance_names(config)
    api_main.logger.info(
        "Scenario loaded: %dx%d grid, %d flora species, %d herbivore species",
        config.grid_width,
        config.grid_height,
        len(config.flora_species),
        len(config.herbivore_species),
    )
    return {
        "message": "Scenario loaded.",
        "grid_width": config.grid_width,
        "grid_height": config.grid_height,
    }


@router.get("/api/scenario/export", summary="Export draft as JSON")
async def scenario_export() -> Response:
    """Serialize draft configuration into a downloadable scenario artifact.

    Returns:
        JSON response with attachment headers for scenario persistence.

    Raises:
        HTTPException: Draft state cannot be transformed into a valid schema payload.
    """
    draft = get_draft()
    try:
        config = draft.build_sim_config()
        data = json.dumps(config.model_dump(), indent=2)
    except (ValueError, AttributeError) as exc:
        api_main.logger.warning("Scenario export failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    api_main.logger.info("Draft scenario exported (scenario_name=%s)", draft.scenario_name)
    return Response(
        content=data,
        media_type="application/json",
        headers={"Content-Disposition": (f'attachment; filename="{draft.scenario_name.replace(" ", "_")}.json"')},
    )


@router.post("/api/scenario/import", summary="Import scenario from JSON file")
async def scenario_import(file: UploadFile = File(...)) -> JSONResponse:  # noqa: B008
    """Parse an uploaded scenario JSON document and replace draft state.

    Args:
        file: Uploaded JSON scenario artifact.

    Returns:
        Confirmation payload with imported grid dimensions.

    Raises:
        HTTPException: Uploaded content fails JSON parsing or scenario-schema validation.
    """
    raw = await file.read()
    try:
        payload = json.loads(raw)
        config = SimulationConfig.model_validate(payload)
    except Exception as exc:
        api_main.logger.warning("Scenario import failed for file %s: %s", file.filename, exc)
        raise HTTPException(status_code=422, detail=f"Invalid scenario JSON: {exc}") from exc

    new_draft = DraftState.from_sim_config(
        config,
        scenario_name=(file.filename or "imported").replace(".json", ""),
    )
    set_draft(new_draft)
    api_main.logger.info(
        "Scenario imported into draft (file=%s, grid=%dx%d, flora=%d, herbivores=%d)",
        file.filename,
        config.grid_width,
        config.grid_height,
        len(config.flora_species),
        len(config.herbivore_species),
    )
    return JSONResponse(
        content={
            "message": "Scenario imported.",
            "grid_width": config.grid_width,
            "grid_height": config.grid_height,
        }
    )


@router.post(
    "/api/scenario/load-draft",
    response_class=Response,
    summary="Load draft config into simulation engine",
)
async def scenario_load_draft(request: Request) -> Response:
    """Build a validated config from the draft and instantiate a new live loop.

    Args:
        request: Incoming request used for HTMX status-badge rendering.

    Returns:
        Updated status-badge fragment representing live runtime state.

    Raises:
        HTTPException: Draft cannot be transformed into a valid simulation configuration.
    """
    _apply_optional_biotope_overrides_from_form(await request.form())

    draft = get_draft()
    try:
        config = draft.build_sim_config()
    except (ValueError, Exception) as exc:
        api_main.logger.warning("Draft load into simulation failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if api_main._sim_task is not None and not api_main._sim_task.done():
        api_main.logger.info("Cancelling existing background simulation task before loading draft")
        api_main._sim_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await api_main._sim_task

    api_main._sim_loop = SimulationLoop(config)
    api_main._sim_task = None
    api_main._set_simulation_substance_names(config, draft=draft)
    api_main.logger.info(
        "Draft loaded: %dx%d grid, %d flora, %d herbivores",
        config.grid_width,
        config.grid_height,
        len(config.flora_species),
        len(config.herbivore_species),
    )
    return _status_badge_fragment()
