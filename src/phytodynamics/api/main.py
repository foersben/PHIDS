"""FastAPI application: REST endpoints and WebSocket streaming for PHIDS.

Endpoints
---------
POST /api/scenario/load
    Accept a SimulationConfig JSON payload and initialise the simulation loop.

POST /api/simulation/start
    Begin (or resume) simulation execution.

POST /api/simulation/pause
    Toggle pause state.

GET  /api/simulation/status
    Return current simulation state.

PUT  /api/simulation/wind
    Dynamically update the wind vector.

GET  /api/telemetry/export/csv
    Download the Lotka-Volterra telemetry as a CSV file.

GET  /api/telemetry/export/json
    Download the Lotka-Volterra telemetry as a JSON file.

WS   /ws/simulation/stream
    Stream the two-dimensional grid state at each tick.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
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

    Parameters
    ----------
    config:
        Complete :class:`~phytodynamics.api.schemas.SimulationConfig` payload.

    Returns
    -------
    dict
        Confirmation message with grid dimensions.
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
    """Begin background execution of the simulation loop."""
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
    """Toggle pause state of the running simulation."""
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
    """Return the current tick, running/paused/terminated flags."""
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

    Parameters
    ----------
    payload:
        :class:`~phytodynamics.api.schemas.WindUpdatePayload` with ``wind_x``
        and ``wind_y`` fields.
    """
    loop = _get_loop()
    loop.update_wind(payload.wind_x, payload.wind_y)
    return {"message": "Wind updated.", "wind_x": payload.wind_x, "wind_y": payload.wind_y}


@app.get("/api/telemetry/export/csv", summary="Export telemetry as CSV")
async def export_telemetry_csv() -> Response:
    """Stream Lotka-Volterra analytics as a downloadable CSV file."""
    loop = _get_loop()
    data = export_bytes_csv(loop.telemetry.dataframe)
    return Response(
        content=data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=telemetry.csv"},
    )


@app.get("/api/telemetry/export/json", summary="Export telemetry as JSON")
async def export_telemetry_json() -> Response:
    """Stream Lotka-Volterra analytics as a downloadable newline-delimited JSON file."""
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

    The state is serialised with msgpack for compact binary transport.
    If the simulation has not been loaded yet, the socket is closed with
    code 1008 (Policy Violation).
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
                await websocket.send_bytes(msgpack.packb(snapshot, use_bin_type=True))
                break

            if loop.tick != last_tick:
                snapshot = loop.get_state_snapshot()
                await websocket.send_bytes(msgpack.packb(snapshot, use_bin_type=True))
                last_tick = loop.tick

            await asyncio.sleep(1.0 / max(1.0, loop.config.tick_rate_hz))

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected from /ws/simulation/stream")
    finally:
        await websocket.close()
