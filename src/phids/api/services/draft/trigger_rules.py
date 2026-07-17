# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Draft-state mutation module for trigger rules and conditions.

Provides pure functions to add, remove, and update trigger rules, as well as complex
tree-manipulation functions for editing the hierarchical activation condition nodes.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from typing import Literal

from phids.api.ui_state import (
    ActivationConditionNode,
    ConditionValue,
    DraftState,
    TriggerRule,
    _condition_node_at_path,
    _parse_condition_path,
    _prune_empty_condition_groups,
)

logger = logging.getLogger(__name__)


def add_trigger_rule(
    draft: DraftState,
    flora_species_id: int,
    herbivore_species_id: int,
    substance_id: int = 0,
    action_type: Literal["synthesize_substance", "resource_withdrawal"] = "synthesize_substance",
    apparent_nutrition_factor: float = 0.2,
    aftereffect_ticks: int = 10,
    min_herbivore_population: int = 5,
    activation_condition: ActivationConditionNode | None = None,
) -> None:
    """Append one trigger rule to the draft trigger ledger.

    Args:
        draft: Draft state mutated in place.
        flora_species_id: Flora species identifier.
        herbivore_species_id: Herbivore species identifier.
        substance_id: Substance identifier synthesized by the rule.
        action_type: "synthesize_substance" or "resource_withdrawal".
        apparent_nutrition_factor: Factor for resource_withdrawal.
        aftereffect_ticks: Duration of aftereffect.
        min_herbivore_population: Minimum herbivore population threshold.
        activation_condition: Optional nested activation-condition tree.

    """
    draft.trigger_rules.append(
        TriggerRule(
            flora_species_id=flora_species_id,
            herbivore_species_id=herbivore_species_id,
            substance_id=substance_id,
            action_type=action_type,
            apparent_nutrition_factor=apparent_nutrition_factor,
            aftereffect_ticks=aftereffect_ticks,
            min_herbivore_population=min_herbivore_population,
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
    substance_id: int | None = None,
    action_type: Literal["synthesize_substance", "resource_withdrawal"] | None = None,
    apparent_nutrition_factor: float | None = None,
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
        substance_id: Optional replacement substance identifier.
        action_type: Optional replacement action type.
        apparent_nutrition_factor: Optional replacement nutrition factor.
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
    if substance_id is not None:
        rule.substance_id = substance_id
    if action_type is not None:
        rule.action_type = action_type
    if apparent_nutrition_factor is not None:
        rule.apparent_nutrition_factor = apparent_nutrition_factor
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


def set_trigger_rule_activation_condition(
    draft: DraftState,
    index: int,
    condition: ActivationConditionNode | None,
) -> None:
    """Replace the full activation-condition tree for one trigger rule.

    Args:
        draft: Draft state mutated in place.
        index: Trigger-rule index in the draft list.
        condition: Full replacement condition tree.

    """
    draft.trigger_rules[index].activation_condition = deepcopy(condition)


def replace_trigger_rule_condition_node(
    draft: DraftState,
    index: int,
    path: str,
    condition: ActivationConditionNode,
) -> None:
    """Replace one condition node addressed by a dotted path.

    Args:
        draft: Draft state mutated in place.
        index: Trigger-rule index in the draft list.
        path: Dotted child index path identifying the node to replace.
        condition: Replacement node payload.

    Raises:
        IndexError: The path or parent node does not resolve to a mutable child slot.

    """
    rule = draft.trigger_rules[index]
    if not path:
        rule.activation_condition = deepcopy(condition)
        return
    if rule.activation_condition is None:
        raise IndexError("Trigger rule has no activation condition to replace.")
    root = deepcopy(rule.activation_condition)
    path_indices = _parse_condition_path(path)
    parent = _condition_node_at_path(root, path_indices[:-1])
    if parent.get("kind") not in {"all_of", "any_of"}:
        raise IndexError("Condition parent is not a group node.")
    children = parent.get("conditions")
    if not isinstance(children, list):
        raise IndexError("Condition parent has no child list.")
    child_index = path_indices[-1]
    if child_index < 0 or child_index >= len(children):
        raise IndexError("Condition node index is out of range.")
    children[child_index] = deepcopy(condition)
    rule.activation_condition = root


def append_trigger_rule_condition_child(
    draft: DraftState,
    index: int,
    parent_path: str,
    condition: ActivationConditionNode,
) -> None:
    """Append one child condition to a group node in a trigger tree.

    Args:
        draft: Draft state mutated in place.
        index: Trigger-rule index in the draft list.
        parent_path: Dotted path to the parent group node.
        condition: Child node payload to append.

    Raises:
        IndexError: The parent node is missing or is not a valid group node.

    """
    rule = draft.trigger_rules[index]
    if rule.activation_condition is None:
        raise IndexError("Trigger rule has no activation condition to append to.")
    root = deepcopy(rule.activation_condition)
    parent = _condition_node_at_path(root, _parse_condition_path(parent_path))
    if parent.get("kind") not in {"all_of", "any_of"}:
        raise IndexError("Condition parent is not a group node.")
    children = parent.setdefault("conditions", [])
    if not isinstance(children, list):
        raise IndexError("Condition parent has an invalid child list.")
    children.append(deepcopy(condition))
    rule.activation_condition = root


def delete_trigger_rule_condition_node(draft: DraftState, index: int, path: str) -> None:
    """Delete one condition node by dotted path and prune empty groups.

    Args:
        draft: Draft state mutated in place.
        index: Trigger-rule index in the draft list.
        path: Dotted child index path to remove.

    Raises:
        IndexError: The path or parent node does not resolve to a removable child slot.

    """
    rule = draft.trigger_rules[index]
    if rule.activation_condition is None:
        return
    if not path:
        rule.activation_condition = None
        return
    root = deepcopy(rule.activation_condition)
    path_indices = _parse_condition_path(path)
    parent = _condition_node_at_path(root, path_indices[:-1])
    if parent.get("kind") not in {"all_of", "any_of"}:
        raise IndexError("Condition parent is not a group node.")
    children = parent.get("conditions")
    if not isinstance(children, list):
        raise IndexError("Condition parent has no child list.")
    child_index = path_indices[-1]
    if child_index < 0 or child_index >= len(children):
        raise IndexError("Condition node index is out of range.")
    del children[child_index]
    rule.activation_condition = _prune_empty_condition_groups(root)


def update_trigger_rule_condition_node(
    draft: DraftState,
    index: int,
    path: str,
    **fields: ConditionValue,
) -> None:
    """Patch selected key-value fields on one condition node.

    Args:
        draft: Draft state mutated in place.
        index: Trigger-rule index in the draft list.
        path: Dotted path to the condition node.
        **fields: Replacement key-value fields merged into the node.

    Raises:
        IndexError: The trigger rule has no condition tree or path resolution fails.

    """
    rule = draft.trigger_rules[index]
    if rule.activation_condition is None:
        raise IndexError("Trigger rule has no activation condition to update.")
    root = deepcopy(rule.activation_condition)
    node = _condition_node_at_path(root, _parse_condition_path(path))
    node.update(fields)
    rule.activation_condition = root
