"""Dashboard presenter: ECS-to-JSON serialisation for live and draft grid payloads.

This module implements the payload assembly layer that bridges the PHIDS simulation runtime —
represented by a live :class:`~phids.engine.loop.SimulationLoop` or a server-side
:class:`~phids.api.ui_state.DraftState` — and the structured JSON dictionaries consumed by the
browser canvas renderer and the HTMX tooltip system.  The three public functions
:func:`build_live_cell_details`, :func:`build_preview_cell_details`, and
:func:`build_live_dashboard_payload` collectively constitute the *presenter layer*, deliberately
isolating heavy data-transformation logic from the FastAPI route handlers that formerly owned it.

Architectural Rationale
-----------------------
In the original architecture, the functions ``_build_live_cell_details``,
``_build_preview_cell_details``, and ``_build_live_dashboard_payload`` resided in
``phids.api.main`` alongside HTTP wiring, middleware, and WebSocket orchestration.  This
co-location violated the single-responsibility principle: the HTTP layer should be concerned only
with request validation, lifecycle control, and transport — not with traversing ECS component
graphs or interpreting double-buffered environmental layers.  Relocating these functions to a
dedicated presenter package restores a clean boundary: the route handlers now pass well-typed
arguments to pure transformation functions, which are independently testable without spinning up
a FastAPI application.

Biological and Computational Semantics
--------------------------------------
The serialisation logic faithfully reflects the dual-representation architecture of PHIDS:

- **Discrete entity state** is sourced from :class:`~phids.engine.core.ecs.ECSWorld` via
  O(1) spatial hash lookups (``world.entities_at(x, y)``).  Per-plant substance components,
  mycorrhizal network topology, and swarm energy bookkeeping are all decoded from ECS components,
  preserving the data-oriented design invariant.
- **Continuous field state** is sourced from the current read buffer of
  :class:`~phids.engine.core.biotope.GridEnvironment` — specifically the ``signal_layers``,
  ``toxin_layers``, ``wind_vector_x``, and ``wind_vector_y`` NumPy arrays.  These fields encode
  diffused chemical plumes whose spatial extent arises from Gaussian diffusion kernels applied
  each tick.
- **Mycorrhizal network links** are serialised from live component connections or inferred from
  draft plant adjacency, enabling both runtime and pre-simulation overlay rendering.

Substance State Machine
-----------------------
The helper :func:`_live_substance_state_payload` encodes a five-state machine per substance:
``synthesizing`` → ``triggered`` → ``active`` / ``aftereffect`` → ``configured``.  The
``snapshot_only`` branch is reserved for grid cells where a non-zero field concentration is
observable but no owning plant entity is registered at that coordinate (i.e., the chemical plume
has diffused beyond the emitter's current position).

Dependency Injection
--------------------
All public functions accept ``substance_names: dict[int, str]`` as a keyword-only argument.
This replaces the former implicit dependency on the ``_sim_substance_names`` module-level global
in ``phids.api.main``, making the functions deterministically testable with arbitrary name
dictionaries and eliminating hidden coupling to mutable application state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import HTTPException

if TYPE_CHECKING:
    from phids.api.ui_state import DraftState, TriggerRule
    from phids.engine.loop import SimulationLoop


# ---------------------------------------------------------------------------
# Pure utility helpers (self-contained copies; no import from phids.api.main)
# ---------------------------------------------------------------------------


def _coerce_int(value: object, *, default: int = -1) -> int:
    """Coerce an arbitrary object to ``int``, returning ``default`` on failure.

    Args:
        value: The input value to coerce.  Accepted types are ``int``, ``float``, and ``str``.
            ``bool`` values are explicitly rejected to avoid silent misinterpretation of flag
            fields as integer counts.
        default: Fallback integer returned when coercion is not possible.

    Returns:
        Coerced integer, or ``default`` if the input cannot be converted.
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


def _default_substance_name(substance_id: int, *, is_toxin: bool) -> str:
    """Return a deterministic fallback display label for a substance identifier.

    The label encodes the biological classification (signal vs. toxin) and the integer
    identifier, ensuring operator-facing tooltips remain informative even when no explicit
    substance definition has been registered in the draft or live runtime.

    Args:
        substance_id: The integer substance channel index.
        is_toxin: Whether the substance occupies a toxin layer (``True``) or a signal layer
            (``False``).

    Returns:
        A human-readable label of the form ``"Toxin N"`` or ``"Signal N"``.
    """
    return f"{'Toxin' if is_toxin else 'Signal'} {substance_id}"


def _describe_activation_condition(
    condition: dict[str, Any] | None,
    *,
    herbivore_names: dict[int, str] | None = None,
    substance_names: dict[int, str] | None = None,
) -> str:
    """Render a concise human-readable summary of a nested activation-condition tree.

    Activation conditions follow a recursive tree schema with leaf kinds
    ``herbivore_presence``, ``substance_active``, and ``environmental_signal``, and
    combinator kinds ``all_of`` and ``any_of``.  The function traverses the tree
    depth-first and assembles a parenthesised natural-language description suitable
    for operator-facing tooltips and the trigger-rules configuration panel.

    Args:
        condition: A deserialized condition node dictionary, or ``None`` for
            unconditional triggering.
        herbivore_names: Optional mapping from herbivore species identifier to display
            name.  Used to resolve ``herbivore_presence`` leaf labels.
        substance_names: Optional mapping from substance identifier to display name.
            Used to resolve ``substance_active`` and ``environmental_signal`` leaf labels.

    Returns:
        A human-readable condition summary string.  Returns ``"unconditional"`` when
        ``condition`` is ``None`` or when a combinator node has no valid children.
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
            child, herbivore_names=herbivore_names, substance_names=substance_names
        )
        for child in children
    ]
    return f"({joiner.join(rendered)})"


def validate_cell_coordinates(x: int, y: int, width: int, height: int) -> None:
    """Validate that (x, y) lies within the configured grid bounds.

    This guard is applied at the entry point of both live and draft cell-detail
    functions to ensure that coordinate lookups against NumPy environmental layers
    and the ECS spatial hash never produce out-of-bounds array accesses.

    Args:
        x: Column index of the target cell.
        y: Row index of the target cell.
        width: Total grid width in cells.
        height: Total grid height in cells.

    Raises:
        HTTPException: HTTP 404 if the coordinates fall outside ``[0, width) × [0, height)``.
    """
    if not (0 <= x < width and 0 <= y < height):
        raise HTTPException(
            status_code=404,
            detail=f"Cell ({x}, {y}) is outside the current {width}x{height} grid.",
        )


# ---------------------------------------------------------------------------
# Mycorrhizal network link builders
# ---------------------------------------------------------------------------


def build_draft_mycorrhizal_links(draft: DraftState) -> list[dict[str, Any]]:
    """Infer potential mycorrhizal root links from adjacent draft plant placements.

    The mycorrhizal network in PHIDS is modelled as a graph of Manhattan-adjacent
    plant entities.  In draft mode, the live ECS world has not yet been instantiated,
    so adjacency is determined directly from the :attr:`~phids.api.ui_state.DraftState.initial_plants`
    placement list.  Two plants at Manhattan distance 1 are considered candidates for
    a root link; inter-species links are included only when
    :attr:`~phids.api.ui_state.DraftState.mycorrhizal_inter_species` is ``True``.

    Args:
        draft: The current server-side draft configuration.

    Returns:
        A list of link dictionaries, each containing ``plant_index_a``, ``plant_index_b``,
        ``x1``, ``y1``, ``x2``, ``y2``, and ``inter_species`` fields.
    """
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
    """Serialise the unique set of root links currently active in the live ECS world.

    Each plant entity in the :class:`~phids.engine.core.ecs.ECSWorld` maintains a
    ``mycorrhizal_connections`` set of neighbour entity identifiers.  This function
    iterates over all live :class:`~phids.engine.components.plant.PlantComponent`
    instances and emits one canonical link record per unordered pair, using a
    ``seen_pairs`` set to prevent duplicate serialisation.  The resulting list is
    consumed by the canvas overlay renderer to draw the belowground network topology.

    Args:
        loop: The active simulation loop whose ECS world is queried.

    Returns:
        A list of link dictionaries containing ``entity_id_a``, ``entity_id_b``,
        ``x1``, ``y1``, ``x2``, ``y2``, and ``inter_species`` fields.
    """
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
    """Filter a serialised link list to those whose endpoint coordinates include (x, y).

    This filter is applied when assembling the per-cell tooltip payload, ensuring that
    the mycorrhizal overlay shown for a specific cell reflects only the root links
    that are anchored at or terminate at that cell.

    Args:
        links: Serialised link records as produced by :func:`_build_live_mycorrhizal_links`
            or :func:`build_draft_mycorrhizal_links`.
        x: Target column index.
        y: Target row index.

    Returns:
        The subset of ``links`` where either endpoint matches ``(x, y)``.
    """
    return [
        link
        for link in links
        if (int(link["x1"]) == x and int(link["y1"]) == y)
        or (int(link["x2"]) == x and int(link["y2"]) == y)
    ]


# ---------------------------------------------------------------------------
# Substance state helpers
# ---------------------------------------------------------------------------


def _is_live_substance_visible(substance: Any) -> bool:
    """Determine whether a live substance component warrants serialisation in UI payloads.

    A substance is considered visible — and therefore included in tooltip and dashboard
    payloads — when it occupies any state other than quiescent configured: active emission,
    triggered initiation, ongoing synthesis, or a lingering aftereffect phase.

    Args:
        substance: A live :class:`~phids.engine.components.substances.SubstanceComponent`
            instance.

    Returns:
        ``True`` if the substance is in a non-quiescent state; ``False`` otherwise.
    """
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
    """Encode the current runtime state of a substance as a (state_key, state_label) pair.

    The function implements a priority-ordered mapping from raw boolean/counter fields onto
    one of five mutually exclusive UI state tokens: ``"field_snapshot"``, ``"synthesizing"``,
    ``"triggered"``, ``"aftereffect"``, and ``"active"`` / ``"configured"``.  This mapping
    drives both the tooltip badge colours and the legend entries in the browser canvas.

    The priority ordering reflects the biological significance of each state: a substance
    in its synthesis window has not yet reached ecological effect; a triggered substance
    is undergoing initial response to a detected threat; an aftereffect-phase signal
    represents the lingering systemic acquired resistance following active emission.

    Args:
        is_toxin: Whether the substance occupies a toxin channel (``True``) or a signal
            channel (``False``).
        active: Whether the substance is currently emitting into the environment.
        triggered_this_tick: Whether the synthesis sequence was initiated in the current tick.
        synthesis_remaining: Number of ticks remaining in the synthesis phase.
        aftereffect_remaining_ticks: Number of ticks remaining in the post-emission aftereffect
            phase (signals only).
        snapshot_only: If ``True``, the substance is present only as a field residue without
            an owning entity at the queried cell; the returned state is ``"field_snapshot"``.

    Returns:
        A two-tuple ``(state_key, state_label)`` where ``state_key`` is a machine-readable
        token and ``state_label`` is a human-readable UI description.
    """
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
    herbivore_names: dict[int, str],
    substance_names: dict[int, str],
) -> dict[str, Any]:
    """Serialise a single live runtime substance component into a dashboard-ready dictionary.

    The output dictionary encodes the full biological and operational state of the substance
    for operator inspection: identifier, display name, classification (signal or toxin),
    trigger predicate, current runtime state, and quantitative parameters governing lethality,
    repellency, and temporal dynamics.  The ``activation_condition_summary`` field renders the
    nested condition tree as a human-readable string via :func:`_describe_activation_condition`.

    Args:
        substance: A live :class:`~phids.engine.components.substances.SubstanceComponent`
            instance.
        herbivore_names: Mapping from herbivore species identifier to display name, used to
            resolve the ``trigger_herbivore_name`` field.
        substance_names: Mapping from substance identifier to display name, used to resolve
            the ``name`` and ``activation_condition_summary`` fields.

    Returns:
        A dictionary conforming to the substance payload schema expected by the browser
        tooltip and dashboard components.
    """
    state, state_label = _live_substance_state_payload(
        is_toxin=bool(substance.is_toxin),
        active=bool(substance.active),
        triggered_this_tick=bool(substance.triggered_this_tick),
        synthesis_remaining=int(substance.synthesis_remaining),
        aftereffect_remaining_ticks=int(substance.aftereffect_remaining_ticks),
    )
    return {
        "substance_id": substance.substance_id,
        "name": substance_names.get(
            substance.substance_id,
            _default_substance_name(substance.substance_id, is_toxin=bool(substance.is_toxin)),
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
        "trigger_herbivore_species_id": substance.trigger_herbivore_species_id,
        "trigger_herbivore_name": herbivore_names.get(
            substance.trigger_herbivore_species_id,
            f"Herbivore {substance.trigger_herbivore_species_id}",
        )
        if substance.trigger_herbivore_species_id >= 0
        else None,
        "trigger_min_herbivore_population": substance.trigger_min_herbivore_population,
        "activation_condition": substance.activation_condition,
        "activation_condition_summary": _describe_activation_condition(
            substance.activation_condition,
            herbivore_names=herbivore_names,
            substance_names=substance_names,
        ),
    }


def _fallback_live_substance_payload(
    substance_id: int,
    *,
    is_toxin: bool,
    substance_names: dict[int, str],
) -> dict[str, Any]:
    """Return a snapshot-only fallback payload for a diffused field residue without a live owner.

    When the environmental signal or toxin layer at a given cell is non-zero but no live
    :class:`~phids.engine.components.substances.SubstanceComponent` is registered at that
    coordinate, the chemical presence is attributed to Gaussian diffusion from a nearby emitter.
    This fallback preserves the operator's ability to inspect field concentration without
    fabricating misleading entity-level data.

    Args:
        substance_id: Integer channel index of the substance.
        is_toxin: Whether the substance occupies a toxin layer (``True``) or a signal layer
            (``False``).
        substance_names: Mapping from substance identifier to display name.

    Returns:
        A substance payload dictionary in the ``"field_snapshot"`` state with all dynamic
        fields set to zero or ``False``.
    """
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
        "name": substance_names.get(
            substance_id, _default_substance_name(substance_id, is_toxin=is_toxin)
        ),
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
        "trigger_herbivore_species_id": -1,
        "trigger_herbivore_name": None,
        "trigger_min_herbivore_population": 0,
        "activation_condition": None,
        "activation_condition_summary": "visible on rendered live snapshot",
    }


# ---------------------------------------------------------------------------
# Public presenter functions
# ---------------------------------------------------------------------------


def build_live_cell_details(
    loop: SimulationLoop,
    x: int,
    y: int,
    *,
    substance_names: dict[int, str],
) -> dict[str, Any]:
    """Assemble a rich tooltip payload for a single live-simulation grid cell.

    This function traverses the ECS world and double-buffered environmental layers for cell
    ``(x, y)``, collecting all plant entities (with their owned substance components and
    mycorrhizal network neighbours), swarm entities (with energy and repellency state), and
    per-channel signal and toxin concentrations.  The result is a structured dictionary
    consumed by the HTMX tooltip partial rendered when the operator hovers over a canvas cell.

    Entity lookups are performed via O(1) spatial hash queries (``world.entities_at(x, y)``),
    preserving the architectural constraint against O(N²) distance scans.  Environmental field
    values are read directly from the NumPy read buffer of
    :class:`~phids.engine.core.biotope.GridEnvironment`.

    Args:
        loop: The active :class:`~phids.engine.loop.SimulationLoop` whose ECS world and
            environment layers are queried.
        x: Column index of the target cell.
        y: Row index of the target cell.
        substance_names: Mapping from substance identifier to display name.  Injected by the
            caller to avoid implicit dependency on module-level mutable state.

    Returns:
        A dictionary with keys ``mode``, ``tick``, ``x``, ``y``, ``grid_width``,
        ``grid_height``, ``flow_field``, ``wind``, ``signal_peak``, ``toxin_peak``,
        ``signal_concentrations``, ``toxin_concentrations``, ``mycorrhiza``,
        ``plants``, and ``swarms``.

    Raises:
        HTTPException: HTTP 404 if ``(x, y)`` lies outside the configured grid bounds.
    """
    from phids.engine.components.plant import PlantComponent
    from phids.engine.components.substances import SubstanceComponent
    from phids.engine.components.swarm import SwarmComponent

    env = loop.env
    world = loop.world
    validate_cell_coordinates(x, y, env.width, env.height)

    flora_names = {species.species_id: species.name for species in loop.config.flora_species}
    herbivore_names = {
        species.species_id: species.name for species in loop.config.herbivore_species
    }

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
                    herbivore_names=herbivore_names,
                    substance_names=substance_names,
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
                    _fallback_live_substance_payload(
                        signal_id, is_toxin=False, substance_names=substance_names
                    )
                )
                visible_keys.add(substance_key)
            for toxin_id in range(env.num_toxins):
                if float(env.toxin_layers[toxin_id, plant.x, plant.y]) <= 0.0:
                    continue
                substance_key = (toxin_id, True)
                if substance_key in visible_keys:
                    continue
                visible_substances.append(
                    _fallback_live_substance_payload(
                        toxin_id, is_toxin=True, substance_names=substance_names
                    )
                )
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
                    "name": herbivore_names.get(swarm.species_id, f"Herbivore {swarm.species_id}"),
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
            "name": substance_names.get(
                signal_id, _default_substance_name(signal_id, is_toxin=False)
            ),
            "value": float(env.signal_layers[signal_id, x, y]),
        }
        for signal_id in range(env.num_signals)
        if float(env.signal_layers[signal_id, x, y]) > 0.0
    ]
    toxin_concentrations = [
        {
            "substance_id": toxin_id,
            "name": substance_names.get(toxin_id, _default_substance_name(toxin_id, is_toxin=True)),
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


def build_preview_cell_details(
    x: int,
    y: int,
    *,
    draft: DraftState,
    substance_names: dict[int, str] | None = None,
) -> dict[str, Any]:
    """Assemble a tooltip payload for a single draft (pre-simulation) grid cell.

    When no live simulation is running, the operator-facing canvas displays the draft
    placement configuration.  This function resolves all plants, swarms, and configured
    trigger rules at cell ``(x, y)`` from the provided :class:`~phids.api.ui_state.DraftState`,
    including potential mycorrhizal root links inferred from adjacent plant positions.

    The returned payload mirrors the structural contract of :func:`build_live_cell_details`
    to allow the browser tooltip component to render both modes with a single template.

    Args:
        x: Column index of the target cell.
        y: Row index of the target cell.
        draft: The server-side draft configuration to query.  Must be provided explicitly
            to decouple this function from module-level singleton state.
        substance_names: Optional mapping from substance identifier to display name.
            If ``None``, substance names are resolved exclusively from
            ``draft.substance_definitions``.

    Returns:
        A dictionary with keys ``mode`` (``"draft"``), ``tick`` (``None``), ``x``, ``y``,
        ``grid_width``, ``grid_height``, ``flow_field`` (``None``), ``wind``,
        ``signal_peak``, ``toxin_peak``, ``signal_concentrations``, ``toxin_concentrations``,
        ``mycorrhiza``, ``plants``, and ``swarms``.

    Raises:
        HTTPException: HTTP 404 if ``(x, y)`` lies outside the draft grid bounds.
    """
    validate_cell_coordinates(x, y, draft.grid_width, draft.grid_height)

    flora_names = {
        getattr(species, "species_id", index): getattr(species, "name", f"Flora {index}")
        for index, species in enumerate(draft.flora_species)
    }
    herbivore_names = {
        getattr(species, "species_id", index): getattr(species, "name", f"Herbivore {index}")
        for index, species in enumerate(draft.herbivore_species)
    }
    substances = {definition.substance_id: definition for definition in draft.substance_definitions}
    # Build effective substance_names from draft definitions when no explicit mapping is provided.
    effective_substance_names: dict[int, str] = (
        substance_names
        if substance_names is not None
        else {
            definition.substance_id: definition.name for definition in draft.substance_definitions
        }
    )

    rules_by_flora: dict[int, list[TriggerRule]] = {}
    for rule in draft.trigger_rules:
        rules_by_flora.setdefault(rule.flora_species_id, []).append(rule)

    preview_links = build_draft_mycorrhizal_links(draft)
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
                        "herbivore_species_id": rule.herbivore_species_id,
                        "herbivore_name": herbivore_names.get(
                            rule.herbivore_species_id,
                            f"Herbivore {rule.herbivore_species_id}",
                        ),
                        "min_herbivore_population": rule.min_herbivore_population,
                        "activation_condition": rule.activation_condition,
                        "activation_condition_summary": _describe_activation_condition(
                            rule.activation_condition,
                            herbivore_names=herbivore_names,
                            substance_names=effective_substance_names,
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
            "name": herbivore_names.get(swarm.species_id, f"Herbivore {swarm.species_id}"),
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


def build_live_dashboard_payload(
    loop: SimulationLoop,
    *,
    substance_names: dict[int, str],
) -> dict[str, Any]:
    """Assemble the full JSON payload streamed to the browser canvas over the UI WebSocket.

    This function constructs the authoritative rendering payload consumed by
    ``/ws/ui/stream``.  It collects and serialises:

    - Per-species plant energy layers from the double-buffered
      :class:`~phids.engine.core.biotope.GridEnvironment`.
    - All live plant entities with their positions, energy, mycorrhizal connection counts,
      and active substance channel identifiers.
    - All live swarm entities with their positions, population, energy state, repellency, and
      local toxin exposure.
    - Signal and toxin field overlays (maximum projection across channels).
    - Mycorrhizal network links as computed by :func:`_build_live_mycorrhizal_links`.
    - Full flora species catalogue with per-species extinction flags, enabling the legend
      to enumerate extinct species without repainting their absent energy layers.
    - Simulation lifecycle state (``tick``, ``terminated``, ``running``, ``paused``).

    The distinction between ``species_energy`` (extant species only) and ``all_flora_species``
    (full configured catalogue with ``extinct`` flags) is a deliberate design invariant: the
    canvas renderer must not composite extinct species layers onto the viewport, while the
    operator-facing legend must retain full ecological history for interpretability.

    Args:
        loop: The active :class:`~phids.engine.loop.SimulationLoop` whose ECS world and
            environment layers are serialised.
        substance_names: Mapping from substance identifier to display name.  Injected by the
            caller to eliminate implicit dependency on module-level mutable state.

    Returns:
        A dictionary conforming to the full canvas payload schema, including keys
        ``tick``, ``grid_width``, ``grid_height``, ``max_energy``, ``species_energy``,
        ``all_flora_species``, ``signal_overlay``, ``toxin_overlay``, ``max_signal``,
        ``max_toxin``, ``plants``, ``mycorrhizal_links``, ``swarms``, ``terminated``,
        ``termination_reason``, ``running``, and ``paused``.
    """
    from phids.engine.components.plant import PlantComponent
    from phids.engine.components.substances import SubstanceComponent
    from phids.engine.components.swarm import SwarmComponent

    env = loop.env
    world = loop.world
    max_e = float(env.plant_energy_layer.max()) or 1.0
    signal_overlay = env.signal_layers.max(axis=0) if env.num_signals > 0 else None
    toxin_overlay = env.toxin_layers.max(axis=0) if env.num_toxins > 0 else None

    flora_names = {species.species_id: species.name for species in loop.config.flora_species}
    herbivore_names = {
        species.species_id: species.name for species in loop.config.herbivore_species
    }

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
                "name": herbivore_names.get(swarm.species_id, f"Herbivore {swarm.species_id}"),
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
