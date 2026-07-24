# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Draft-state mutation module for substance definitions.

Provides pure functions to add, update, and remove substance definitions within the draft.
Removing a substance correctly updates remaining definitions and purges associated trigger rules
to maintain state integrity.
"""

from __future__ import annotations

import dataclasses
import logging
from copy import deepcopy

from phids.api.services.draft.helpers import find_substance_index, is_truthy_flag
from phids.api.ui_state import DraftState, SubstanceDefinition, TriggerRule, _remap_condition_references

logger = logging.getLogger(__name__)


def add_substance(
    draft: DraftState,
    *,
    name: str,
    is_toxin: str | bool = False,
    lethal: str | bool = False,
    repellent: str | bool = False,
    synthesis_duration: int = 3,
    aftereffect_ticks: int = 0,
    lethality_rate: float = 0.0,
    repellent_walk_ticks: int = 3,
    energy_cost_per_tick: float = 1.0,
    irreversible: str | bool = False,
) -> SubstanceDefinition:
    """Append one substance definition to the bounded registry.

    Args:
        draft: Draft state mutated in place.
        name: Operator-facing substance label.
        is_toxin: Substance class toggle.
        lethal: Lethal-toxin toggle.
        repellent: Repellent-toxin toggle.
        synthesis_duration: Requested synthesis latency.
        aftereffect_ticks: Requested persistence duration after deactivation.
        lethality_rate: Requested lethal damage rate.
        repellent_walk_ticks: Requested repel walk duration.
        energy_cost_per_tick: Requested per-tick maintenance cost.
        irreversible: Irreversible activation toggle.

    Returns:
        The created ``SubstanceDefinition`` entry.

    Raises:
        ValueError: The Rule of 16 ceiling for substances has been reached.

    """
    if len(draft.substance_definitions) >= 16:
        raise ValueError("Rule of 16: maximum substances reached.")

    definition = SubstanceDefinition(
        substance_id=len(draft.substance_definitions),
        name=name,
        is_toxin=is_truthy_flag(is_toxin),
        lethal=is_truthy_flag(lethal),
        repellent=is_truthy_flag(repellent),
        synthesis_duration=max(1, synthesis_duration),
        aftereffect_ticks=max(0, aftereffect_ticks),
        lethality_rate=max(0.0, lethality_rate),
        repellent_walk_ticks=max(0, repellent_walk_ticks),
        energy_cost_per_tick=max(0.0, energy_cost_per_tick),
        irreversible=is_truthy_flag(irreversible),
    )
    draft.substance_definitions.append(definition)
    logger.debug(
        "Draft substance added (substance_id=%d, name=%s, is_toxin=%s, total_substances=%d)",
        definition.substance_id,
        definition.name,
        definition.is_toxin,
        len(draft.substance_definitions),
    )
    return definition


def update_substance(
    draft: DraftState,
    substance_id: int,
    *,
    name: str | None = None,
    type_label: str | None = None,
    synthesis_duration: int | None = None,
    aftereffect_ticks: int | None = None,
    lethality_rate: float | None = None,
    repellent_walk_ticks: int | None = None,
    energy_cost_per_tick: float | None = None,
    irreversible: str | bool | None = None,
) -> SubstanceDefinition:
    """Patch one substance definition in place.

    Args:
        draft: Draft state mutated in place.
        substance_id: Substance identifier to modify.
        name: Optional replacement name.
        type_label: Optional UI type label controlling toxin flags.
        synthesis_duration: Optional replacement synthesis latency.
        aftereffect_ticks: Optional replacement persistence duration.
        lethality_rate: Optional replacement lethal damage rate.
        repellent_walk_ticks: Optional replacement repel walk duration.
        energy_cost_per_tick: Optional replacement maintenance cost.
        irreversible: Optional replacement irreversible flag.

    Returns:
        The mutated ``SubstanceDefinition`` entry.

    Raises:
        ValueError: No substance with the requested identifier exists.

    """
    idx = find_substance_index(draft, substance_id)
    if idx is None:
        raise ValueError(f"Substance {substance_id} not found.")

    definition = draft.substance_definitions[idx]
    if name is not None:
        definition.name = name
    if type_label is not None:
        definition.is_toxin = type_label in (
            "Lethal Toxin",
            "Repellent Toxin",
            "Repelling Toxin",
            "Toxin",
        )
        definition.lethal = type_label == "Lethal Toxin"
        definition.repellent = type_label in ("Repellent Toxin", "Repelling Toxin")
    if synthesis_duration is not None:
        definition.synthesis_duration = max(1, synthesis_duration)
    if aftereffect_ticks is not None:
        definition.aftereffect_ticks = max(0, aftereffect_ticks)
    if lethality_rate is not None:
        definition.lethality_rate = max(0.0, lethality_rate)
    if repellent_walk_ticks is not None:
        definition.repellent_walk_ticks = max(0, repellent_walk_ticks)
    if energy_cost_per_tick is not None:
        definition.energy_cost_per_tick = max(0.0, energy_cost_per_tick)
    if irreversible is not None:
        definition.irreversible = is_truthy_flag(irreversible)

    logger.debug(
        "Draft substance updated (substance_id=%d, name=%s, is_toxin=%s)",
        substance_id,
        definition.name,
        definition.is_toxin,
    )
    return definition


def remove_substance(draft: DraftState, substance_id: int) -> None:
    """Remove one substance definition and compact all dependent references.

    Args:
        draft: Draft state mutated in place.
        substance_id: Substance identifier to remove.

    Raises:
        ValueError: No substance with the requested identifier exists.

    """
    idx = find_substance_index(draft, substance_id)
    if idx is None:
        raise ValueError(f"Substance {substance_id} not found.")

    del draft.substance_definitions[idx]
    for new_id, definition in enumerate(draft.substance_definitions):
        definition.substance_id = new_id

    remaining_rules: list[TriggerRule] = []
    removed_rules = 0
    for rule in draft.trigger_rules:
        if rule.substance_id == substance_id:
            removed_rules += 1
            continue
        new_rule = dataclasses.replace(rule)
        if new_rule.substance_id > substance_id:
            new_rule.substance_id -= 1
        new_rule.activation_condition = _remap_condition_references(
            deepcopy(new_rule.activation_condition),
            removed_substance_id=substance_id,
        )
        remaining_rules.append(new_rule)
    draft.trigger_rules = remaining_rules

    logger.debug(
        (
            "Draft substance removed (substance_id=%d, total_substances=%d, "
            "remaining_trigger_rules=%d, removed_trigger_rules=%d)"
        ),
        substance_id,
        len(draft.substance_definitions),
        len(draft.trigger_rules),
        removed_rules,
    )
