from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from phids.api.main import templates
from phids.api.schemas import SimulationConfig
from phids.api.services.dse_service import get_dse_manager
from phids.api.ui_state import get_draft
from phids.api.websockets.manager import dse_stream_manager

router = APIRouter(prefix="/api/dse", tags=["DSE"])


@router.post("/start", summary="Start Design Space Exploration Task")
async def start_dse(config: SimulationConfig) -> dict[str, str]:
    """Starts the NSGA-II multithreaded optimizer asynchronously.

    Broadcasts metrics over the `/ws/dse/stream` websocket.
    """
    dse_manager = get_dse_manager(dse_stream_manager)
    dse_manager.start_dse_task(config)
    return {"status": "DSE started"}


@router.post("/stop", summary="Stop Design Space Exploration Task")
async def stop_dse() -> dict[str, str]:
    """Gracefully terminates the DSE optimization background task."""
    dse_manager = get_dse_manager(dse_stream_manager)
    dse_manager.stop_dse_task()
    return {"status": "DSE stopped"}


@router.post("/apply/{candidate_idx}", summary="Apply a Pareto Candidate to Draft", response_class=HTMLResponse)
async def apply_dse_candidate(request: Request, _candidate_idx: int) -> HTMLResponse:
    """Applies the winning genotype payload to the active DraftState and stops the DSE."""
    # In a full implementation we would retrieve the exact genotype from the optimizer's Pareto cache.
    # For now, we stub applying constraints and shutting down the task.
    dse_manager = get_dse_manager(dse_stream_manager)
    dse_manager.stop_dse_task()

    draft = get_draft()
    # E.g. draft.flora_species[0].growth_rate = retrieved_candidate.growth_rate

    return templates.TemplateResponse(
        request,
        "partials/biotope_config.html",
        {"draft": draft, "request": request},
    )


ws_router = APIRouter(tags=["DSE WebSocket"])


@ws_router.websocket("/ws/dse/stream")
async def dse_websocket_stream(websocket: WebSocket) -> None:
    """Provides real-time DSE Generation Pareto-Front metrics."""
    await dse_stream_manager.connect_dse(websocket)
    try:
        while True:
            # Client shouldn't send us data, but keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        dse_stream_manager.disconnect_dse(websocket)
