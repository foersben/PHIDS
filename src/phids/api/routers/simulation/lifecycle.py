# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Simulation lifecycle routes.

This module provides routes for starting, pausing, stepping, resetting,
and querying the status of the simulation.
"""

from __future__ import annotations

import asyncio
import contextlib

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse

import phids.api.main as api_main
from phids.api.schemas.responses import SimulationStatusResponse
from phids.api.ui_state.state import get_draft
from phids.engine.loop import SimulationLoop

from .helpers import (
    _apply_optional_biotope_overrides_from_form,
    _status_badge_fragment,
)

router = APIRouter()


@router.post("/api/simulation/start", summary="Start simulation background task")
async def start_simulation(request: Request) -> Response:
    """Launch the continuous determinist tick loop in a background asyncio task.

    Args:
        request: Incoming HTTP request used to select JSON or HTMX fragment responses.

    Returns:
        Status payload or status-badge fragment, depending on caller context.

    Raises:
        HTTPException: A terminated simulation is asked to restart without reset.
    """
    _apply_optional_biotope_overrides_from_form(await request.form())

    loop = api_main._get_loop()
    draft = get_draft()
    loop.update_tick_rate(draft.tick_rate_hz)
    loop.update_wind(draft.wind_x, draft.wind_y)

    if loop.running and not loop.paused:
        api_main.logger.info("Start requested while simulation was already running")
        if api_main._is_htmx_request(request):
            return _status_badge_fragment()
        return JSONResponse({"message": "Simulation already running."})

    if loop.terminated:
        api_main.logger.warning("Start requested for a terminated simulation (reason=%s)", loop.termination_reason)
        raise HTTPException(status_code=400, detail="Simulation has terminated.")

    loop.start()

    if api_main._sim_task is None or api_main._sim_task.done():
        api_main.logger.info(
            "Starting background simulation task (tick_rate_hz=%.2f)",
            loop.config.tick_rate_hz,
        )

        async def _bg() -> None:
            try:
                await loop.run()
            except asyncio.CancelledError:
                api_main.logger.info("Background simulation task cancelled")
            except Exception as e:
                api_main.logger.exception("Background simulation task encountered a fatal error: %s", e)

        api_main._sim_task = asyncio.create_task(_bg())
        api_main.logger.info("Background simulation task created")
    else:
        api_main.logger.info("Simulation resumed using active background task")

    api_main.logger.info("Simulation started via API")
    if api_main._is_htmx_request(request):
        return _status_badge_fragment()
    return JSONResponse({"message": "Simulation started."})


@router.post("/api/simulation/pause", summary="Pause simulation background task")
async def pause_simulation(request: Request) -> Response:
    """Toggle pause state of the active live simulation loop.

    Args:
        request: Incoming HTTP request used to select JSON or HTMX fragment responses.

    Returns:
        Status payload or status-badge fragment with updated pause state.
    """
    _apply_optional_biotope_overrides_from_form(await request.form())

    loop = api_main._get_loop()

    if loop.terminated:
        api_main.logger.info("Pause requested on terminated simulation loop")
        if api_main._is_htmx_request(request):
            return _status_badge_fragment()
        return JSONResponse({"message": "Simulation terminated.", "paused": loop.paused, "running": loop.running})

    if not loop.running:
        loop.pause()
        state = "paused"
    elif loop.paused:
        loop.start()

        if api_main._sim_task is None or api_main._sim_task.done():

            async def _bg() -> None:
                try:
                    await loop.run()
                except asyncio.CancelledError:
                    api_main.logger.info("Background simulation task cancelled")
                except Exception as e:
                    api_main.logger.exception("Background simulation task encountered a fatal error: %s", e)

            api_main._sim_task = asyncio.create_task(_bg())
        state = "resumed"
    else:
        loop.pause()
        state = "paused"

    api_main.logger.info("Simulation %s via API", state)
    if api_main._is_htmx_request(request):
        return _status_badge_fragment()
    return JSONResponse({"message": f"Simulation {state}.", "paused": loop.paused, "running": loop.running})


@router.post("/api/simulation/step", summary="Advance simulation by one tick")
async def step_simulation(request: Request) -> Response:
    """Execute exactly one deterministic tick on the active simulation loop.

    Before stepping, this synchronizes any pending draft parameters (such as tick rate
    and wind vectors) into the live engine to ensure the step matches the latest UI configurations.

    Raises:
        HTTPException: If the simulation is currently running or has already terminated.
    """
    _apply_optional_biotope_overrides_from_form(await request.form())

    loop = api_main._get_loop()
    draft = get_draft()
    loop.update_tick_rate(draft.tick_rate_hz)
    loop.update_wind(draft.wind_x, draft.wind_y)

    if api_main._sim_task is not None and not api_main._sim_task.done() and loop.running and not loop.paused:
        api_main.logger.warning("Single-step requested while simulation is already running")
        raise HTTPException(status_code=400, detail="Pause the simulation before stepping.")

    if loop.terminated:
        api_main.logger.warning(
            "Single-step requested for a terminated simulation (reason=%s)",
            loop.termination_reason,
        )
        raise HTTPException(status_code=400, detail="Simulation has terminated.")

    result = await loop.step()
    api_main.logger.info(
        "Simulation advanced by one tick via API (tick=%d, terminated=%s)",
        loop.tick,
        result.terminated,
    )
    if api_main._is_htmx_request(request):
        return _status_badge_fragment()
    return JSONResponse(
        {
            "message": "Simulation advanced by one tick.",
            "tick": loop.tick,
            "terminated": loop.terminated,
            "termination_reason": loop.termination_reason,
        }
    )


@router.post("/api/simulation/reset", summary="Reset simulation to the loaded scenario")
async def reset_simulation(request: Request) -> Response:
    """Recreate live runtime state from the loaded baseline scenario.

    Args:
        request: Incoming HTTP request used to select JSON or HTMX fragment responses.

    Returns:
        Status payload or status-badge fragment for the reset state.
    """
    _apply_optional_biotope_overrides_from_form(await request.form())

    loop = api_main._get_loop()

    if api_main._sim_task is not None and not api_main._sim_task.done():
        api_main.logger.info("Cancelling existing background simulation task before reset")
        api_main._sim_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await api_main._sim_task

    api_main._sim_loop = SimulationLoop(loop.config)
    api_main._sim_task = None
    api_main._set_simulation_substance_names(loop.config)
    api_main.logger.info("Simulation reset to the loaded scenario")
    if api_main._is_htmx_request(request):
        return _status_badge_fragment()
    return JSONResponse({"message": "Simulation reset.", "tick": 0})


@router.get(
    "/api/simulation/status",
    response_model=SimulationStatusResponse,
    summary="Get simulation status",
)
async def simulation_status() -> SimulationStatusResponse:
    """Return lifecycle status and tick position for the active simulation.

    Returns:
        Structured lifecycle state for polling and control-plane diagnostics.
    """
    loop = api_main._get_loop()
    return SimulationStatusResponse(
        tick=loop.tick,
        tick_rate_hz=loop.config.tick_rate_hz,
        running=loop.running,
        paused=loop.paused,
        terminated=loop.terminated,
        termination_reason=loop.termination_reason,
    )
