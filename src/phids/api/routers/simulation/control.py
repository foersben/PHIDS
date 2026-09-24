# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Simulation control routes.

This module provides routes for updating real-time parameters
of the simulation, such as tick rate and wind.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import JSONResponse
from phids.api.schemas.responses import WindUpdatePayload

import phids.api.main as api_main
from phids.api.ui_state.state import get_draft

from .helpers import _status_badge_fragment


router = APIRouter()


@router.put("/api/simulation/tick-rate", summary="Update live simulation tick speed")
async def update_tick_rate(
    request: Request,
    tick_rate_hz: Annotated[float, Form()] = 10.0,
) -> Response:
    """Update the active simulation tick-speed in the live grid view.

    The new tick rate is immediately applied to the active `SimulationLoop` and also
    synchronized back to the `DraftState` so it persists across scenario reloads.

    Args:
        request: Incoming HTTP request used to select JSON or HTMX fragment responses.
        tick_rate_hz: Requested simulation ticks per second.

    Returns:
        Status payload or status-badge fragment, depending on caller context.
    """
    loop = api_main._get_loop()
    applied_tick_rate = loop.update_tick_rate(tick_rate_hz)
    get_draft().tick_rate_hz = applied_tick_rate
    api_main.logger.info("Live simulation tick rate updated via API to %.2f Hz", applied_tick_rate)
    if api_main._is_htmx_request(request):
        return _status_badge_fragment()
    return JSONResponse({"message": "Tick rate updated.", "tick_rate_hz": applied_tick_rate})


@router.put("/api/simulation/wind", summary="Update wind vector")
async def update_wind(payload: WindUpdatePayload) -> dict[str, float | str]:
    """Update the uniform wind vector field of the active environment.

    The new wind vector is applied to the active `SimulationLoop` and also
    synchronized back into the `DraftState` so it persists across scenario reloads.

    Args:
        payload: Requested wind components in simulation coordinate space.

    Returns:
        Confirmation payload echoing the applied wind vector.
    """
    loop = api_main._get_loop()
    loop.update_wind(payload.wind_x, payload.wind_y)
    draft = get_draft()
    draft.wind_x = payload.wind_x
    draft.wind_y = payload.wind_y
    api_main.logger.info("Wind updated via API to (vx=%.3f, vy=%.3f)", payload.wind_x, payload.wind_y)
    return {"message": "Wind updated.", "wind_x": payload.wind_x, "wind_y": payload.wind_y}
