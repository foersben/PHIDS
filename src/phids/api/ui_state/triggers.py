# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Server-side draft state model for the HTMX scenario-builder UI in PHIDS.

This module implements :class:`DraftState`, a server-side configuration accumulator for the PHIDS
scenario-builder UI. ``DraftState`` stores all operator choices made through the web interface,
including species definitions, substance properties, trigger rules, diet-matrix entries, and
initial placements, before committing them to the simulation engine via
``POST /api/scenario/load-draft``. Imperative mutation procedures are executed by
the ``phids.api.services.draft`` functions against ``DraftState`` instances, while
this module retains data structures, condition-tree utilities, schema export logic, and singleton
draft lifecycle management. No concurrency-safe locking is applied, as the server is designed for
single-operator workbench usage.
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Literal

logger = logging.getLogger(__name__)

type ConditionScalar = str | int | float | bool
type ConditionValue = object
type ActivationConditionNode = dict[str, object]

# Trigger rule
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class TriggerRule:
    """One explicit chemical-defense trigger rule.

    A rule says: "when flora species *flora_species_id* is attacked by
    herbivore species *herbivore_species_id* with at least
    *min_herbivore_population* individuals, synthesise substance
    *substance_id*. Optional nested activation conditions can additionally
    require active substances and/or other herbivore presences via explicit
    ``all_of`` / ``any_of`` predicate trees. ``None`` = unconditional."

    Multiple rules may share the same (flora, herbivore) pair to express
    production of different substances simultaneously.

    Args:
        flora_species_id: Flora species index (0-based).
        herbivore_species_id: Herbivore species index (0-based).
        substance_id: Substance layer index to synthesise.
        min_herbivore_population: Minimum swarm size to trigger this rule.
        activation_condition: Optional JSON-serialisable predicate tree.

    """

    flora_species_id: int
    initiator_type: Literal["herbivore_attack", "environmental_signal"] = "herbivore_attack"
    herbivore_species_id: int = 0
    min_herbivore_population: int = 5
    initiator_signal_id: int = 0
    initiator_min_concentration: float = 0.01
    substance_id: int = 0
    action_type: Literal["synthesize_substance", "resource_withdrawal"] = "synthesize_substance"
    apparent_nutrition_factor: float = 0.2
    withdrawal_duration: int = 10
    aftereffect_ticks: int = 10
    activation_condition: ActivationConditionNode | None = None


def _parse_condition_path(path: str) -> list[int]:
    """Parse a dotted child-path like ``0.1.2`` into list indices."""
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
    """Create a default activation-condition node of the requested kind."""
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
    """Return the condition node at ``path`` or raise on invalid traversal."""
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
    """Remove empty nested groups after delete/remap operations."""
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
    """Compact/remove nested condition references after entity deletion."""
    if condition is None:
        return None

    kind = condition.get("kind")
    if kind in {"all_of", "any_of"}:
        return _remap_group_condition(condition, removed_herbivore_id, removed_substance_id)

    return _remap_leaf_condition(condition, removed_herbivore_id, removed_substance_id)
