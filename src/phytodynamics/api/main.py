"""FastAPI application exposing REST endpoints and WebSocket streaming.

The application provides endpoints for loading scenarios, controlling the
simulation lifecycle, updating environmental parameters and exporting
telemetry. A WebSocket endpoint streams per-tick grid snapshots.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import zlib
from typing import Any

import msgpack  # type: ignore[import-untyped]
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from phytodynamics.api.schemas import (
    SimulationConfig,
    SimulationStatusResponse,
    WindUpdatePayload,
)
from phytodynamics.engine.loop import SimulationLoop
from phytodynamics.telemetry.export import export_bytes_csv, export_bytes_json

logger = logging.getLogger(__name__)

app = FastAPI(
    title="PHIDS – Plant-Herbivore Interaction & Defense Simulator",
    description=(
        "Visual discrete-event simulator modelling ecological dynamics between "
        "plants and herbivores on a spatial grid."
    ),
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# Global simulation state (single active instance)
# ---------------------------------------------------------------------------
_sim_loop: SimulationLoop | None = None
_sim_task: asyncio.Task[None] | None = None


def _get_loop() -> SimulationLoop:
    if _sim_loop is None:
        raise HTTPException(
            status_code=400,
            detail="No scenario loaded. POST /api/scenario/load first.",
        )
    return _sim_loop


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------


@app.post("/api/scenario/load", summary="Load simulation scenario")
async def load_scenario(config: SimulationConfig) -> dict[str, Any]:
    """Initialise the simulation loop with the provided configuration.

    Args:
        config: Validated :class:`~phytodynamics.api.schemas.SimulationConfig`.

    Returns:
        dict: Confirmation message including grid dimensions.
    """
    global _sim_loop, _sim_task  # noqa: PLW0603

    # Cancel any running simulation
    if _sim_task is not None and not _sim_task.done():
        _sim_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _sim_task

    _sim_loop = SimulationLoop(config)
    logger.info("Scenario loaded: %dx%d grid, %d flora species, %d predator species",
                config.grid_width, config.grid_height,
                len(config.flora_species), len(config.predator_species))
    return {
        "message": "Scenario loaded.",
        "grid_width": config.grid_width,
        "grid_height": config.grid_height,
    }


@app.post("/api/simulation/start", summary="Start or resume simulation")
async def start_simulation() -> dict[str, str]:
    """Begin background execution of the simulation loop.

    Returns:
        dict: Message confirming the simulation was started.
    """
    global _sim_task  # noqa: PLW0603
    loop = _get_loop()

    if loop.running and not loop.paused:
        return {"message": "Simulation already running."}

    if loop.terminated:
        raise HTTPException(status_code=400, detail="Simulation has terminated.")

    loop.start()

    async def _bg() -> None:
        await loop.run()

    _sim_task = asyncio.create_task(_bg())
    return {"message": "Simulation started."}


@app.post("/api/simulation/pause", summary="Pause or resume simulation")
async def pause_simulation() -> dict[str, str]:
    """Toggle pause state of the running simulation.

    Returns:
        dict: Message indicating current paused/resumed state.
    """
    loop = _get_loop()
    loop.pause()
    state = "paused" if loop.paused else "resumed"
    return {"message": f"Simulation {state}."}


@app.get(
    "/api/simulation/status",
    response_model=SimulationStatusResponse,
    summary="Get simulation status",
)
async def simulation_status() -> SimulationStatusResponse:
    """Return the current tick and simulation state flags.

    Returns:
        SimulationStatusResponse: Pydantic response model with status.
    """
    loop = _get_loop()
    return SimulationStatusResponse(
        tick=loop.tick,
        running=loop.running,
        paused=loop.paused,
        terminated=loop.terminated,
        termination_reason=loop.termination_reason,
    )


@app.put("/api/simulation/wind", summary="Update wind vector")
async def update_wind(payload: WindUpdatePayload) -> dict[str, Any]:
    """Dynamically update the simulation wind vector.

    Args:
        payload: :class:`~phytodynamics.api.schemas.WindUpdatePayload`.

    Returns:
        dict: Confirmation and the applied wind vector.
    """
    loop = _get_loop()
    loop.update_wind(payload.wind_x, payload.wind_y)
    return {"message": "Wind updated.", "wind_x": payload.wind_x, "wind_y": payload.wind_y}


@app.get("/api/telemetry/export/csv", summary="Export telemetry as CSV")
async def export_telemetry_csv() -> Response:
    """Stream Lotka-Volterra analytics as a downloadable CSV file.

    Returns:
        Response: FastAPI response containing CSV bytes and headers.
    """
    loop = _get_loop()
    data = export_bytes_csv(loop.telemetry.dataframe)
    return Response(
        content=data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=telemetry.csv"},
    )


@app.get("/api/telemetry/export/json", summary="Export telemetry as JSON")
async def export_telemetry_json() -> Response:
    """Stream Lotka-Volterra analytics as a downloadable NDJSON file.

    Returns:
        Response: FastAPI response containing NDJSON bytes and headers.
    """
    loop = _get_loop()
    data = export_bytes_json(loop.telemetry.dataframe)
    return Response(
        content=data,
        media_type="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=telemetry.ndjson"},
    )


# ---------------------------------------------------------------------------
# WebSocket streaming
# ---------------------------------------------------------------------------


@app.websocket("/ws/simulation/stream")
async def simulation_stream(websocket: WebSocket) -> None:
    """Stream grid state snapshots over WebSocket at each simulation tick.

    The state is serialised with :mod:`msgpack` and compressed with
    :mod:`zlib` for compact binary transport. If no scenario is loaded the
    connection is closed with code 1008 (Policy Violation).
    """
    await websocket.accept()

    if _sim_loop is None:
        await websocket.close(code=1008, reason="No scenario loaded.")
        return

    loop = _sim_loop
    last_tick = -1

    try:
        while True:
            if loop.terminated:
                # Send final state and close
                snapshot = loop.get_state_snapshot()
                packed = msgpack.packb(snapshot, use_bin_type=True)
                await websocket.send_bytes(zlib.compress(packed))
                break

            if loop.tick != last_tick:
                snapshot = loop.get_state_snapshot()
                packed = msgpack.packb(snapshot, use_bin_type=True)
                await websocket.send_bytes(zlib.compress(packed))
                last_tick = loop.tick

            await asyncio.sleep(1.0 / max(1.0, loop.config.tick_rate_hz))

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected from /ws/simulation/stream")
    finally:
        await websocket.close()
