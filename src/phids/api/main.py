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

import asyncio
from collections.abc import Awaitable, Callable
from functools import partial
import json
import logging
import pathlib
import time
from typing import TypedDict

from pydantic import TypeAdapter, ValidationError
from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
)
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from phids.api.schemas import (
    ConditionNode,
    SimulationConfig,
)
from phids.api.routers.batch import router as batch_router
from phids.api.presenters.dashboard import (
    build_live_cell_details,
    build_live_dashboard_payload,
    build_preview_cell_details,
)
from phids.api.routers.simulation import router as simulation_router
from phids.api.routers.config import router as config_router
from phids.api.routers.telemetry import router as telemetry_router
from phids.api.routers.ui import router as ui_router
from phids.api.ui_state import (
    ActivationConditionNode,
    DraftState,
    TriggerRule,
    get_draft,
)
from phids.api.websockets import SimulationStreamManager, UIStreamManager
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


class LiveSummary(TypedDict):
    """Structured live-runtime counters for diagnostics and status rendering."""

    tick: int
    running: bool
    paused: bool
    terminated: bool
    termination_reason: str | None
    plants: int
    swarms: int
    active_substances: int


class EnergyDeficitSwarmRow(TypedDict):
    """One leaderboard row describing a swarm with positive metabolic energy deficit."""

    entity_id: int
    name: str
    population: int
    energy_deficit: float
    x: int
    y: int
    repelled: bool


def _coerce_int(value: object, *, default: int = -1) -> int:
    """Coerce heterogeneous scalar inputs into deterministic integer values.

    The diagnostics and compatibility surfaces accept polymorphic scalar payloads from UI controls,
    telemetry shims, and historical fixtures. This helper stabilizes those values into canonical
    integer form so downstream ordering and threshold logic remains reproducible.

    Args:
        value: Candidate scalar to normalize.
        default: Fallback value used when coercion is unsafe or invalid.

    Returns:
        Normalized integer suitable for deterministic control-flow decisions.
    """
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
    """Coerce heterogeneous scalar inputs into deterministic floating-point values.

    The helper mirrors integer coercion semantics for quantitative telemetry and rendering fields
    where malformed values must degrade gracefully without destabilizing dashboard calculations.

    Args:
        value: Candidate scalar to normalize.
        default: Fallback value used when coercion is unsafe or invalid.

    Returns:
        Normalized floating-point value for deterministic arithmetic paths.
    """
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
    """Construct deterministic fallback nomenclature for unlabeled substances.

    Args:
        substance_id: Substance-layer identifier.
        is_toxin: Flag distinguishing toxin and signal label prefixes.

    Returns:
        Stable human-readable fallback label.
    """
    return f"{'Toxin' if is_toxin else 'Signal'} {substance_id}"


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


def _parse_activation_condition_json(raw: str | None) -> ActivationConditionNode | None:
    """Parse and validate a serialized activation-condition tree from builder input.

    Args:
        raw: Raw JSON text submitted from trigger-rule editing controls.

    Returns:
        Normalized condition dictionary, or ``None`` when the input is absent/blank.

    Raises:
        HTTPException: Condition JSON is syntactically invalid or violates schema constraints.
    """
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
    condition: ActivationConditionNode | None,
    *,
    herbivore_names: dict[int, str] | None = None,
    substance_names: dict[int, str] | None = None,
) -> str:
    """Render a compact textual explanation of a nested activation-condition tree.

    The formatter translates discriminated condition nodes into operator-readable logic statements
    that preserve quantitative thresholds and boolean composition. This summary is used in the
    trigger editor to expose the biological gating semantics of toxin/signal activation.

    Args:
        condition: Parsed activation-condition node or tree.
        herbivore_names: Optional species-name map for herbivore identifiers.
        substance_names: Optional display-name map for substance identifiers.

    Returns:
        Human-readable logical expression describing the activation gate.
    """
    if condition is None:
        return "unconditional"

    kind = condition.get("kind")
    if kind == "herbivore_presence":
        herbivore_species_id = _coerce_int(condition.get("herbivore_species_id", -1), default=-1)
        min_population = _coerce_int(condition.get("min_herbivore_population", 1), default=1)
        herbivore_label = (
            herbivore_names.get(herbivore_species_id, f"Herbivore {herbivore_species_id}")
            if herbivore_names is not None
            else f"Herbivore {herbivore_species_id}"
        )
        return f"{herbivore_label} ≥ {min_population}"
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
        min_conc = _coerce_float(condition.get("min_concentration", 0.01), default=0.01)
        signal_label = (
            substance_names.get(signal_id, _default_substance_name(signal_id, is_toxin=False))
            if substance_names is not None
            else _default_substance_name(signal_id, is_toxin=False)
        )
        return f"{signal_label} concentration ≥ {min_conc:.2f}"

    raw_children = condition.get("conditions", [])
    children = (
        [child for child in raw_children if isinstance(child, dict)]
        if isinstance(raw_children, list)
        else []
    )
    joiner = " AND " if kind == "all_of" else " OR "
    if not children:
        return "unconditional"
    rendered = [
        _describe_activation_condition(
            child,
            herbivore_names=herbivore_names,
            substance_names=substance_names,
        )
        for child in children
    ]
    return f"({joiner.join(rendered)})"


def _trigger_rules_template_context(draft: DraftState) -> dict[str, object]:
    """Assemble the canonical template context for trigger-rule partial rendering.

    Args:
        draft: Active draft scenario state used as the authoritative builder source.

    Returns:
        Template context dictionary containing species registries, trigger rows, condition summaries,
        and condition-node editing metadata.
    """
    herbivore_names = {
        getattr(species, "species_id", index): getattr(species, "name", f"Herbivore {index}")
        for index, species in enumerate(draft.herbivore_species)
    }
    substance_names = {
        definition.substance_id: definition.name for definition in draft.substance_definitions
    }
    return {
        "flora_species": draft.flora_species,
        "herbivore_species": draft.herbivore_species,
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
                herbivore_names=herbivore_names,
                substance_names=substance_names,
            )
            for index, rule in enumerate(draft.trigger_rules)
        },
        "condition_group_kinds": ["all_of", "any_of"],
        "condition_leaf_kinds": [
            "herbivore_presence",
            "substance_active",
            "environmental_signal",
        ],
    }


def _default_activation_condition_for_rule(
    draft: DraftState,
    rule: TriggerRule,
    node_kind: str,
) -> ActivationConditionNode:
    """Construct a default activation-condition node compatible with a trigger rule.

    Args:
        draft: Active draft state containing species and substance registries.
        rule: Trigger rule being edited.
        node_kind: Requested node discriminator.

    Returns:
        Default node payload suitable for insertion into a condition tree.

    Raises:
        HTTPException: ``node_kind`` is unsupported by the condition editor.
    """
    default_herbivore_species_id = rule.herbivore_species_id
    default_substance_id = rule.substance_id
    for definition in draft.substance_definitions:
        if definition.substance_id != rule.substance_id:
            default_substance_id = definition.substance_id
            break

    if node_kind == "herbivore_presence":
        return {
            "kind": "herbivore_presence",
            "herbivore_species_id": default_herbivore_species_id,
            "min_herbivore_population": max(1, rule.min_herbivore_population),
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
                    "kind": "herbivore_presence",
                    "herbivore_species_id": default_herbivore_species_id,
                    "min_herbivore_population": max(1, rule.min_herbivore_population),
                }
            ],
        }
    raise HTTPException(status_code=400, detail=f"Unsupported condition node kind: {node_kind}")


def _trigger_rule_by_index(draft: DraftState, index: int) -> TriggerRule:
    """Return one trigger rule from draft state with HTTP-oriented bounds checking.

    Args:
        draft: Active draft state containing trigger rules.
        index: Positional index requested by route handlers.

    Returns:
        Trigger rule at the requested index.

    Raises:
        HTTPException: Index is outside the current trigger-rule list bounds.
    """
    if index < 0 or index >= len(draft.trigger_rules):
        raise HTTPException(status_code=404, detail=f"Trigger rule {index} not found.")
    return draft.trigger_rules[index]


def _build_live_summary() -> LiveSummary | None:
    """Aggregate coarse live-model counters for diagnostics surfaces.

    Returns:
        Summary counters when a live loop exists, otherwise ``None``.
    """
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
    summary: LiveSummary = {
        "tick": _sim_loop.tick,
        "running": _sim_loop.running,
        "paused": _sim_loop.paused,
        "terminated": _sim_loop.terminated,
        "termination_reason": _sim_loop.termination_reason,
        "plants": plants,
        "swarms": swarms,
        "active_substances": active_substances,
    }
    return summary


def _build_energy_deficit_swarms() -> list[EnergyDeficitSwarmRow]:
    """Rank live swarms by metabolic energy deficit severity.

    Returns:
        Sorted stress records for swarm entities with positive energy deficits.
    """
    if _sim_loop is None:
        return []

    from phids.engine.components.swarm import SwarmComponent

    herbivore_names = {
        species.species_id: species.name for species in _sim_loop.config.herbivore_species
    }
    energy_stressed: list[EnergyDeficitSwarmRow] = []
    for entity in _sim_loop.world.query(SwarmComponent):
        swarm = entity.get_component(SwarmComponent)
        energy_deficit = float(max(0.0, swarm.population * swarm.energy_min - swarm.energy))
        if energy_deficit <= 0.0:
            continue
        energy_stressed.append(
            {
                "entity_id": swarm.entity_id,
                "name": herbivore_names.get(swarm.species_id, f"Herbivore {swarm.species_id}"),
                "population": swarm.population,
                "energy_deficit": energy_deficit,
                "x": swarm.x,
                "y": swarm.y,
                "repelled": swarm.repelled,
            }
        )
    energy_stressed.sort(
        key=lambda swarm: (
            -swarm["energy_deficit"],
            swarm["name"],
        )
    )
    return energy_stressed[:12]


def _render_status_badge_html() -> str:
    """Render the HTMX-polled simulation status badge fragment.

    Returns:
        HTML fragment encoding current lifecycle state with semantic coloring.
    """
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
# UI WebSocket – JSON stream for canvas rendering
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
    return HTMLResponse(content=_render_status_badge_html())


@app.get("/api/ui/cell-details", summary="Detailed tooltip payload for one grid cell")
async def ui_cell_details(x: int, y: int, expected_tick: int | None = None) -> JSONResponse:
    """Return rich grid-cell details for dashboard tooltips.

    When a live simulation exists, data is sourced from the current ECS world and environment
    layers. Otherwise the endpoint returns draft-preview payloads so the placement editor can expose
    deterministic pre-runtime inspection.

    Args:
        x: Grid x-coordinate.
        y: Grid y-coordinate.
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
        else build_preview_cell_details(
            x, y, draft=get_draft(), substance_names=_sim_substance_names
        )
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

    W, H, pad = 800, 160, 30
    ticks: list[int] = df["tick"].to_list()
    flora_pop: list[int] = df["flora_population"].to_list()
    herbivore_pop: list[int] = df["herbivore_population"].to_list()
    flora_e: list[float] = df["total_flora_energy"].to_list()

    max_tick = max(ticks) or 1
    max_pop = max(max(flora_pop, default=1), max(herbivore_pop, default=1)) or 1
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
        f"{'M' if i == 0 else 'L'}{sx(ticks[i]):.1f},{sy_pop(herbivore_pop[i]):.1f}"
        for i in range(n)
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
