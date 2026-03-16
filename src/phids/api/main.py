"""FastAPI composition root for PHIDS runtime orchestration.

This module assembles the canonical application object, owns the live single-simulation runtime, and
defines the helper functions that bridge draft-state editing, deterministic `SimulationLoop`
execution, telemetry summarisation, and WebSocket transport. Route registration is now partitioned:
low-risk HTML and telemetry surfaces are delegated to dedicated router modules, while the remaining
control, mutation, and streaming endpoints stay co-located with the shared mutable runtime they
operate upon. This arrangement preserves the biological and computational invariants of PHIDS,
including strict draft-versus-live separation, double-buffered environment advancement, and
operator-facing observation of emergent plant-herbivore defence dynamics.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import json
import logging
import pathlib
import time
import zlib
from typing import Any

import msgpack  # type: ignore[import-untyped]
from pydantic import TypeAdapter, ValidationError
from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from phids.api.schemas import (
    ConditionNode,
    SimulationConfig,
)
from phids.api.routers.batch import router as batch_router
from phids.api.routers.simulation import router as simulation_router
from phids.api.routers.config import router as config_router
from phids.api.routers.telemetry import router as telemetry_router
from phids.api.routers.ui import router as ui_router
from phids.api.ui_state import (
    DraftState,
    TriggerRule,
    get_draft,
)
from phids.engine.loop import SimulationLoop
from phids.shared.logging_config import configure_logging

configure_logging()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Jinja2 templates (resolved relative to this file)
# ---------------------------------------------------------------------------
_TEMPLATE_DIR = pathlib.Path(__file__).parent / "templates"
_STATIC_DIR = pathlib.Path(__file__).parent / "static"

templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))

app = FastAPI(
    title="PHIDS – Plant-Herbivore Interaction & Defense Simulator",
    description=(
        "Visual discrete-event simulator modelling ecological dynamics between "
        "plants and herbivores on a spatial grid."
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
    """Log API/UI request timing with low overhead.

    DEBUG logging is emitted for successful API, HTMX, and UI requests.
    WARNING logging is emitted for client/server error responses.
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
_stream_cache_loop_id: int = -1
_stream_cache_tick: int = -1
_stream_cache_payload: bytes = b""
_BATCH_DIR = pathlib.Path("data") / "batches"


def _coerce_int(value: object, *, default: int = -1) -> int:
    """Return ``value`` coerced to ``int`` when possible, otherwise ``default``."""
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _coerce_float(value: object, *, default: float = 0.0) -> float:
    """Return ``value`` coerced to ``float`` when possible, otherwise ``default``."""
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _default_substance_name(substance_id: int, *, is_toxin: bool) -> str:
    """Return a deterministic fallback label for a substance id."""
    return f"{'Toxin' if is_toxin else 'Signal'} {substance_id}"


def _set_simulation_substance_names(
    config: SimulationConfig,
    *,
    draft: DraftState | None = None,
) -> None:
    """Refresh tooltip/display labels for live-simulation substances."""
    global _sim_substance_names  # noqa: PLW0603

    if draft is not None:
        _sim_substance_names = {
            definition.substance_id: definition.name for definition in draft.substance_definitions
        }
        return

    derived_names: dict[int, str] = {}
    for flora in config.flora_species:
        for trigger in flora.triggers:
            derived_names.setdefault(
                trigger.substance_id,
                _default_substance_name(
                    trigger.substance_id,
                    is_toxin=trigger.is_toxin,
                ),
            )
    _sim_substance_names = derived_names


def _substance_name(substance_id: int, *, is_toxin: bool) -> str:
    """Return the best available display name for a substance id."""
    return _sim_substance_names.get(
        substance_id,
        _default_substance_name(substance_id, is_toxin=is_toxin),
    )


def _parse_activation_condition_json(raw: str | None) -> dict[str, Any] | None:
    """Parse and validate a JSON activation-condition tree from the UI."""
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid condition JSON: {exc.msg}") from exc

    try:
        condition = _condition_adapter.validate_python(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid activation condition: {exc}") from exc
    return condition.model_dump(mode="json")


def _describe_activation_condition(
    condition: dict[str, Any] | None,
    *,
    predator_names: dict[int, str] | None = None,
    substance_names: dict[int, str] | None = None,
) -> str:
    """Render a human-readable summary for a nested activation-condition tree."""
    if condition is None:
        return "unconditional"

    kind = condition.get("kind")
    if kind == "enemy_presence":
        predator_species_id = _coerce_int(condition.get("predator_species_id", -1), default=-1)
        min_population = _coerce_int(condition.get("min_predator_population", 1), default=1)
        predator_label = (
            predator_names.get(predator_species_id, f"Predator {predator_species_id}")
            if predator_names is not None
            else f"Predator {predator_species_id}"
        )
        return f"{predator_label} ≥ {min_population}"
    if kind == "substance_active":
        substance_id = _coerce_int(condition.get("substance_id", -1), default=-1)
        substance_label = (
            substance_names.get(substance_id, _default_substance_name(substance_id, is_toxin=False))
            if substance_names is not None
            else _default_substance_name(substance_id, is_toxin=False)
        )
        return f"{substance_label} active"
    if kind == "environmental_signal":
        signal_id = _coerce_int(condition.get("signal_id", -1), default=-1)
        min_conc = float(condition.get("min_concentration", 0.01))
        signal_label = (
            substance_names.get(signal_id, _default_substance_name(signal_id, is_toxin=False))
            if substance_names is not None
            else _default_substance_name(signal_id, is_toxin=False)
        )
        return f"{signal_label} concentration ≥ {min_conc:.2f}"

    children = [child for child in condition.get("conditions", []) if isinstance(child, dict)]
    joiner = " AND " if kind == "all_of" else " OR "
    if not children:
        return "unconditional"
    rendered = [
        _describe_activation_condition(
            child,
            predator_names=predator_names,
            substance_names=substance_names,
        )
        for child in children
    ]
    return f"({joiner.join(rendered)})"


def _trigger_rules_template_context(draft: DraftState) -> dict[str, Any]:
    """Build the shared template context for the trigger-rules editor."""
    predator_names = {
        getattr(species, "species_id", index): getattr(species, "name", f"Predator {index}")
        for index, species in enumerate(draft.predator_species)
    }
    substance_names = {
        definition.substance_id: definition.name for definition in draft.substance_definitions
    }
    return {
        "flora_species": draft.flora_species,
        "predator_species": draft.predator_species,
        "trigger_rules": draft.trigger_rules,
        "substances": draft.substance_definitions,
        "trigger_rule_condition_json": {
            index: json.dumps(rule.activation_condition, indent=2)
            if rule.activation_condition is not None
            else ""
            for index, rule in enumerate(draft.trigger_rules)
        },
        "trigger_rule_condition_summary": {
            index: _describe_activation_condition(
                rule.activation_condition,
                predator_names=predator_names,
                substance_names=substance_names,
            )
            for index, rule in enumerate(draft.trigger_rules)
        },
        "condition_group_kinds": ["all_of", "any_of"],
        "condition_leaf_kinds": [
            "enemy_presence",
            "substance_active",
            "environmental_signal",
        ],
    }


def _default_activation_condition_for_rule(
    draft: DraftState,
    rule: TriggerRule,
    node_kind: str,
) -> dict[str, Any]:
    """Create a default condition node tailored to one trigger rule."""
    default_predator_species_id = rule.predator_species_id
    default_substance_id = rule.substance_id
    for definition in draft.substance_definitions:
        if definition.substance_id != rule.substance_id:
            default_substance_id = definition.substance_id
            break

    if node_kind == "enemy_presence":
        return {
            "kind": "enemy_presence",
            "predator_species_id": default_predator_species_id,
            "min_predator_population": max(1, rule.min_predator_population),
        }
    if node_kind == "substance_active":
        return {"kind": "substance_active", "substance_id": default_substance_id}
    if node_kind == "environmental_signal":
        return {
            "kind": "environmental_signal",
            "signal_id": rule.substance_id,
            "min_concentration": 0.01,
        }
    if node_kind in {"all_of", "any_of"}:
        return {
            "kind": node_kind,
            "conditions": [
                {
                    "kind": "enemy_presence",
                    "predator_species_id": default_predator_species_id,
                    "min_predator_population": max(1, rule.min_predator_population),
                }
            ],
        }
    raise HTTPException(status_code=400, detail=f"Unsupported condition node kind: {node_kind}")


def _trigger_rule_by_index(draft: DraftState, index: int) -> TriggerRule:
    """Return one trigger rule or raise 404."""
    if index < 0 or index >= len(draft.trigger_rules):
        raise HTTPException(status_code=404, detail=f"Trigger rule {index} not found.")
    return draft.trigger_rules[index]


def _validate_cell_coordinates(x: int, y: int, width: int, height: int) -> None:
    """Reject cell lookups outside the configured grid bounds.

    This thin shim delegates to :func:`phids.api.presenters.dashboard._validate_cell_coordinates`
    and is retained for backward-compatibility with existing test surfaces.
    """
    from phids.api.presenters.dashboard import _validate_cell_coordinates as _pres_validate

    _pres_validate(x, y, width, height)


def _build_draft_mycorrhizal_links(draft: DraftState) -> list[dict[str, Any]]:
    """Return potential root links implied by adjacent draft plant placements.

    Delegates to the presenter layer.  Retained as a backward-compatibility shim.
    """
    from phids.api.presenters.dashboard import _build_draft_mycorrhizal_links as _pres_links

    return _pres_links(draft)


# ---------------------------------------------------------------------------
# Backward-compatibility shims for the three moved payload builders.
# The real implementations live in phids.api.presenters.dashboard.
# ---------------------------------------------------------------------------


def _build_live_cell_details(loop: SimulationLoop, x: int, y: int) -> dict[str, Any]:
    """Build a rich tooltip payload for one live-simulation grid cell.

    Delegates to :func:`phids.api.presenters.dashboard.build_live_cell_details`.
    """
    from phids.api.presenters.dashboard import build_live_cell_details

    return build_live_cell_details(loop, x, y, substance_names=_sim_substance_names)


def _build_preview_cell_details(x: int, y: int) -> dict[str, Any]:
    """Build a tooltip payload for one draft/preview grid cell.

    Delegates to :func:`phids.api.presenters.dashboard.build_preview_cell_details`.
    """
    from phids.api.presenters.dashboard import build_preview_cell_details

    return build_preview_cell_details(x, y, draft=get_draft(), substance_names=_sim_substance_names)


def _build_live_dashboard_payload(loop: SimulationLoop) -> dict[str, Any]:
    """Build the JSON payload used by the live dashboard canvas websocket.

    Delegates to :func:`phids.api.presenters.dashboard.build_live_dashboard_payload`.
    """
    from phids.api.presenters.dashboard import build_live_dashboard_payload

    return build_live_dashboard_payload(loop, substance_names=_sim_substance_names)


def _build_live_summary() -> dict[str, Any] | None:
    """Return coarse live-model counters for the diagnostics rail."""
    if _sim_loop is None:
        return None

    from phids.engine.components.plant import PlantComponent
    from phids.engine.components.substances import SubstanceComponent
    from phids.engine.components.swarm import SwarmComponent

    world = _sim_loop.world
    plants = sum(1 for _ in world.query(PlantComponent))
    swarms = sum(1 for _ in world.query(SwarmComponent))
    active_substances = 0
    for entity in world.query(SubstanceComponent):
        substance = entity.get_component(SubstanceComponent)
        if (
            substance.active
            or substance.synthesis_remaining > 0
            or substance.aftereffect_remaining_ticks > 0
        ):
            active_substances += 1
    return {
        "tick": _sim_loop.tick,
        "running": _sim_loop.running,
        "paused": _sim_loop.paused,
        "terminated": _sim_loop.terminated,
        "termination_reason": _sim_loop.termination_reason,
        "plants": plants,
        "swarms": swarms,
        "active_substances": active_substances,
    }


def _build_energy_deficit_swarms() -> list[dict[str, Any]]:
    """Return swarms currently in an energy-deficit state."""
    if _sim_loop is None:
        return []

    from phids.engine.components.swarm import SwarmComponent

    predator_names = {
        species.species_id: species.name for species in _sim_loop.config.predator_species
    }
    energy_stressed: list[dict[str, Any]] = []
    for entity in _sim_loop.world.query(SwarmComponent):
        swarm = entity.get_component(SwarmComponent)
        energy_deficit = float(max(0.0, swarm.population * swarm.energy_min - swarm.energy))
        if energy_deficit <= 0.0:
            continue
        energy_stressed.append(
            {
                "entity_id": swarm.entity_id,
                "name": predator_names.get(swarm.species_id, f"Predator {swarm.species_id}"),
                "population": swarm.population,
                "energy_deficit": energy_deficit,
                "x": swarm.x,
                "y": swarm.y,
                "repelled": swarm.repelled,
            }
        )
    energy_stressed.sort(
        key=lambda swarm: (
            -_coerce_float(swarm.get("energy_deficit", 0.0), default=0.0),
            str(swarm.get("name", "")),
        )
    )
    return energy_stressed[:12]


def _render_status_badge_html() -> str:
    """Return the current simulation status badge HTML fragment."""
    if _sim_loop is None:
        label, colour = "Idle", "bg-slate-100 text-slate-500"
    elif _sim_loop.terminated:
        label, colour = "Terminated", "bg-red-100 text-red-600"
    elif _sim_loop.paused:
        label, colour = "Paused", "bg-amber-100 text-amber-600"
    elif _sim_loop.running:
        label, colour = "Running", "bg-emerald-100 text-emerald-600"
    else:
        label, colour = "Loaded", "bg-indigo-100 text-indigo-600"

    return (
        f'<span id="sim-status" '
        f'hx-get="/api/ui/status-badge" hx-trigger="every 2s" hx-swap="outerHTML" '
        f'class="text-xs px-2 py-1 rounded {colour}">{label}</span>'
    )


def _is_htmx_request(request: Request) -> bool:
    """Return whether a request originated from HTMX."""
    return request.headers.get("HX-Request", "false").lower() == "true"


def _get_loop() -> SimulationLoop:
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


@app.websocket("/ws/simulation/stream")
async def simulation_stream(websocket: WebSocket) -> None:
    """Stream grid state snapshots over WebSocket at each simulation tick.

    The state is serialised with :mod:`msgpack` and compressed with
    :mod:`zlib` for compact binary transport. If no scenario is loaded the
    connection is closed with code 1008 (Policy Violation).
    """
    await websocket.accept()
    logger.debug("WebSocket connected: /ws/simulation/stream")

    if _sim_loop is None:
        logger.warning("Closing /ws/simulation/stream because no scenario is loaded")
        await websocket.close(code=1008, reason="No scenario loaded.")
        return

    loop = _sim_loop
    last_tick = -1
    global _stream_cache_loop_id, _stream_cache_tick, _stream_cache_payload

    def _encoded_snapshot_bytes() -> bytes:
        """Return cached compressed bytes for the current loop tick."""
        global _stream_cache_loop_id, _stream_cache_tick, _stream_cache_payload
        loop_id = id(loop)
        if loop_id != _stream_cache_loop_id or loop.tick != _stream_cache_tick:
            snapshot = loop.get_state_snapshot()
            packed = msgpack.packb(snapshot, use_bin_type=True)
            _stream_cache_payload = zlib.compress(packed, level=1)
            _stream_cache_loop_id = loop_id
            _stream_cache_tick = loop.tick
        return _stream_cache_payload

    try:
        while True:
            if loop.terminated:
                # Send final state and close
                if loop.tick != last_tick:
                    await websocket.send_bytes(_encoded_snapshot_bytes())
                break

            if loop.tick != last_tick:
                await websocket.send_bytes(_encoded_snapshot_bytes())
                last_tick = loop.tick

            await asyncio.sleep(1.0 / max(1.0, loop.config.tick_rate_hz))

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected from /ws/simulation/stream")
    finally:
        await websocket.close()


# ---------------------------------------------------------------------------
# UI WebSocket – JSON stream for canvas rendering
# ---------------------------------------------------------------------------


@app.websocket("/ws/ui/stream")
async def ui_stream(websocket: WebSocket) -> None:
    """Stream lightweight JSON grid snapshots for the browser canvas.

    Each message contains ``plant_energy`` (2-D list), ``swarms``
    (list of ``{x, y, population}``), ``tick``, and ``max_energy``.
    Reconnects are handled client-side with an exponential back-off.
    """
    await websocket.accept()
    logger.debug("WebSocket connected: /ws/ui/stream")
    last_state_signature: tuple[int, int, bool, bool, bool] | None = None
    try:
        while True:
            loop = _sim_loop
            if loop is None:
                await asyncio.sleep(0.5)
                continue

            loop_id = id(loop)
            state_signature = (loop_id, loop.tick, loop.running, loop.paused, loop.terminated)
            # Send whenever the rendered state changes, including pause/resume toggles.
            if state_signature != last_state_signature:
                from phids.api.presenters.dashboard import build_live_dashboard_payload

                payload = build_live_dashboard_payload(loop, substance_names=_sim_substance_names)
                await websocket.send_text(json.dumps(payload))
                last_state_signature = state_signature

            await asyncio.sleep(1.0 / max(1.0, loop.config.tick_rate_hz))

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected from /ws/ui/stream")
    finally:
        await websocket.close()


# ---------------------------------------------------------------------------
# UI polling helpers
# ---------------------------------------------------------------------------


@app.get("/api/ui/tick", summary="Current simulation tick (plain text)")
async def ui_tick() -> Response:
    """Return the current tick as plain text for HTMX innerHTML swap.

    Returns:
        Response: Tick count as plain-text body.
    """
    tick = _sim_loop.tick if _sim_loop is not None else 0
    return Response(content=str(tick), media_type="text/plain")


@app.get("/api/ui/status-badge", summary="Simulation status badge HTML")
async def ui_status_badge() -> HTMLResponse:
    """Return a small status ``<span>`` for HTMX outerHTML swap.

    Returns:
        HTMLResponse: Styled ``<span id="sim-status">`` fragment.
    """
    return HTMLResponse(content=_render_status_badge_html())


@app.get("/api/ui/cell-details", summary="Detailed tooltip payload for one grid cell")
async def ui_cell_details(x: int, y: int, expected_tick: int | None = None) -> JSONResponse:
    """Return rich grid-cell details for dashboard tooltips.

    When a live simulation exists, data is sourced from the current ECS world
    and environment layers. Otherwise the draft placement preview is returned.
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

    from phids.api.presenters.dashboard import build_live_cell_details, build_preview_cell_details

    payload = (
        build_live_cell_details(_sim_loop, x, y, substance_names=_sim_substance_names)
        if _sim_loop is not None
        else build_preview_cell_details(
            x, y, draft=get_draft(), substance_names=_sim_substance_names
        )
    )
    return JSONResponse(content=payload)


# ---------------------------------------------------------------------------
# Telemetry chart (HTMX-polled SVG)
# ---------------------------------------------------------------------------


def _build_telemetry_svg(df: Any) -> str:  # df is polars.DataFrame
    """Generate an inline SVG line chart from telemetry data.

    Args:
        df: Polars DataFrame with columns ``tick``, ``flora_population``,
            ``predator_population``, ``total_flora_energy``.

    Returns:
        str: SVG markup suitable for ``innerHTML`` injection.
    """
    import polars as pl

    if not isinstance(df, pl.DataFrame) or df.is_empty() or len(df) < 2:
        return (
            '<svg width="100%" height="80" viewBox="0 0 800 80">'
            '<text x="400" y="44" text-anchor="middle" fill="#94a3b8" font-size="13">'
            "No telemetry data yet."
            "</text></svg>"
        )

    W, H, pad = 800, 160, 30
    ticks: list[int] = df["tick"].to_list()
    flora_pop: list[int] = df["flora_population"].to_list()
    pred_pop: list[int] = df["predator_population"].to_list()
    flora_e: list[float] = df["total_flora_energy"].to_list()

    max_tick = max(ticks) or 1
    max_pop = max(max(flora_pop, default=1), max(pred_pop, default=1)) or 1
    max_energy = max(flora_e, default=1.0) or 1.0

    def sx(t: int) -> float:
        return pad + (t / max_tick) * (W - 2 * pad)

    def sy_pop(v: int) -> float:
        return H - pad - (v / max_pop) * (H - 2 * pad)

    def sy_e(v: float) -> float:
        return H - pad - (v / max_energy) * (H - 2 * pad)

    n = len(ticks)
    fp_path = " ".join(
        f"{'M' if i == 0 else 'L'}{sx(ticks[i]):.1f},{sy_pop(flora_pop[i]):.1f}" for i in range(n)
    )
    pp_path = " ".join(
        f"{'M' if i == 0 else 'L'}{sx(ticks[i]):.1f},{sy_pop(pred_pop[i]):.1f}" for i in range(n)
    )
    fe_path = " ".join(
        f"{'M' if i == 0 else 'L'}{sx(ticks[i]):.1f},{sy_e(flora_e[i]):.1f}" for i in range(n)
    )

    return (
        f'<svg width="100%" height="{H}" viewBox="0 0 {W} {H}" class="w-full">'
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
