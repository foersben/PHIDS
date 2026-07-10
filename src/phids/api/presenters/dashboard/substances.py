from __future__ import annotations

from typing import TYPE_CHECKING

from phids.api.presenters.dashboard.helpers import _default_substance_name, _describe_activation_condition

if TYPE_CHECKING:
    from phids.engine.components.substances import SubstanceComponent


def _is_live_substance_visible(substance: SubstanceComponent) -> bool:
    return (
        substance.active
        or substance.synthesis_remaining > 0
        or substance.aftereffect_remaining_ticks > 0
        or substance.triggered_this_tick
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
    if snapshot_only:
        return ("field_snapshot", "visible field residue")
    if synthesis_remaining > 0 and not active:
        return ("synthesizing", "synthesizing")
    if active and triggered_this_tick:
        return ("triggered", "triggered")
    if active and not is_toxin and aftereffect_remaining_ticks > 0:
        return ("aftereffect", "aftereffect")
    if not active and triggered_this_tick:
        return ("triggered", "triggered")
    return ("active", "active") if active else ("configured", "quiescent")


def _serialize_live_substance(
    substance: SubstanceComponent,
    *,
    herbivore_names: dict[int, str],
    substance_names: dict[int, str],
) -> dict[str, object]:
    trigger_herbivore_name = None
    if substance.trigger_herbivore_species_id >= 0:
        trigger_herbivore_name = herbivore_names.get(
            substance.trigger_herbivore_species_id,
            f"Herbivore {substance.trigger_herbivore_species_id}",
        )
    activation_condition_summary = _describe_activation_condition(
        substance.activation_condition,
        herbivore_names=herbivore_names,
        substance_names=substance_names,
    )
    state, state_label = _live_substance_state_payload(
        is_toxin=bool(substance.is_toxin),
        active=bool(substance.active),
        triggered_this_tick=bool(substance.triggered_this_tick),
        synthesis_remaining=int(substance.synthesis_remaining),
        aftereffect_remaining_ticks=int(substance.aftereffect_remaining_ticks),
        snapshot_only=False,
    )

    return {
        "substance_id": substance.substance_id,
        "name": substance_names.get(
            substance.substance_id,
            _default_substance_name(substance.substance_id, is_toxin=substance.is_toxin),
        ),
        "kind": "toxin" if substance.is_toxin else "signal",
        "state": state,
        "state_label": state_label,
        "active": bool(substance.active),
        "trigger_herbivore_name": trigger_herbivore_name,
        "activation_condition_summary": activation_condition_summary,
        "lethality_rate": float(substance.lethality_rate),
        "repellent": bool(substance.repellent),
        "synthesis_ticks": int(substance.synthesis_duration),
        "synthesis_remaining": int(substance.synthesis_remaining),
        "aftereffect_duration": int(substance.aftereffect_ticks),
        "aftereffect_remaining_ticks": int(substance.aftereffect_remaining_ticks),
        "snapshot_only": False,
        "triggered_this_tick": bool(substance.triggered_this_tick),
        "lethal": bool(substance.lethal),
        "repellent_walk_ticks": int(substance.repellent_walk_ticks),
        "trigger_herbivore_species_id": int(substance.trigger_herbivore_species_id),
        "trigger_min_herbivore_population": int(substance.trigger_min_herbivore_population),
        "activation_condition": substance.activation_condition,
    }


def _fallback_live_substance_payload(
    substance_id: int,
    *,
    is_toxin: bool,
    substance_names: dict[int, str],
) -> dict[str, object]:
    return {
        "substance_id": substance_id,
        "name": substance_names.get(
            substance_id,
            _default_substance_name(substance_id, is_toxin=is_toxin),
        ),
        "kind": "toxin" if is_toxin else "signal",
        "state": "field_snapshot",
        "state_label": "visible field residue",
        "active": False,
        "trigger_herbivore_name": None,
        "activation_condition_summary": "unconditional",
        "lethality_rate": 0.0,
        "repellent": False,
        "synthesis_ticks": 0,
        "synthesis_remaining": 0,
        "aftereffect_duration": 0,
        "aftereffect_remaining_ticks": 0,
        "snapshot_only": True,
        "triggered_this_tick": False,
        "lethal": False,
        "repellent_walk_ticks": 0,
        "trigger_herbivore_species_id": -1,
        "trigger_min_herbivore_population": 0,
        "activation_condition": None,
    }
