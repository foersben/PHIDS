# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Core trigger rule mutations."""

from __future__ import annotations

import logging
from copy import deepcopy
from typing import TYPE_CHECKING, Literal

from fastapi import HTTPException

from phids.api.ui_state.triggers import (
    ActivationConditionNode,
    TriggerRule,
)

if TYPE_CHECKING:
    from phids.api.ui_state.state import DraftState

logger = logging.getLogger(__name__)


def add_trigger_rule(
    draft: DraftState,
    flora_species_id: int,
    herbivore_species_id: int = 0,
    substance_id: int = 0,
    action_type: Literal["synthesize_substance", "resource_withdrawal"] = "synthesize_substance",
    apparent_nutrition_factor: float = 0.2,
    withdrawal_duration: int = 10,
    aftereffect_ticks: int = 10,
    min_herbivore_population: int = 5,
    activation_condition: ActivationConditionNode | None = None,
    initiator_type: Literal["herbivore_attack", "environmental_signal"] = "herbivore_attack",
    initiator_signal_id: int = 0,
    initiator_min_concentration: float = 0.01,
) -> None:
    """Append one trigger rule to the draft trigger ledger.

    Args:
        draft: Draft state mutated in place.
        flora_species_id: Flora species identifier.
        herbivore_species_id: Herbivore species identifier.
        substance_id: Substance identifier synthesized by the rule.
        action_type: "synthesize_substance" or "resource_withdrawal".
        apparent_nutrition_factor: Factor for resource_withdrawal.
        withdrawal_duration: Duration of the nutrition withdrawal.
        aftereffect_ticks: Duration of aftereffect.
        min_herbivore_population: Minimum herbivore population threshold.
        activation_condition: Optional nested activation-condition tree.
        initiator_type: The type of trigger initiator.
        initiator_signal_id: The ID of the environmental signal.
        initiator_min_concentration: Minimum signal concentration.

    """
    draft.trigger_rules.append(
        TriggerRule(
            flora_species_id=flora_species_id,
            initiator_type=initiator_type,
            herbivore_species_id=herbivore_species_id,
            min_herbivore_population=min_herbivore_population,
            initiator_signal_id=initiator_signal_id,
            initiator_min_concentration=initiator_min_concentration,
            substance_id=substance_id,
            action_type=action_type,
            apparent_nutrition_factor=apparent_nutrition_factor,
            withdrawal_duration=withdrawal_duration,
            aftereffect_ticks=aftereffect_ticks,
            activation_condition=deepcopy(activation_condition),
        )
    )
    logger.debug(
        "Draft trigger rule added (flora_species_id=%d, herbivore_species_id=%d, substance_id=%d, total_rules=%d)",
        flora_species_id,
        herbivore_species_id,
        substance_id,
        len(draft.trigger_rules),
    )


def remove_trigger_rule(draft: DraftState, index: int) -> None:
    """Remove one trigger rule by list index.

    Args:
        draft: Draft state mutated in place.
        index: Trigger-rule index in the draft list.

    Raises:
        IndexError: The requested trigger-rule index is out of range.

    """
    removed = draft.trigger_rules[index]
    del draft.trigger_rules[index]
    logger.debug(
        (
            "Draft trigger rule removed (index=%d, flora_species_id=%d, "
            "herbivore_species_id=%d, substance_id=%d, total_rules=%d)"
        ),
        index,
        removed.flora_species_id,
        removed.herbivore_species_id,
        removed.substance_id,
        len(draft.trigger_rules),
    )


def update_trigger_rule(
    draft: DraftState,
    index: int,
    *,
    flora_species_id: int | None = None,
    herbivore_species_id: int | None = None,
    initiator_type: Literal["herbivore_attack", "environmental_signal"] | None = None,
    initiator_signal_id: int | None = None,
    initiator_min_concentration: float | None = None,
    substance_id: int | None = None,
    action_type: Literal["synthesize_substance", "resource_withdrawal"] | None = None,
    apparent_nutrition_factor: float | None = None,
    withdrawal_duration: int | None = None,
    aftereffect_ticks: int | None = None,
    min_herbivore_population: int | None = None,
    activation_condition: ActivationConditionNode | None = None,
) -> None:
    """Patch selected fields on one trigger rule.

    Args:
        draft: Draft state mutated in place.
        index: Trigger-rule index in the draft list.
        flora_species_id: Optional replacement flora species identifier.
        herbivore_species_id: Optional replacement herbivore species identifier.
        initiator_type: Optional replacement initiator type.
        initiator_signal_id: Optional replacement signal identifier.
        initiator_min_concentration: Optional replacement minimum concentration.
        substance_id: Optional replacement substance identifier.
        action_type: Optional replacement action type.
        apparent_nutrition_factor: Optional replacement nutrition factor.
        withdrawal_duration: Optional replacement nutrition withdrawal duration.
        aftereffect_ticks: Optional replacement aftereffect ticks.
        min_herbivore_population: Optional replacement threshold.
        activation_condition: Optional replacement condition tree.

    Raises:
        IndexError: The requested trigger-rule index is out of range.

    """
    rule = draft.trigger_rules[index]
    if flora_species_id is not None:
        rule.flora_species_id = flora_species_id
    if herbivore_species_id is not None:
        rule.herbivore_species_id = herbivore_species_id
    if initiator_type is not None:
        rule.initiator_type = initiator_type
    if initiator_signal_id is not None:
        rule.initiator_signal_id = initiator_signal_id
    if initiator_min_concentration is not None:
        rule.initiator_min_concentration = initiator_min_concentration
    if substance_id is not None:
        rule.substance_id = substance_id
    if action_type is not None:
        rule.action_type = action_type
    if apparent_nutrition_factor is not None:
        rule.apparent_nutrition_factor = apparent_nutrition_factor
    if withdrawal_duration is not None:
        rule.withdrawal_duration = withdrawal_duration
    if aftereffect_ticks is not None:
        rule.aftereffect_ticks = aftereffect_ticks
    if min_herbivore_population is not None:
        rule.min_herbivore_population = min_herbivore_population
    if activation_condition is not None:
        rule.activation_condition = deepcopy(activation_condition)
    logger.debug(
        "Draft trigger rule updated (index=%d, flora_species_id=%d, herbivore_species_id=%d, substance_id=%d)",
        index,
        rule.flora_species_id,
        rule.herbivore_species_id,
        rule.substance_id,
    )


def trigger_rule_by_index(draft: DraftState, index: int) -> TriggerRule:
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
