# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Trigger rules and condition node structures for the draft scenario UI."""

from __future__ import annotations

import dataclasses
from typing import Literal

type ConditionScalar = str | int | float | bool
type ConditionValue = object
type ActivationConditionNode = dict[str, object]


@dataclasses.dataclass
class TriggerRule:
    """One explicit chemical-defense trigger rule."""

    flora_species_id: int
    initiator_type: Literal["herbivore_attack", "environmental_signal"] = "herbivore_attack"
    herbivore_species_id: int = 0
    min_herbivore_population: int = 5
    initiator_signal_id: int = 0
    initiator_min_concentration: float = 0.01
    substance_id: int = 0
    action_type: Literal["synthesize_substance", "resource_withdrawal"] = "synthesize_substance"
    apparent_nutrition_factor: float = 0.2
    withdrawal_duration: int = 20
    aftereffect_ticks: int = 10
    activation_condition: ActivationConditionNode | None = None


def _parse_condition_path(path: str) -> list[int]:
    """Parse a dotted child-path like ``0.1.2`` into list indices.

    Args:
        path: The path string to parse.

    Returns:
        A list of integer indices.
    """
    if not path:
        return []
    return [int(part) for part in path.split(".") if part != ""]


def _default_activation_condition_node(
    node_kind: str,
    *,
    herbivore_species_id: int = 0,
    substance_id: int = 0,
    min_herbivore_population: int = 1,
) -> ActivationConditionNode:
    """Create a default activation-condition node of the requested kind.

    Args:
        node_kind: The kind of node to create.
        herbivore_species_id: The herbivore species id.
        substance_id: The substance id.
        min_herbivore_population: The minimum herbivore population.

    Returns:
        The created node.
    """
    if node_kind == "herbivore_presence":
        return {
            "kind": "herbivore_presence",
            "herbivore_species_id": herbivore_species_id,
            "min_herbivore_population": max(1, min_herbivore_population),
        }
    if node_kind == "substance_active":
        return {"kind": "substance_active", "substance_id": substance_id}
    if node_kind in {"all_of", "any_of"}:
        return {
            "kind": node_kind,
            "conditions": [
                _default_activation_condition_node(
                    "herbivore_presence",
                    herbivore_species_id=herbivore_species_id,
                    min_herbivore_population=min_herbivore_population,
                )
            ],
        }
    raise ValueError(f"Unsupported activation-condition node kind: {node_kind}")


def _condition_node_at_path(
    condition: ActivationConditionNode,
    path: list[int],
) -> ActivationConditionNode:
    """Return the condition node at ``path`` or raise on invalid traversal.

    Args:
        condition: The root condition node.
        path: The path of indices to traverse.

    Returns:
        The node at the specified path.
    """
    node = condition
    for index in path:
        if node.get("kind") not in {"all_of", "any_of"}:
            raise IndexError("Condition path traversed into a non-group node.")
        children = node.get("conditions")
        if not isinstance(children, list) or index < 0 or index >= len(children):
            raise IndexError("Condition path index is out of range.")
        child = children[index]
        if not isinstance(child, dict):
            raise IndexError("Condition path resolved to an invalid child node.")
        node = child
    return node


def _prune_empty_condition_groups(
    condition: ActivationConditionNode | None,
) -> ActivationConditionNode | None:
    """Remove empty nested groups after delete/remap operations.

    Args:
        condition: The root condition node.

    Returns:
        The pruned condition node, or None if it was completely pruned.
    """
    if condition is None:
        return None
    if condition.get("kind") not in {"all_of", "any_of"}:
        return condition

    children = condition.get("conditions")
    if not isinstance(children, list):
        return None

    new_children: list[ActivationConditionNode] = []
    for child in children:
        if not isinstance(child, dict):
            continue
        pruned = _prune_empty_condition_groups(child)
        if pruned is not None:
            new_children.append(pruned)
    if not new_children:
        return None
    condition["conditions"] = new_children
    return condition


def _int_from_condition(condition: ActivationConditionNode, key: str, default: int = -1) -> int:
    """Extract an integer from a condition node.

    Args:
        condition: The condition node.
        key: The key to look up.
        default: The default value if not found or invalid.

    Returns:
        The integer value.
    """
    raw = condition.get(key, default)
    if isinstance(raw, bool):
        return default
    if isinstance(raw, (int, float, str)):
        try:
            return int(raw)
        except ValueError:
            return default
    return default


def _remap_herbivore_presence(
    condition: ActivationConditionNode, removed_herbivore_id: int | None
) -> ActivationConditionNode | None:
    """Remap herbivore presence condition after deletion.

    Args:
        condition: The condition node.
        removed_herbivore_id: The ID of the deleted herbivore.

    Returns:
        The updated condition node, or None if it should be removed.
    """
    if removed_herbivore_id is None:
        return condition
    herbivore_species_id = _int_from_condition(condition, "herbivore_species_id")
    if herbivore_species_id == removed_herbivore_id:
        return None
    if herbivore_species_id > removed_herbivore_id:
        condition["herbivore_species_id"] = herbivore_species_id - 1
    return condition


def _remap_substance_active(
    condition: ActivationConditionNode, removed_substance_id: int | None
) -> ActivationConditionNode | None:
    """Remap substance active condition after deletion.

    Args:
        condition: The condition node.
        removed_substance_id: The ID of the deleted substance.

    Returns:
        The updated condition node, or None if it should be removed.
    """
    if removed_substance_id is None:
        return condition
    substance_id = _int_from_condition(condition, "substance_id")
    if substance_id == removed_substance_id:
        return None
    if substance_id > removed_substance_id:
        condition["substance_id"] = substance_id - 1
    return condition


def _remap_leaf_condition(
    condition: ActivationConditionNode,
    removed_herbivore_id: int | None,
    removed_substance_id: int | None,
) -> ActivationConditionNode | None:
    """Remap a leaf condition after deletion.

    Args:
        condition: The leaf condition node.
        removed_herbivore_id: The ID of the deleted herbivore.
        removed_substance_id: The ID of the deleted substance.

    Returns:
        The updated condition node, or None if it should be removed.
    """
    kind = condition.get("kind")
    if kind == "herbivore_presence":
        return _remap_herbivore_presence(condition, removed_herbivore_id)
    if kind == "substance_active":
        return _remap_substance_active(condition, removed_substance_id)
    return condition


def _remap_group_condition(
    condition: ActivationConditionNode,
    removed_herbivore_id: int | None,
    removed_substance_id: int | None,
) -> ActivationConditionNode | None:
    """Remap a group condition after deletion.

    Args:
        condition: The group condition node.
        removed_herbivore_id: The ID of the deleted herbivore.
        removed_substance_id: The ID of the deleted substance.

    Returns:
        The updated condition node, or None if it should be removed.
    """
    children = condition.get("conditions")
    if not isinstance(children, list):
        return None

    new_children = []
    for child in children:
        if not isinstance(child, dict):
            continue
        pruned = _remap_condition_references(
            child,
            removed_herbivore_id=removed_herbivore_id,
            removed_substance_id=removed_substance_id,
        )
        if pruned is not None:
            new_children.append(pruned)

    condition["conditions"] = new_children
    return _prune_empty_condition_groups(condition)


def _remap_condition_references(
    condition: ActivationConditionNode | None,
    *,
    removed_herbivore_id: int | None = None,
    removed_substance_id: int | None = None,
) -> ActivationConditionNode | None:
    """Compact/remove nested condition references after entity deletion.

    Args:
        condition: The root condition node.
        removed_herbivore_id: The ID of the deleted herbivore.
        removed_substance_id: The ID of the deleted substance.

    Returns:
        The updated condition node, or None if it should be removed.
    """
    if condition is None:
        return None

    kind = condition.get("kind")
    if kind in {"all_of", "any_of"}:
        return _remap_group_condition(condition, removed_herbivore_id, removed_substance_id)

    return _remap_leaf_condition(condition, removed_herbivore_id, removed_substance_id)
