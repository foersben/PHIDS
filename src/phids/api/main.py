# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""FastAPI composition root governing live runtime state and API boundary coordination.

This module defines the canonical PHIDS application object and the mutable singleton references that
bind operator actions to a live ``SimulationLoop`` instance. The implementation mediates the
transition between draft-state configuration and executable simulation state, and wires router modules
that partition control, telemetry, and builder responsibilities. WebSocket transport loops are delegated to
dedicated manager classes, while this module retains ownership of endpoint registration and runtime
state access.

The architecture enforces the central methodological invariant of the PHIDS interface layer:
editable draft configuration remains distinct from live ecological state until explicit load
operations occur. This separation preserves deterministic replayability of trophic interaction,
signal propagation, and metabolic attrition trajectories.
"""

from __future__ import annotations

import asyncio  # noqa: TC003
import logging
import pathlib
import time
from functools import partial
from typing import TYPE_CHECKING

from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
)
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import TypeAdapter

from phids.api.presenters.dashboard import (
    build_live_cell_details,
    build_live_dashboard_payload,
    build_preview_cell_details,
)
from phids.api.presenters.dashboard.shared import (
    _default_substance_name,
)
from phids.api.presenters.diagnostics import render_status_badge_html
from phids.api.routers import (
    batch_router,
    config_router,
    dse_router,
    dse_ws_router,
    simulation_router,
    telemetry_router,
    ui_router,
)
from phids.api.schemas import (
    ConditionNode,
    SimulationConfig,
)
from phids.api.ui_state import (
    DraftState,
    get_draft,
)
from phids.api.websockets import SimulationStreamManager, UIStreamManager
from phids.shared.logging_config import configure_logging

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from phids.engine.loop import SimulationLoop

configure_logging()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Jinja2 templates (resolved relative to this file)
# ---------------------------------------------------------------------------
_TEMPLATE_DIR = pathlib.Path(__file__).parent / "templates"
_STATIC_DIR = pathlib.Path(__file__).parent / "static"

templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))

app = FastAPI(
    title="PHIDS - Plant-Herbivore Interaction & Defense Simulator",
    description=(
        "Visual discrete-event simulator modelling ecological dynamics between plants and herbivores on a spatial grid."
    ),
    version="0.4.0",
)

# Mount static files only if the directory exists
if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.middleware("http")
async def log_http_requests(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Record request-latency diagnostics for interactive API and UI surfaces.

    The middleware emits lightweight observability events for HTMX and REST traffic so operator
    workflows can be correlated with backend latency and error rates. The policy is asymmetric by
    design: client/server failures are elevated to warning level, whereas successful paths are kept
    at debug level to avoid telemetry inflation under nominal workloads.

    Args:
        request: Incoming HTTP request object.
        call_next: Downstream ASGI callable that resolves the response.

    Returns:
        Response returned by downstream middleware and route handling.

    """
    started = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - started) * 1000.0

    is_interactive_path = request.url.path.startswith(("/api/", "/ui/")) or request.url.path == "/"
    if response.status_code >= 400 and is_interactive_path:
        logger.warning(
            "HTTP %s %s -> %d in %.2fms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
    elif is_interactive_path and logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "HTTP %s %s -> %d in %.2fms%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            " [HTMX]" if _is_htmx_request(request) else "",
        )

    return response


# ---------------------------------------------------------------------------
# Global simulation state (single active instance)
# ---------------------------------------------------------------------------
_sim_loop: SimulationLoop | None = None
_sim_task: asyncio.Task[None] | None = None
_sim_substance_names: dict[int, str] = {}
_condition_adapter: TypeAdapter[ConditionNode] = TypeAdapter(ConditionNode)
_BATCH_DIR = pathlib.Path("data") / "batches"


def _set_simulation_substance_names(
    config: SimulationConfig,
    *,
    draft: DraftState | None = None,
) -> None:
    """Refresh display labels used by live dashboard and tooltip payload builders.

    The naming map is derived either from explicit draft substance definitions or, when unavailable,
    from trigger metadata in the validated runtime configuration. This preserves human-readable
    chemical labels across draft-preview and live-execution contexts without mutating engine state.

    Args:
        config: Validated simulation configuration currently associated with the live loop.
        draft: Optional draft source of canonical user-specified substance labels.

    """
    if draft is not None:
        _sim_substance_names.clear()
        _sim_substance_names.update(
            {definition.substance_id: definition.name for definition in draft.substance_definitions}
        )
        return

    from phids.api.schemas import SynthesizeSubstanceAction

    derived_names: dict[int, str] = {}
    for flora in config.flora_species:
        for trigger in flora.triggers:
            if isinstance(trigger.action, SynthesizeSubstanceAction):
                derived_names.setdefault(
                    trigger.action.substance_id,
                    _default_substance_name(
                        trigger.action.substance_id,
                        is_toxin=trigger.action.is_toxin,
                    ),
                )
    _sim_substance_names.clear()
    _sim_substance_names.update(derived_names)


def _substance_name(substance_id: int, *, is_toxin: bool) -> str:
    """Resolve the most informative display label for one substance identifier.

    Args:
        substance_id: Substance-layer identifier.
        is_toxin: Flag used by fallback naming when no explicit label exists.

    Returns:
        Display name suitable for diagnostics and tooltip rendering.

    """
    return _sim_substance_names.get(
        substance_id,
        _default_substance_name(substance_id, is_toxin=is_toxin),
    )


def _is_htmx_request(request: Request) -> bool:
    """Determine whether a request originated from HTMX transport headers.

    Args:
        request: Incoming HTTP request.

    Returns:
        ``True`` when the request was issued by HTMX.

    """
    return request.headers.get("HX-Request", "false").lower() == "true"


def _get_loop() -> SimulationLoop:
    """Return the active simulation loop or raise a user-facing runtime precondition error.

    Returns:
        Active live simulation loop.

    Raises:
        HTTPException: No scenario has been loaded into live runtime state.

    """
    if _sim_loop is None:
        logger.warning("Simulation access requested before a scenario was loaded")
        raise HTTPException(
            status_code=400,
            detail="No scenario loaded. POST /api/scenario/load first.",
        )
    return _sim_loop


# ---------------------------------------------------------------------------
# Scenario/simulation and batch REST routes are registered via router modules.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# WebSocket streaming
# ---------------------------------------------------------------------------

_simulation_stream_manager = SimulationStreamManager()
_ui_stream_manager = UIStreamManager(
    payload_builder=partial(build_live_dashboard_payload, substance_names=_sim_substance_names)
)


@app.websocket("/ws/simulation/stream")
async def simulation_stream(websocket: WebSocket) -> None:
    """Delegate binary simulation streaming to the simulation stream manager.

    Args:
        websocket: Connected client socket endpoint.

    Notes:
        The manager enforces msgpack+zlib encoding, tick-synchronous emission, and policy-close
        semantics when no live scenario is loaded.

    """
    await _simulation_stream_manager.handle_connection(websocket, _sim_loop)


# ---------------------------------------------------------------------------
# UI WebSocket - JSON stream for canvas rendering
# ---------------------------------------------------------------------------


@app.websocket("/ws/ui/stream")
async def ui_stream(websocket: WebSocket) -> None:
    """Delegate live UI JSON streaming to the UI stream manager.

    Args:
        websocket: Connected client socket endpoint.

    Notes:
        The manager polls live-loop availability, emits payloads only on state-signature change,
        and applies tick-rate cadence constraints.

    """
    await _ui_stream_manager.handle_connection(websocket, lambda: _sim_loop)


# ---------------------------------------------------------------------------
# UI polling helpers
# ---------------------------------------------------------------------------


@app.get("/api/ui/tick", summary="Current simulation tick (plain text)")
async def ui_tick() -> Response:
    """Return the current tick as plain text for HTMX innerHTML swap.

    Returns:
        Plain-text tick content for lightweight polling updates.

    """
    tick = _sim_loop.tick if _sim_loop is not None else 0
    return Response(content=str(tick), media_type="text/plain")


@app.get("/api/ui/status-badge", summary="Simulation status badge HTML")
async def ui_status_badge() -> HTMLResponse:
    """Return a small status ``<span>`` for HTMX outerHTML swap.

    Returns:
        Styled ``<span id="sim-status">`` fragment.

    """
    return HTMLResponse(content=render_status_badge_html(_sim_loop))


@app.get("/api/ui/cell-details", summary="Detailed tooltip payload for one grid cell")
async def ui_cell_details(x: int, y: int, expected_tick: int | None = None) -> JSONResponse:
    """Return rich grid-cell details for dashboard tooltips.

    When a live simulation exists, data is sourced from the current ECS world and environment
    layers. Otherwise the endpoint returns draft-preview payloads so the placement editor can expose
    deterministic pre-runtime inspection.

    Args:
        x: The X-axis spatial grid coordinate.
        y: The Y-axis spatial grid coordinate.
        expected_tick: Optional optimistic-concurrency marker from UI polling state.

    Returns:
        JSON response containing either live cell diagnostics or draft-preview details.

    Raises:
        HTTPException: Upstream presenter validation rejects out-of-bounds coordinates.

    """
    if _sim_loop is not None and expected_tick is not None and expected_tick != _sim_loop.tick:
        return JSONResponse(
            status_code=409,
            content={
                "detail": "Live simulation advanced before tooltip details were fetched.",
                "expected_tick": expected_tick,
                "tick": _sim_loop.tick,
            },
        )

    payload = (
        build_live_cell_details(_sim_loop, x, y, substance_names=_sim_substance_names)
        if _sim_loop is not None
        else build_preview_cell_details(x, y, draft=get_draft(), substance_names=_sim_substance_names)
    )
    return JSONResponse(content=payload)


# ---------------------------------------------------------------------------
# Telemetry chart (HTMX-polled SVG)
# ---------------------------------------------------------------------------


def _build_telemetry_svg(df: object) -> str:
    """Generate an inline SVG line chart from telemetry data.

    Args:
        df: Tabular telemetry object with columns ``tick``, ``flora_population``,
            ``herbivore_population``, ``total_flora_energy``.

    Returns:
        SVG markup suitable for ``innerHTML`` injection.

    Notes:
        The chart intentionally overlays flora population, herbivore population, and aggregate flora
        energy on a shared temporal axis to support rapid diagnosis of trophic oscillation and
        metabolic collapse onset.

    """
    import polars as pl

    if not isinstance(df, pl.DataFrame) or df.is_empty() or len(df) < 2:
        return (
            '<svg width="100%" height="80" viewBox="0 0 800 80">'
            '<text x="400" y="44" text-anchor="middle" fill="#94a3b8" font-size="13">'
            "No telemetry data yet."
            "</text></svg>"
        )

    w, h, pad = 800, 160, 30
    ticks: list[int] = df["tick"].to_list()
    flora_pop: list[int] = df["flora_population"].to_list()
    herbivore_pop: list[int] = df["herbivore_population"].to_list()
    flora_e: list[float] = df["total_flora_energy"].to_list()

    max_tick = max(ticks) or 1
    max_pop = max(max(flora_pop, default=1), max(herbivore_pop, default=1)) or 1
    max_energy = max(flora_e, default=1.0) or 1.0

    def sx(t: int) -> float:
        return pad + (t / max_tick) * (w - 2 * pad)

    def sy_pop(v: int) -> float:
        return h - pad - (v / max_pop) * (h - 2 * pad)

    def sy_e(v: float) -> float:
        return h - pad - (v / max_energy) * (h - 2 * pad)

    n = len(ticks)
    fp_path = " ".join(f"{'M' if i == 0 else 'L'}{sx(ticks[i]):.1f},{sy_pop(flora_pop[i]):.1f}" for i in range(n))
    pp_path = " ".join(f"{'M' if i == 0 else 'L'}{sx(ticks[i]):.1f},{sy_pop(herbivore_pop[i]):.1f}" for i in range(n))
    fe_path = " ".join(f"{'M' if i == 0 else 'L'}{sx(ticks[i]):.1f},{sy_e(flora_e[i]):.1f}" for i in range(n))

    return (
        f'<svg width="100%" height="{h}" viewBox="0 0 {w} {h}" class="w-full">'
        f'<path d="{fp_path}" stroke="#22c55e" stroke-width="2" fill="none"/>'
        f'<path d="{pp_path}" stroke="#ef4444" stroke-width="2" fill="none"/>'
        f'<path d="{fe_path}" stroke="#60a5fa" stroke-width="1.5" fill="none" stroke-dasharray="4 2"/>'
        f"</svg>"
    )


# ---------------------------------------------------------------------------
# Draft-configuration routes are registered via ``phids.api.routers.config``.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Scenario import/export and simulation lifecycle routes live in routers/simulation.py.
# ---------------------------------------------------------------------------


app.include_router(batch_router)
app.include_router(simulation_router)
app.include_router(config_router)
app.include_router(telemetry_router)
app.include_router(ui_router)
app.include_router(dse_router)
app.include_router(dse_ws_router)
