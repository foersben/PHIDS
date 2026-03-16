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
import contextlib
from collections.abc import Awaitable, Callable
import datetime
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
    File,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from phids.api.schemas import (
    ConditionNode,
    SimulationConfig,
    SimulationStatusResponse,
    WindUpdatePayload,
    BatchJobState,
    BatchStartPayload,
)
from phids.api.routers.config import router as config_router
from phids.api.routers.telemetry import router as telemetry_router
from phids.api.routers.ui import router as ui_router
from phids.api.ui_state import (
    DraftState,
    PlacedPlant,
    PlacedSwarm,
    SubstanceDefinition,
    TriggerRule,
    get_draft,
    set_draft,
)
from phids.engine.loop import SimulationLoop
from phids.telemetry.export import decimate_dataframe, filter_dataframe_columns, generate_tikz_str
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
    """Reject cell lookups outside the configured grid bounds."""
    if not (0 <= x < width and 0 <= y < height):
        raise HTTPException(
            status_code=404,
            detail=f"Cell ({x}, {y}) is outside the current {width}x{height} grid.",
        )


def _build_draft_mycorrhizal_links(draft: DraftState) -> list[dict[str, Any]]:
    """Return potential root links implied by adjacent draft plant placements."""
    links: list[dict[str, Any]] = []
    for left_index, left in enumerate(draft.initial_plants):
        for right_index in range(left_index + 1, len(draft.initial_plants)):
            right = draft.initial_plants[right_index]
            if abs(left.x - right.x) + abs(left.y - right.y) != 1:
                continue
            inter_species = left.species_id != right.species_id
            if inter_species and not draft.mycorrhizal_inter_species:
                continue
            links.append(
                {
                    "plant_index_a": left_index,
                    "plant_index_b": right_index,
                    "x1": left.x,
                    "y1": left.y,
                    "x2": right.x,
                    "y2": right.y,
                    "inter_species": inter_species,
                }
            )
    return links


def _build_live_mycorrhizal_links(loop: SimulationLoop) -> list[dict[str, Any]]:
    """Return unique root links currently active in the live ECS world."""
    from phids.engine.components.plant import PlantComponent

    world = loop.world
    plant_lookup = {
        plant.entity_id: plant
        for entity in world.query(PlantComponent)
        for plant in [entity.get_component(PlantComponent)]
    }
    links: list[dict[str, Any]] = []
    seen_pairs: set[tuple[int, int]] = set()
    for plant_id, plant in plant_lookup.items():
        for neighbour_id in sorted(plant.mycorrhizal_connections):
            if neighbour_id not in plant_lookup:
                continue
            pair = (min(plant_id, neighbour_id), max(plant_id, neighbour_id))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            neighbour = plant_lookup[neighbour_id]
            links.append(
                {
                    "entity_id_a": plant_id,
                    "entity_id_b": neighbour_id,
                    "x1": plant.x,
                    "y1": plant.y,
                    "x2": neighbour.x,
                    "y2": neighbour.y,
                    "inter_species": plant.species_id != neighbour.species_id,
                }
            )
    return links


def _links_touching_cell(links: list[dict[str, Any]], x: int, y: int) -> list[dict[str, Any]]:
    """Return the subset of serialized root links touching one cell."""
    return [
        link
        for link in links
        if (int(link["x1"]) == x and int(link["y1"]) == y)
        or (int(link["x2"]) == x and int(link["y2"]) == y)
    ]


def _is_live_substance_visible(substance: Any) -> bool:
    """Return whether a live substance should be surfaced in UI payloads."""
    return (
        bool(substance.active)
        or bool(substance.triggered_this_tick)
        or int(substance.synthesis_remaining) > 0
        or int(substance.aftereffect_remaining_ticks) > 0
    )


def _live_substance_state_payload(
    *,
    is_toxin: bool,
    active: bool,
    triggered_this_tick: bool,
    synthesis_remaining: int,
    aftereffect_remaining_ticks: int,
    snapshot_only: bool = False,
) -> tuple[str, str]:
    """Describe the current UI-facing runtime state of a substance."""
    if snapshot_only:
        return ("field_snapshot", "visible field residue")
    if synthesis_remaining > 0 and not active:
        return ("synthesizing", "synthesizing")
    if active and triggered_this_tick:
        return ("triggered", "triggered this tick")
    if active and not is_toxin and aftereffect_remaining_ticks > 0:
        return ("aftereffect", "lingering aftereffect")
    if active:
        return ("active", "active emitter")
    if triggered_this_tick:
        return ("triggered", "triggered this tick")
    return ("configured", "configured")


def _serialize_live_substance(
    substance: Any,
    *,
    predator_names: dict[int, str],
) -> dict[str, Any]:
    """Serialize one live runtime substance for dashboard and tooltip payloads."""
    state, state_label = _live_substance_state_payload(
        is_toxin=bool(substance.is_toxin),
        active=bool(substance.active),
        triggered_this_tick=bool(substance.triggered_this_tick),
        synthesis_remaining=int(substance.synthesis_remaining),
        aftereffect_remaining_ticks=int(substance.aftereffect_remaining_ticks),
    )
    return {
        "substance_id": substance.substance_id,
        "name": _substance_name(
            substance.substance_id,
            is_toxin=substance.is_toxin,
        ),
        "kind": "toxin" if substance.is_toxin else "signal",
        "active": substance.active,
        "state": state,
        "state_label": state_label,
        "snapshot_only": False,
        "triggered_this_tick": substance.triggered_this_tick,
        "synthesis_remaining": substance.synthesis_remaining,
        "aftereffect_remaining_ticks": substance.aftereffect_remaining_ticks,
        "lethal": substance.lethal,
        "repellent": substance.repellent,
        "lethality_rate": float(substance.lethality_rate),
        "repellent_walk_ticks": substance.repellent_walk_ticks,
        "trigger_predator_species_id": substance.trigger_predator_species_id,
        "trigger_predator_name": predator_names.get(
            substance.trigger_predator_species_id,
            f"Predator {substance.trigger_predator_species_id}",
        )
        if substance.trigger_predator_species_id >= 0
        else None,
        "trigger_min_predator_population": substance.trigger_min_predator_population,
        "activation_condition": substance.activation_condition,
        "activation_condition_summary": _describe_activation_condition(
            substance.activation_condition,
            predator_names=predator_names,
            substance_names=_sim_substance_names,
        ),
    }


def _fallback_live_substance_payload(
    substance_id: int,
    *,
    is_toxin: bool,
) -> dict[str, Any]:
    """Return a snapshot-only fallback when a local layer is visible without a runtime entity."""
    kind = "toxin" if is_toxin else "signal"
    state, state_label = _live_substance_state_payload(
        is_toxin=is_toxin,
        active=False,
        triggered_this_tick=False,
        synthesis_remaining=0,
        aftereffect_remaining_ticks=0,
        snapshot_only=True,
    )
    return {
        "substance_id": substance_id,
        "name": _substance_name(substance_id, is_toxin=is_toxin),
        "kind": kind,
        "active": False,
        "state": state,
        "state_label": state_label,
        "snapshot_only": True,
        "triggered_this_tick": False,
        "synthesis_remaining": 0,
        "aftereffect_remaining_ticks": 0,
        "lethal": False,
        "repellent": False,
        "lethality_rate": 0.0,
        "repellent_walk_ticks": 0,
        "trigger_predator_species_id": -1,
        "trigger_predator_name": None,
        "trigger_min_predator_population": 0,
        "activation_condition": None,
        "activation_condition_summary": "visible on rendered live snapshot",
    }


def _build_live_cell_details(loop: SimulationLoop, x: int, y: int) -> dict[str, Any]:
    """Build a rich tooltip payload for one live-simulation grid cell."""
    from phids.engine.components.plant import PlantComponent
    from phids.engine.components.substances import SubstanceComponent
    from phids.engine.components.swarm import SwarmComponent

    env = loop.env
    world = loop.world
    _validate_cell_coordinates(x, y, env.width, env.height)

    flora_names = {species.species_id: species.name for species in loop.config.flora_species}
    predator_names = {species.species_id: species.name for species in loop.config.predator_species}

    owned_substances: dict[int, list[SubstanceComponent]] = {}
    for entity in world.query(SubstanceComponent):
        substance = entity.get_component(SubstanceComponent)
        owned_substances.setdefault(substance.owner_plant_id, []).append(substance)

    plant_lookup = {
        plant.entity_id: plant
        for entity in world.query(PlantComponent)
        for plant in [entity.get_component(PlantComponent)]
    }
    live_links = _build_live_mycorrhizal_links(loop)
    touching_links = _links_touching_cell(live_links, x, y)

    plants: list[dict[str, Any]] = []
    swarms: list[dict[str, Any]] = []

    cell_signal_peak = float(env.signal_layers[:, x, y].max()) if env.num_signals > 0 else 0.0
    cell_toxin_peak = float(env.toxin_layers[:, x, y].max()) if env.num_toxins > 0 else 0.0

    for entity_id in sorted(world.entities_at(x, y)):
        if not world.has_entity(entity_id):
            continue
        entity = world.get_entity(entity_id)

        if entity.has_component(PlantComponent):
            plant = entity.get_component(PlantComponent)
            plant_substances = sorted(
                (
                    substance
                    for substance in owned_substances.get(plant.entity_id, [])
                    if _is_live_substance_visible(substance)
                ),
                key=lambda substance: (substance.is_toxin, substance.substance_id),
            )
            visible_substances = [
                _serialize_live_substance(
                    substance,
                    predator_names=predator_names,
                )
                for substance in plant_substances
            ]
            visible_keys = {
                (int(payload["substance_id"]), payload["kind"] == "toxin")
                for payload in visible_substances
            }
            for signal_id in range(env.num_signals):
                if float(env.signal_layers[signal_id, plant.x, plant.y]) <= 0.0:
                    continue
                substance_key = (signal_id, False)
                if substance_key in visible_keys:
                    continue
                visible_substances.append(
                    _fallback_live_substance_payload(signal_id, is_toxin=False)
                )
                visible_keys.add(substance_key)
            for toxin_id in range(env.num_toxins):
                if float(env.toxin_layers[toxin_id, plant.x, plant.y]) <= 0.0:
                    continue
                substance_key = (toxin_id, True)
                if substance_key in visible_keys:
                    continue
                visible_substances.append(_fallback_live_substance_payload(toxin_id, is_toxin=True))
                visible_keys.add(substance_key)
            visible_substances.sort(
                key=lambda payload: (payload["kind"] == "toxin", int(payload["substance_id"]))
            )
            mycorrhizal_neighbours = []
            for neighbour_id in sorted(plant.mycorrhizal_connections):
                neighbour = plant_lookup.get(neighbour_id)
                if neighbour is None:
                    continue
                mycorrhizal_neighbours.append(
                    {
                        "entity_id": neighbour.entity_id,
                        "name": flora_names.get(
                            neighbour.species_id, f"Flora {neighbour.species_id}"
                        ),
                        "x": neighbour.x,
                        "y": neighbour.y,
                        "inter_species": neighbour.species_id != plant.species_id,
                    }
                )
            plants.append(
                {
                    "entity_id": plant.entity_id,
                    "species_id": plant.species_id,
                    "name": flora_names.get(plant.species_id, f"Flora {plant.species_id}"),
                    "energy": float(plant.energy),
                    "max_energy": float(plant.max_energy),
                    "base_energy": float(plant.base_energy),
                    "growth_rate": float(plant.growth_rate),
                    "camouflage": plant.camouflage,
                    "camouflage_factor": float(plant.camouflage_factor),
                    "mycorrhizal_connections": len(plant.mycorrhizal_connections),
                    "mycorrhizal_neighbours": mycorrhizal_neighbours,
                    "active_substances": visible_substances,
                }
            )

        if entity.has_component(SwarmComponent):
            swarm = entity.get_component(SwarmComponent)
            swarms.append(
                {
                    "entity_id": swarm.entity_id,
                    "species_id": swarm.species_id,
                    "name": predator_names.get(swarm.species_id, f"Predator {swarm.species_id}"),
                    "population": swarm.population,
                    "initial_population": swarm.initial_population,
                    "energy": float(swarm.energy),
                    "energy_min": float(swarm.energy_min),
                    "energy_deficit": max(
                        0.0,
                        float(swarm.population * swarm.energy_min - swarm.energy),
                    ),
                    "repelled": swarm.repelled,
                    "repelled_ticks_remaining": swarm.repelled_ticks_remaining,
                    "intoxicated": cell_toxin_peak > 0.0,
                    "signal_level": cell_signal_peak,
                    "toxin_level": cell_toxin_peak,
                }
            )

    signal_concentrations = [
        {
            "substance_id": signal_id,
            "name": _substance_name(signal_id, is_toxin=False),
            "value": float(env.signal_layers[signal_id, x, y]),
        }
        for signal_id in range(env.num_signals)
        if float(env.signal_layers[signal_id, x, y]) > 0.0
    ]
    toxin_concentrations = [
        {
            "substance_id": toxin_id,
            "name": _substance_name(toxin_id, is_toxin=True),
            "value": float(env.toxin_layers[toxin_id, x, y]),
        }
        for toxin_id in range(env.num_toxins)
        if float(env.toxin_layers[toxin_id, x, y]) > 0.0
    ]

    return {
        "mode": "live",
        "tick": loop.tick,
        "x": x,
        "y": y,
        "grid_width": env.width,
        "grid_height": env.height,
        "flow_field": float(env.flow_field[x, y]),
        "wind": {
            "x": float(env.wind_vector_x[x, y]),
            "y": float(env.wind_vector_y[x, y]),
        },
        "signal_peak": cell_signal_peak,
        "toxin_peak": cell_toxin_peak,
        "signal_concentrations": signal_concentrations,
        "toxin_concentrations": toxin_concentrations,
        "mycorrhiza": {
            "enabled": bool(touching_links),
            "link_count": len(touching_links),
            "inter_species_enabled": loop.config.mycorrhizal_inter_species,
            "connection_cost": float(loop.config.mycorrhizal_connection_cost),
            "signal_velocity": loop.config.mycorrhizal_signal_velocity,
            "links": [
                {
                    "from": {"x": int(link["x1"]), "y": int(link["y1"])},
                    "to": {"x": int(link["x2"]), "y": int(link["y2"])},
                    "inter_species": bool(link["inter_species"]),
                }
                for link in touching_links
            ],
        },
        "plants": plants,
        "swarms": swarms,
    }


def _build_preview_cell_details(x: int, y: int) -> dict[str, Any]:
    """Build a tooltip payload for one draft/preview grid cell."""
    draft = get_draft()
    _validate_cell_coordinates(x, y, draft.grid_width, draft.grid_height)

    flora_names = {
        getattr(species, "species_id", index): getattr(species, "name", f"Flora {index}")
        for index, species in enumerate(draft.flora_species)
    }
    predator_names = {
        getattr(species, "species_id", index): getattr(species, "name", f"Predator {index}")
        for index, species in enumerate(draft.predator_species)
    }
    substances = {definition.substance_id: definition for definition in draft.substance_definitions}
    rules_by_flora: dict[int, list[TriggerRule]] = {}
    for rule in draft.trigger_rules:
        rules_by_flora.setdefault(rule.flora_species_id, []).append(rule)

    preview_links = _build_draft_mycorrhizal_links(draft)
    touching_links = _links_touching_cell(preview_links, x, y)

    plants: list[dict[str, Any]] = []
    for index, plant in enumerate(draft.initial_plants):
        if plant.x != x or plant.y != y:
            continue
        mycorrhizal_neighbours = []
        for link in preview_links:
            is_left = int(link["plant_index_a"]) == index
            is_right = int(link["plant_index_b"]) == index
            if not is_left and not is_right:
                continue
            other_index = int(link["plant_index_b"] if is_left else link["plant_index_a"])
            other = draft.initial_plants[other_index]
            mycorrhizal_neighbours.append(
                {
                    "name": flora_names.get(other.species_id, f"Flora {other.species_id}"),
                    "x": other.x,
                    "y": other.y,
                    "inter_species": bool(link["inter_species"]),
                }
            )
        plants.append(
            {
                "index": index,
                "species_id": plant.species_id,
                "name": flora_names.get(plant.species_id, f"Flora {plant.species_id}"),
                "energy": float(plant.energy),
                "mycorrhizal_connections": len(mycorrhizal_neighbours),
                "mycorrhizal_neighbours": mycorrhizal_neighbours,
                "configured_trigger_rules": [
                    {
                        "substance_id": rule.substance_id,
                        "substance_name": (
                            substances[rule.substance_id].name
                            if rule.substance_id in substances
                            else _default_substance_name(rule.substance_id, is_toxin=False)
                        ),
                        "predator_species_id": rule.predator_species_id,
                        "predator_name": predator_names.get(
                            rule.predator_species_id,
                            f"Predator {rule.predator_species_id}",
                        ),
                        "min_predator_population": rule.min_predator_population,
                        "activation_condition": rule.activation_condition,
                        "activation_condition_summary": _describe_activation_condition(
                            rule.activation_condition,
                            predator_names=predator_names,
                            substance_names={
                                substance_id: definition.name
                                for substance_id, definition in substances.items()
                            },
                        ),
                    }
                    for rule in rules_by_flora.get(plant.species_id, [])
                ],
            }
        )

    swarms = [
        {
            "index": index,
            "species_id": swarm.species_id,
            "name": predator_names.get(swarm.species_id, f"Predator {swarm.species_id}"),
            "population": swarm.population,
            "energy": float(swarm.energy),
        }
        for index, swarm in enumerate(draft.initial_swarms)
        if swarm.x == x and swarm.y == y
    ]

    return {
        "mode": "draft",
        "tick": None,
        "x": x,
        "y": y,
        "grid_width": draft.grid_width,
        "grid_height": draft.grid_height,
        "flow_field": None,
        "wind": {"x": draft.wind_x, "y": draft.wind_y},
        "signal_peak": 0.0,
        "toxin_peak": 0.0,
        "signal_concentrations": [],
        "toxin_concentrations": [],
        "mycorrhiza": {
            "enabled": bool(touching_links),
            "link_count": len(touching_links),
            "inter_species_enabled": draft.mycorrhizal_inter_species,
            "connection_cost": float(draft.mycorrhizal_connection_cost),
            "signal_velocity": draft.mycorrhizal_signal_velocity,
            "links": [
                {
                    "from": {"x": int(link["x1"]), "y": int(link["y1"])},
                    "to": {"x": int(link["x2"]), "y": int(link["y2"])},
                    "inter_species": bool(link["inter_species"]),
                }
                for link in touching_links
            ],
        },
        "plants": plants,
        "swarms": swarms,
    }


def _build_live_dashboard_payload(loop: SimulationLoop) -> dict[str, Any]:
    """Build the JSON payload used by the live dashboard canvas websocket."""
    from phids.engine.components.plant import PlantComponent
    from phids.engine.components.substances import SubstanceComponent
    from phids.engine.components.swarm import SwarmComponent

    env = loop.env
    world = loop.world
    max_e = float(env.plant_energy_layer.max()) or 1.0
    signal_overlay = env.signal_layers.max(axis=0) if env.num_signals > 0 else None
    toxin_overlay = env.toxin_layers.max(axis=0) if env.num_toxins > 0 else None

    flora_names = {species.species_id: species.name for species in loop.config.flora_species}
    predator_names = {species.species_id: species.name for species in loop.config.predator_species}

    owned_substances: dict[int, list[SubstanceComponent]] = {}
    for entity in world.query(SubstanceComponent):
        substance = entity.get_component(SubstanceComponent)
        owned_substances.setdefault(substance.owner_plant_id, []).append(substance)

    plants = []
    for entity in world.query(PlantComponent):
        plant = entity.get_component(PlantComponent)
        plant_substances = owned_substances.get(plant.entity_id, [])
        local_signal_ids = {
            signal_id
            for signal_id in range(env.num_signals)
            if float(env.signal_layers[signal_id, plant.x, plant.y]) > 0.0
        }
        local_toxin_ids = {
            toxin_id
            for toxin_id in range(env.num_toxins)
            if float(env.toxin_layers[toxin_id, plant.x, plant.y]) > 0.0
        }
        visible_signal_ids = sorted(
            local_signal_ids
            | {
                substance.substance_id
                for substance in plant_substances
                if not substance.is_toxin and _is_live_substance_visible(substance)
            }
        )
        visible_toxin_ids = sorted(
            local_toxin_ids
            | {
                substance.substance_id
                for substance in plant_substances
                if substance.is_toxin and _is_live_substance_visible(substance)
            }
        )
        plants.append(
            {
                "entity_id": plant.entity_id,
                "species_id": plant.species_id,
                "name": flora_names.get(plant.species_id, f"Flora {plant.species_id}"),
                "x": plant.x,
                "y": plant.y,
                "energy": float(plant.energy),
                "root_link_count": len(plant.mycorrhizal_connections),
                "active_signal_ids": visible_signal_ids,
                "active_toxin_ids": visible_toxin_ids,
            }
        )
    plants.sort(
        key=lambda plant: (
            _coerce_int(plant.get("x", 0), default=0),
            _coerce_int(plant.get("y", 0), default=0),
            _coerce_int(plant.get("species_id", 0), default=0),
        )
    )

    swarms: list[dict[str, Any]] = []
    for entity in world.query(SwarmComponent):
        swarm = entity.get_component(SwarmComponent)
        toxin_level = (
            float(env.toxin_layers[:, swarm.x, swarm.y].max()) if env.num_toxins > 0 else 0.0
        )
        swarms.append(
            {
                "x": swarm.x,
                "y": swarm.y,
                "population": swarm.population,
                "species_id": swarm.species_id,
                "name": predator_names.get(swarm.species_id, f"Predator {swarm.species_id}"),
                "energy": float(swarm.energy),
                "energy_deficit": max(
                    0.0,
                    float(swarm.population * swarm.energy_min - swarm.energy),
                ),
                "repelled": swarm.repelled,
                "repelled_ticks_remaining": swarm.repelled_ticks_remaining,
                "toxin_level": toxin_level,
                "intoxicated": toxin_level > 0.0,
            }
        )
    swarms.sort(
        key=lambda swarm: (
            _coerce_int(swarm.get("x", 0), default=0),
            _coerce_int(swarm.get("y", 0), default=0),
            _coerce_int(swarm.get("species_id", 0), default=0),
        )
    )

    live_flora_species_ids = {
        species_id
        for species_id in (_coerce_int(plant.get("species_id", -1), default=-1) for plant in plants)
        if species_id >= 0
    }
    all_flora_species: list[dict[str, object]] = []
    species_energy: list[dict[str, object]] = []
    for species in loop.config.flora_species:
        species_id = species.species_id
        is_extinct = species_id not in live_flora_species_ids
        all_flora_species.append(
            {
                "species_id": species_id,
                "name": species.name,
                "extinct": is_extinct,
            }
        )
        if is_extinct:
            continue
        if species_id < env.plant_energy_by_species.shape[0]:
            species_energy.append(
                {
                    "species_id": species_id,
                    "name": species.name,
                    "layer": env.plant_energy_by_species[species_id].tolist(),
                }
            )
        else:
            # Defensive fallback: species_id outside pre-allocated layer bounds.
            species_energy.append(
                {
                    "species_id": species_id,
                    "name": species.name,
                    "layer": [[0.0] * env.height for _ in range(env.width)],
                }
            )

    return {
        "tick": loop.tick,
        "grid_width": env.width,
        "grid_height": env.height,
        "max_energy": max_e,
        "species_energy": species_energy,
        "all_flora_species": all_flora_species,
        "signal_overlay": signal_overlay.tolist() if signal_overlay is not None else [],
        "toxin_overlay": toxin_overlay.tolist() if toxin_overlay is not None else [],
        "max_signal": float(signal_overlay.max()) if signal_overlay is not None else 0.0,
        "max_toxin": float(toxin_overlay.max()) if toxin_overlay is not None else 0.0,
        "plants": plants,
        "mycorrhizal_links": _build_live_mycorrhizal_links(loop),
        "swarms": swarms,
        "terminated": loop.terminated,
        "termination_reason": loop.termination_reason,
        "running": loop.running,
        "paused": loop.paused,
    }


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
# REST endpoints
# ---------------------------------------------------------------------------


@app.post("/api/scenario/load", summary="Load simulation scenario")
async def load_scenario(config: SimulationConfig) -> dict[str, Any]:
    """Initialise the simulation loop with the provided configuration.

    Args:
        config: Validated :class:`~phids.api.schemas.SimulationConfig`.

    Returns:
        dict: Confirmation message including grid dimensions.
    """
    global _sim_loop, _sim_task  # noqa: PLW0603

    # Cancel any running simulation
    if _sim_task is not None and not _sim_task.done():
        logger.info("Cancelling existing background simulation task before loading a new scenario")
        _sim_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _sim_task

    _sim_loop = SimulationLoop(config)
    _set_simulation_substance_names(config)
    logger.info(
        "Scenario loaded: %dx%d grid, %d flora species, %d predator species",
        config.grid_width,
        config.grid_height,
        len(config.flora_species),
        len(config.predator_species),
    )
    return {
        "message": "Scenario loaded.",
        "grid_width": config.grid_width,
        "grid_height": config.grid_height,
    }


@app.post("/api/simulation/start", summary="Start or resume simulation")
async def start_simulation(request: Request) -> Any:
    """Begin background execution of the simulation loop.

    Returns:
        dict: Message confirming the simulation was started.
    """
    global _sim_task  # noqa: PLW0603
    loop = _get_loop()

    if loop.running and not loop.paused:
        logger.info("Start requested while simulation was already running")
        if _is_htmx_request(request):
            return HTMLResponse(content=_render_status_badge_html())
        return {"message": "Simulation already running."}

    if loop.terminated:
        logger.warning(
            "Start requested for a terminated simulation (reason=%s)", loop.termination_reason
        )
        raise HTTPException(status_code=400, detail="Simulation has terminated.")

    loop.start()

    async def _bg() -> None:
        await loop.run()

    _sim_task = asyncio.create_task(_bg())
    logger.info("Background simulation task created")
    if _is_htmx_request(request):
        return HTMLResponse(content=_render_status_badge_html())
    return {"message": "Simulation started."}


@app.post("/api/simulation/pause", summary="Pause or resume simulation")
async def pause_simulation(request: Request) -> Any:
    """Toggle pause state of the running simulation.

    Returns:
        dict: Message indicating current paused/resumed state.
    """
    loop = _get_loop()
    loop.pause()
    state = "paused" if loop.paused else "resumed"
    logger.info("Simulation %s via API", state)
    if _is_htmx_request(request):
        return HTMLResponse(content=_render_status_badge_html())
    return {"message": f"Simulation {state}."}


@app.post("/api/simulation/step", summary="Advance simulation by one tick")
async def step_simulation(request: Request) -> Any:
    """Execute a single deterministic simulation tick.

    Returns:
        dict[str, Any]: Updated simulation status after the step.

    Raises:
        HTTPException: If the simulation is running in the background or has terminated.
    """
    loop = _get_loop()

    if _sim_task is not None and not _sim_task.done() and loop.running and not loop.paused:
        logger.warning("Single-step requested while simulation is already running")
        raise HTTPException(status_code=400, detail="Pause the simulation before stepping.")

    if loop.terminated:
        logger.warning(
            "Single-step requested for a terminated simulation (reason=%s)", loop.termination_reason
        )
        raise HTTPException(status_code=400, detail="Simulation has terminated.")

    result = await loop.step()
    logger.info(
        "Simulation advanced by one tick via API (tick=%d, terminated=%s)",
        loop.tick,
        result.terminated,
    )
    if _is_htmx_request(request):
        return HTMLResponse(content=_render_status_badge_html())
    return {
        "message": "Simulation advanced by one tick.",
        "tick": loop.tick,
        "terminated": loop.terminated,
        "termination_reason": loop.termination_reason,
    }


@app.post("/api/simulation/reset", summary="Reset simulation to the loaded scenario")
async def reset_simulation(request: Request) -> Any:
    """Recreate the live simulation loop from the currently loaded config.

    Returns:
        dict[str, Any]: Confirmation and reset tick.
    """
    global _sim_loop, _sim_task  # noqa: PLW0603

    loop = _get_loop()

    if _sim_task is not None and not _sim_task.done():
        logger.info("Cancelling existing background simulation task before reset")
        _sim_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _sim_task

    _sim_loop = SimulationLoop(loop.config)
    _sim_task = None
    _set_simulation_substance_names(loop.config)
    logger.info("Simulation reset to the loaded scenario")
    if _is_htmx_request(request):
        return HTMLResponse(content=_render_status_badge_html())
    return {"message": "Simulation reset.", "tick": 0}


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
        payload: :class:`~phids.api.schemas.WindUpdatePayload`.

    Returns:
        dict: Confirmation and the applied wind vector.
    """
    loop = _get_loop()
    loop.update_wind(payload.wind_x, payload.wind_y)
    logger.info("Wind updated via API to (vx=%.3f, vy=%.3f)", payload.wind_x, payload.wind_y)
    return {"message": "Wind updated.", "wind_x": payload.wind_x, "wind_y": payload.wind_y}


# ---------------------------------------------------------------------------
# Batch processing routes
# ---------------------------------------------------------------------------

_BATCH_DIR = pathlib.Path("data") / "batches"


def _discover_persisted_batches() -> list[BatchJobState]:
    """Discover persisted batch summaries from disk and map them to UI job rows.

    Returns:
        list[BatchJobState]: Jobs reconstructed from ``*_summary.json`` files.
    """
    if not _BATCH_DIR.exists():
        return []

    discovered: list[BatchJobState] = []
    for summary_path in sorted(_BATCH_DIR.glob("*_summary.json")):
        job_id = summary_path.stem.removesuffix("_summary")
        try:
            with summary_path.open(encoding="utf-8") as fp:
                aggregate = json.load(fp)
        except Exception:
            logger.warning("Skipping unreadable batch summary file: %s", summary_path)
            continue

        runs_completed = int(aggregate.get("runs_completed", 1) or 1)
        ticks = aggregate.get("ticks", [])
        started_at = datetime.datetime.fromtimestamp(
            summary_path.stat().st_mtime, tz=datetime.timezone.utc
        )
        discovered.append(
            BatchJobState(
                job_id=job_id,
                status="done",
                completed=runs_completed,
                total=runs_completed,
                scenario_name=f"persisted_{job_id}",
                started_at=started_at.isoformat(),
                finished_at=started_at.isoformat(),
                max_ticks=len(ticks),
            )
        )
    return discovered


@app.post("/api/batch/start", summary="Start a Monte Carlo batch simulation job")
async def batch_start(
    payload: BatchStartPayload,
) -> JSONResponse:
    """Enqueue a Monte Carlo batch simulation job for asynchronous execution.

    Validates the current server-side draft scenario, creates a
    :class:`~phids.api.schemas.BatchJobState` record, inserts it into the
    draft's ``active_batch_jobs`` registry, and dispatches a background
    :class:`asyncio.Task` that drives the
    :class:`~phids.engine.batch.BatchRunner` in a
    :class:`concurrent.futures.ProcessPoolExecutor`. The HTTP response returns
    immediately with the ``job_id`` so the client can begin polling the status
    endpoint.

    Args:
        payload: Batch execution parameters (runs, max_ticks, scenario_name).

    Returns:
        JSONResponse: ``{"job_id": str}`` upon successful enqueue.

    Raises:
        HTTPException: 400 if the current draft cannot produce a valid
            :class:`~phids.api.schemas.SimulationConfig`.
    """
    import datetime
    import uuid

    draft = get_draft()
    try:
        config = draft.build_sim_config()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid draft: {exc}") from exc

    job_id = str(uuid.uuid4())[:8]
    scenario_name = payload.scenario_name or draft.scenario_name
    job = BatchJobState(
        job_id=job_id,
        status="queued",
        completed=0,
        total=payload.runs,
        scenario_name=scenario_name,
        started_at=datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
        max_ticks=payload.max_ticks,
    )
    draft.active_batch_jobs[job_id] = job
    logger.info(
        "Batch job %s enqueued (runs=%d, max_ticks=%d)", job_id, payload.runs, payload.max_ticks
    )

    scenario_dict = config.model_dump()

    async def _run_batch() -> None:
        from phids.engine.batch import BatchRunner

        job.status = "running"
        try:
            _BATCH_DIR.mkdir(parents=True, exist_ok=True)
            runner = BatchRunner()

            loop = asyncio.get_event_loop()

            def _progress(completed: int) -> None:
                job.completed = completed
                logger.debug("Batch job %s progress: %d/%d", job_id, completed, payload.runs)

            await loop.run_in_executor(
                None,
                lambda: runner.execute_batch(
                    scenario_dict,
                    payload.runs,
                    payload.max_ticks,
                    job_id,
                    _BATCH_DIR,
                    _progress,
                ),
            )
            job.status = "done"
            job.completed = payload.runs
        except Exception:
            logger.exception("Batch job %s failed", job_id)
            job.status = "failed"
        finally:
            import datetime as dt

            job.finished_at = dt.datetime.now(tz=dt.timezone.utc).isoformat()

    asyncio.create_task(_run_batch())
    return JSONResponse({"job_id": job_id})


@app.get("/api/batch/status/{job_id}", response_class=HTMLResponse, summary="Batch job status row")
async def batch_status(request: Request, job_id: str) -> Any:
    """Return an HTMX HTML fragment for a single batch job progress row.

    Args:
        request: FastAPI request object.
        job_id: Unique batch job identifier.

    Returns:
        TemplateResponse: Rendered ``partials/batch_job_row.html`` fragment.

    Raises:
        HTTPException: 404 if ``job_id`` is not found.
    """
    draft = get_draft()
    job = draft.active_batch_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return templates.TemplateResponse(
        request,
        "partials/batch_job_row.html",
        {"job": job},
    )


@app.get("/api/batch/ledger", response_class=HTMLResponse, summary="Batch job ledger")
async def batch_ledger(request: Request) -> Any:
    """Return an HTMX HTML fragment listing all batch jobs.

    Args:
        request: FastAPI request object.

    Returns:
        TemplateResponse: Rendered ``partials/batch_ledger.html`` fragment.
    """
    draft = get_draft()
    jobs = list(draft.active_batch_jobs.values())
    return templates.TemplateResponse(
        request,
        "partials/batch_ledger.html",
        {"jobs": jobs},
    )


@app.post("/api/batch/load-persisted", summary="Load persisted batch summaries into the UI ledger")
async def batch_load_persisted() -> JSONResponse:
    """Load persisted batch summaries from disk into draft ``active_batch_jobs``.

    Returns:
        JSONResponse: Number of jobs loaded into memory.
    """
    draft = get_draft()
    loaded = 0
    for job in _discover_persisted_batches():
        if job.job_id not in draft.active_batch_jobs:
            draft.active_batch_jobs[job.job_id] = job
            loaded += 1
    logger.info("Loaded %d persisted batch jobs into UI ledger", loaded)
    return JSONResponse({"loaded": loaded, "total": len(draft.active_batch_jobs)})


@app.get("/api/batch/view/{job_id}", response_class=HTMLResponse, summary="Batch aggregate view")
async def batch_view(request: Request, job_id: str) -> Any:
    """Return an HTMX fragment showing aggregate statistics for a completed batch job.

    Reads the persisted ``{job_id}_summary.json`` from disk and renders the
    aggregate mean±σ chart data. If the file does not exist (e.g., job still
    running), a placeholder message is returned.

    Args:
        request: FastAPI request object.
        job_id: Unique batch job identifier.

    Returns:
        TemplateResponse: Rendered ``partials/batch_view.html`` fragment.
    """
    import json as _json

    draft = get_draft()
    job = draft.active_batch_jobs.get(job_id)
    summary_path = _BATCH_DIR / f"{job_id}_summary.json"
    aggregate: dict[str, Any] = {}
    if summary_path.exists():
        with summary_path.open(encoding="utf-8") as fp:
            aggregate = _json.load(fp)

    return templates.TemplateResponse(
        request,
        "partials/batch_view.html",
        {"job": job, "aggregate": aggregate, "job_id": job_id},
    )


@app.get(
    "/api/batch/export/{job_id}",
    summary="Export batch aggregate in academic formats",
)
async def batch_export(
    job_id: str,
    format: str = "csv",  # noqa: A002
    tick_interval: int = 1,
    columns: str | None = None,
    title: str | None = None,
    x_label: str | None = None,
    y_label: str | None = None,
    chart_type: str = "timeseries",
) -> Response:
    """Export a batch aggregate summary as CSV, LaTeX table, or PGFPlots TikZ source.

    Args:
        job_id: Unique batch job identifier.
        format: Output format — ``csv``, ``tex_table``, or ``tex_tikz``.

    Returns:
        Response: File download with appropriate Content-Type headers.

    Raises:
        HTTPException: 404 if the summary file for ``job_id`` does not exist.
    """
    import json as _json

    summary_path = _BATCH_DIR / f"{job_id}_summary.json"
    if not summary_path.exists():
        raise HTTPException(status_code=404, detail=f"No summary found for job '{job_id}'.")

    with summary_path.open(encoding="utf-8") as fp:
        aggregate: dict[str, Any] = _json.load(fp)

    from phids.telemetry.export import aggregate_to_dataframe

    df = aggregate_to_dataframe(aggregate)
    if tick_interval < 1:
        raise HTTPException(status_code=400, detail="tick_interval must be >= 1")
    df = filter_dataframe_columns(df, columns)
    df = decimate_dataframe(df, tick_interval)

    if format == "csv":
        data = df.to_csv(index=False).encode("utf-8")
        filename = f"phids_batch_{job_id}.csv"
        media_type = "text/csv"
    elif format == "tex_table":
        latex: str = df.to_latex(index=False, float_format="%.2f")
        data = latex.encode("utf-8")
        filename = f"phids_batch_{job_id}_table.tex"
        media_type = "text/plain"
    elif format == "tex_tikz":
        # Build simplified export rows from aggregate mean and survival series.
        rows_agg: list[dict[str, Any]] = []
        ticks = aggregate.get("ticks", [])
        flora_mean = aggregate.get("flora_population_mean", [])
        pred_mean = aggregate.get("predator_population_mean", [])
        survival = aggregate.get("survival_probability_curve", [])
        for i, t in enumerate(ticks):
            rows_agg.append(
                {
                    "tick": t,
                    "plant_pop_by_species": {0: flora_mean[i] if i < len(flora_mean) else 0},
                    "swarm_pop_by_species": {0: pred_mean[i] if i < len(pred_mean) else 0},
                    "survival_probability": float(survival[i]) if i < len(survival) else 0.0,
                }
            )
        normalized_chart_type = "survival_probability" if chart_type == "survival" else chart_type
        tikz = generate_tikz_str(
            rows_agg,
            normalized_chart_type,
            title=title,
            x_label=x_label,
            y_label=y_label,
        )
        data = tikz.encode("utf-8")
        filename = f"phids_batch_{job_id}.tex"
        media_type = "text/plain"
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown format '{format}'. Use csv, tex_table, or tex_tikz.",
        )

    logger.info("Batch export job=%s format=%s size=%d", job_id, format, len(data))
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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
                payload = _build_live_dashboard_payload(loop)
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

    payload = (
        _build_live_cell_details(_sim_loop, x, y)
        if _sim_loop is not None
        else _build_preview_cell_details(x, y)
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
# Scenario import / export / load-draft
# ---------------------------------------------------------------------------


@app.get("/api/scenario/export", summary="Export draft as JSON")
async def scenario_export() -> Response:
    """Serialise the draft state as a downloadable JSON file.

    Returns:
        Response: JSON file download response.
    """
    draft = get_draft()
    try:
        config = draft.build_sim_config()
        data = json.dumps(config.model_dump(), indent=2)
    except (ValueError, AttributeError) as exc:
        logger.warning("Scenario export failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.info("Draft scenario exported (scenario_name=%s)", draft.scenario_name)
    return Response(
        content=data,
        media_type="application/json",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{draft.scenario_name.replace(" ", "_")}.json"'
            )
        },
    )


@app.post("/api/scenario/import", summary="Import scenario from JSON file")
async def scenario_import(file: UploadFile = File(...)) -> JSONResponse:
    """Parse an uploaded JSON scenario and replace the draft.

    Args:
        file: Uploaded ``.json`` file containing a ``SimulationConfig``
            serialisation.

    Returns:
        JSONResponse: Confirmation with imported scenario grid dimensions.

    Raises:
        HTTPException: 422 if the JSON does not validate against
            :class:`~phids.api.schemas.SimulationConfig`.
    """
    raw = await file.read()
    try:
        payload = json.loads(raw)
        config = SimulationConfig.model_validate(payload)
    except Exception as exc:
        logger.warning("Scenario import failed for file %s: %s", file.filename, exc)
        raise HTTPException(status_code=422, detail=f"Invalid scenario JSON: {exc}") from exc

    # Reconstruct trigger rules from the imported flora triggers
    imported_trigger_rules: list[TriggerRule] = []
    imported_substances: list[SubstanceDefinition] = []
    seen_substance_ids: set[int] = set()
    for flora_spec in config.flora_species:
        for trig in flora_spec.triggers:
            imported_trigger_rules.append(
                TriggerRule(
                    flora_species_id=flora_spec.species_id,
                    predator_species_id=trig.predator_species_id,
                    substance_id=trig.substance_id,
                    min_predator_population=trig.min_predator_population,
                    activation_condition=(
                        trig.activation_condition.model_dump(mode="json")
                        if trig.activation_condition is not None
                        else None
                    ),
                )
            )
            if trig.substance_id not in seen_substance_ids:
                seen_substance_ids.add(trig.substance_id)
                imported_substances.append(
                    SubstanceDefinition(
                        substance_id=trig.substance_id,
                        name=f"Substance {trig.substance_id}",
                        is_toxin=trig.is_toxin,
                        lethal=trig.lethal,
                        repellent=trig.repellent,
                        synthesis_duration=trig.synthesis_duration,
                        aftereffect_ticks=trig.aftereffect_ticks,
                        lethality_rate=trig.lethality_rate,
                        repellent_walk_ticks=trig.repellent_walk_ticks,
                        energy_cost_per_tick=trig.energy_cost_per_tick,
                        irreversible=trig.irreversible,
                        precursor_signal_id=(
                            trig.precursor_signal_ids[0]
                            if len(trig.precursor_signal_ids) == 1
                            else trig.precursor_signal_id
                        ),
                        min_predator_population=trig.min_predator_population,
                    )
                )

    new_draft = DraftState(
        scenario_name=(file.filename or "imported").replace(".json", ""),
        grid_width=config.grid_width,
        grid_height=config.grid_height,
        max_ticks=config.max_ticks,
        tick_rate_hz=config.tick_rate_hz,
        wind_x=config.wind_x,
        wind_y=config.wind_y,
        num_signals=config.num_signals,
        num_toxins=config.num_toxins,
        mycorrhizal_inter_species=config.mycorrhizal_inter_species,
        mycorrhizal_connection_cost=config.mycorrhizal_connection_cost,
        mycorrhizal_growth_interval_ticks=config.mycorrhizal_growth_interval_ticks,
        mycorrhizal_signal_velocity=config.mycorrhizal_signal_velocity,
        flora_species=list(config.flora_species),
        predator_species=list(config.predator_species),
        diet_matrix=[list(row) for row in config.diet_matrix.rows],
        trigger_rules=imported_trigger_rules,
        substance_definitions=imported_substances,
        initial_plants=[
            PlacedPlant(species_id=p.species_id, x=p.x, y=p.y, energy=p.energy)
            for p in config.initial_plants
        ],
        initial_swarms=[
            PlacedSwarm(
                species_id=s.species_id,
                x=s.x,
                y=s.y,
                population=s.population,
                energy=s.energy,
            )
            for s in config.initial_swarms
        ],
    )
    set_draft(new_draft)
    logger.info(
        "Scenario imported into draft (file=%s, grid=%dx%d, flora=%d, predators=%d)",
        file.filename,
        config.grid_width,
        config.grid_height,
        len(config.flora_species),
        len(config.predator_species),
    )
    return JSONResponse(
        content={
            "message": "Scenario imported.",
            "grid_width": config.grid_width,
            "grid_height": config.grid_height,
        }
    )


@app.post(
    "/api/scenario/load-draft",
    response_class=HTMLResponse,
    summary="Load draft config into simulation engine",
)
async def scenario_load_draft(request: Request) -> Any:
    """Commit the current draft to the simulation engine.

    Equivalent to ``POST /api/scenario/load`` but uses the server-side
    draft rather than a request body.

    Returns:
        HTMLResponse: Updated status badge HTML fragment.

    Raises:
        HTTPException: 400 if draft is invalid or missing required species.
    """
    global _sim_loop, _sim_task  # noqa: PLW0603

    draft = get_draft()
    try:
        config = draft.build_sim_config()
    except (ValueError, Exception) as exc:
        logger.warning("Draft load into simulation failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if _sim_task is not None and not _sim_task.done():
        logger.info("Cancelling existing background simulation task before loading draft")
        _sim_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _sim_task

    _sim_loop = SimulationLoop(config)
    _sim_task = None
    _set_simulation_substance_names(config, draft=draft)
    logger.info(
        "Draft loaded: %dx%d grid, %d flora, %d predators",
        config.grid_width,
        config.grid_height,
        len(config.flora_species),
        len(config.predator_species),
    )
    return HTMLResponse(content=_render_status_badge_html())


app.include_router(config_router)
app.include_router(telemetry_router)
app.include_router(ui_router)
