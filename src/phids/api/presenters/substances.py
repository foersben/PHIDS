"""Substance state presentation layer.

This module encapsulates the five-state machine presentation logic for chemical substances
(signals and toxins) managed by the ECS runtime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from phids.api.presenters.utils import _default_substance_name, _describe_activation_condition

if TYPE_CHECKING:
    from phids.engine.components.substances import SubstanceComponent


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
