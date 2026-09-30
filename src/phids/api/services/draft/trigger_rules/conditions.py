# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Activation condition tree manipulations for draft trigger rules."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import TYPE_CHECKING

from fastapi import HTTPException
from pydantic import TypeAdapter, ValidationError

from phids.api.schemas.conditions import ConditionNode
from phids.api.ui_state.triggers import (
    ActivationConditionNode,
    ConditionValue,
    TriggerRule,
    _condition_node_at_path,
    _parse_condition_path,
    _prune_empty_condition_groups,
)

if TYPE_CHECKING:
    from phids.api.ui_state.state import DraftState


def get_condition_node(
    rule_condition: ActivationConditionNode,
    path: str,
) -> ActivationConditionNode:
    """Resolve one condition node by a dotted path string.

    This is the public surface for condition-tree reads so that callers never
    need to import the private ``_condition_node_at_path`` / ``_parse_condition_path``
    helpers from ``ui_state`` directly.

    Args:
        rule_condition: Root condition node of a trigger rule.
        path: Dotted integer-index path (e.g. ``"0.1"``). Empty string returns the root.

    Returns:
        The ``ActivationConditionNode`` dict at the requested path.

    Raises:
        IndexError: The path does not resolve to a valid node.

    """
    if not path:
        return rule_condition
    return _condition_node_at_path(rule_condition, _parse_condition_path(path))


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
    if rule.activation_condition is None:
        raise IndexError("Trigger rule has no activation condition to replace.")
    if not path:
        rule.activation_condition = deepcopy(condition)
        return

    tokens = _parse_condition_path(path)
    parent_tokens = tokens[:-1]
    child_index = tokens[-1]
    parent = _condition_node_at_path(rule.activation_condition, parent_tokens)
    children = parent.get("conditions")
    if not isinstance(children, list) or child_index >= len(children):
        raise IndexError(f"Condition path {path!r} cannot be replaced.")
    children[child_index] = deepcopy(condition)


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


def append_trigger_rule_condition_child(
    draft: DraftState,
    index: int,
    path: str,
    child_condition: ActivationConditionNode,
) -> None:
    """Append one child condition into a composite group condition node.

    Args:
        draft: Draft state mutated in place.
        index: Trigger-rule index in the draft list.
        path: Dotted path identifying the composite parent node.
        child_condition: Child condition payload to append.

    Raises:
        IndexError: The path does not resolve to an activation condition.
        ValueError: The addressed node is not a composite (has no ``conditions`` list).

    """
    rule = draft.trigger_rules[index]
    if rule.activation_condition is None:
        raise IndexError("Trigger rule has no activation condition.")
    parent = _condition_node_at_path(rule.activation_condition, _parse_condition_path(path))
    children = parent.get("conditions")
    if not isinstance(children, list):
        raise ValueError(f"Condition node at {path!r} is not composite.")
    children.append(deepcopy(child_condition))


def delete_trigger_rule_condition_node(
    draft: DraftState,
    index: int,
    path: str,
) -> None:
    """Delete one condition node addressed by a dotted path.

    If deleting this node leaves a parent group condition empty, the group is
    pruned recursively. If the root node is deleted or pruned away, the rule's
    ``activation_condition`` is set to ``None``.

    Args:
        draft: Draft state mutated in place.
        index: Trigger-rule index in the draft list.
        path: Dotted path identifying the node to delete.

    Raises:
        IndexError: The path or child index is not valid.

    """
    rule = draft.trigger_rules[index]
    if rule.activation_condition is None:
        raise IndexError("Trigger rule has no activation condition.")
    if not path:
        rule.activation_condition = None
        return

    tokens = _parse_condition_path(path)
    parent_tokens = tokens[:-1]
    child_index = tokens[-1]
    parent = _condition_node_at_path(rule.activation_condition, parent_tokens)
    children = parent.get("conditions")
    if not isinstance(children, list) or child_index >= len(children):
        raise IndexError(f"Condition path {path!r} cannot be deleted.")
    del children[child_index]

    if not _prune_empty_condition_groups(rule.activation_condition):
        rule.activation_condition = None


_condition_adapter: TypeAdapter[ConditionNode] = TypeAdapter(ConditionNode)


def parse_activation_condition_json(raw: str | None) -> ActivationConditionNode | None:
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


def default_activation_condition_for_rule(
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
