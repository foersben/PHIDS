"""Dashboard presenter for mycorrhizal root network links.

Defines payloads and utility functions to build and filter root communication links
between Manhattan-adjacent plant entities in both draft and live simulation modes.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, TypedDict

from fastapi import HTTPException

if TYPE_CHECKING:
    from phids.engine.components.substances import SubstanceComponent

if TYPE_CHECKING:
    from phids.api.ui_state import DraftState
    from phids.engine.loop import SimulationLoop


class _MycorrhizalLinkPayload(TypedDict, total=False):
    """Serializable link payload used by draft and live mycorrhizal helpers."""

    plant_index_a: int
    plant_index_b: int
    entity_id_a: int
    entity_id_b: int
    x1: int
    y1: int
    x2: int
    y2: int
    inter_species: bool


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


def _coerce_float(value: object, *, default: float = 0.0) -> float:
    """Coerce an arbitrary object to ``float``, returning ``default`` on failure."""
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
    condition: Mapping[str, object] | None,
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
        min_conc = _coerce_float(condition.get("min_concentration", 0.01), default=0.01)
        signal_label = (
            substance_names.get(signal_id, _default_substance_name(signal_id, is_toxin=False))
            if substance_names is not None
            else _default_substance_name(signal_id, is_toxin=False)
        )
        return f"{signal_label} concentration ≥ {min_conc:.2f}"

    raw_children = condition.get("conditions", [])
    if not isinstance(raw_children, list):
        return "unconditional"
    children = [child for child in raw_children if isinstance(child, Mapping)]
    joiner = " AND " if kind == "all_of" else " OR "
    if not children:
        return "unconditional"
    rendered = [
        _describe_activation_condition(child, herbivore_names=herbivore_names, substance_names=substance_names)
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
        HTTPException: HTTP 404 if the coordinates fall outside ``[0, width) x [0, height)``.

    """
    if not (0 <= x < width and 0 <= y < height):
        raise HTTPException(
            status_code=404,
            detail=f"Cell ({x}, {y}) is outside the current {width}x{height} grid.",
        )


# ---------------------------------------------------------------------------
# Mycorrhizal network link builders
# ---------------------------------------------------------------------------


def build_draft_mycorrhizal_links(draft: DraftState) -> list[_MycorrhizalLinkPayload]:
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
    links: list[_MycorrhizalLinkPayload] = []
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


def _build_live_mycorrhizal_links(loop: SimulationLoop) -> list[_MycorrhizalLinkPayload]:
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
    links: list[_MycorrhizalLinkPayload] = []
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


def _links_touching_cell(links: list[_MycorrhizalLinkPayload], x: int, y: int) -> list[_MycorrhizalLinkPayload]:
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
    return [link for link in links if (link["x1"] == x and link["y1"] == y) or (link["x2"] == x and link["y2"] == y)]


# ---------------------------------------------------------------------------
# Substance state helpers
# ---------------------------------------------------------------------------


def _is_live_substance_visible(substance: SubstanceComponent) -> bool:
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
    substance: SubstanceComponent,
    *,
    herbivore_names: dict[int, str],
    substance_names: dict[int, str],
) -> dict[str, object]:
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
) -> dict[str, object]:
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
        "name": substance_names.get(substance_id, _default_substance_name(substance_id, is_toxin=is_toxin)),
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
