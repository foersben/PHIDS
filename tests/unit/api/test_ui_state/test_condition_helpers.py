# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for condition helper utilities and condition-tree navigation.

This module verifies the deterministic behavior of internal condition-tree
helpers used by the trigger-rule editor: type label synthesis, path parsing,
default condition node construction, tree navigation by indexed path, empty-group
pruning, and condition-reference remapping after species/substance removal.

MUTATION_TESTING_EXEMPTION: None - all branches are deterministic pure-function
logic suitable for mutmut coverage.
"""

from __future__ import annotations

from copy import deepcopy
from typing import cast

import pytest

from phids.api.ui_state.substances import SubstanceDefinition
from phids.api.ui_state.triggers import (
    _condition_node_at_path,
    _default_activation_condition_node,
    _parse_condition_path,
    _prune_empty_condition_groups,
    _remap_condition_references,
)


def test_condition_helper_utilities_and_type_labels() -> None:
    """Verify condition helper utilities and substance type labels remain deterministic.

    Intent:
        Validate that SubstanceDefinition.type_label, path parsing, and default
        condition node synthesis produce the documented deterministic outputs
        across all supported condition kinds.

    Preconditions:
        - DraftState reset via autouse fixture.

    Invariants Tested:
        - Substance type labels: Signal, Toxin, Lethal Toxin, Repellent Toxin.
        - _parse_condition_path returns [] for empty string and [0, 1, 2] for "0.1.2".
        - _default_activation_condition_node builds correct dicts per kind.
        - Unsupported kind raises ValueError.
    """
    assert SubstanceDefinition(substance_id=0, is_toxin=False).type_label == "Signal"
    assert SubstanceDefinition(substance_id=1, is_toxin=True).type_label == "Toxin"
    assert SubstanceDefinition(substance_id=2, is_toxin=True, lethal=True).type_label == "Lethal Toxin"
    assert SubstanceDefinition(substance_id=3, is_toxin=True, repellent=True).type_label == "Repellent Toxin"

    assert _parse_condition_path("") == []
    assert _parse_condition_path("0.1.2") == [0, 1, 2]

    assert _default_activation_condition_node(
        "herbivore_presence",
        herbivore_species_id=3,
        min_herbivore_population=0,
    ) == {
        "kind": "herbivore_presence",
        "herbivore_species_id": 3,
        "min_herbivore_population": 1,
    }
    assert _default_activation_condition_node("substance_active", substance_id=7) == {
        "kind": "substance_active",
        "substance_id": 7,
    }
    group_node = cast(
        "dict[str, object]",
        _default_activation_condition_node("all_of", herbivore_species_id=2),
    )
    group_conditions = cast("list[dict[str, object]]", group_node["conditions"])
    assert group_conditions[0]["herbivore_species_id"] == 2
    assert _default_activation_condition_node("any_of")["kind"] == "any_of"

    with pytest.raises(ValueError):
        _default_activation_condition_node("unsupported")


def test_condition_tree_navigation_pruning_and_remap() -> None:
    """Verify condition-tree navigation, empty-group pruning, and ID remapping behave deterministically.

    Intent:
        Validate the three major condition-tree traversal operations:
        1. Navigation by index path raises appropriately on invalid paths.
        2. Pruning removes empty ``all_of``/``any_of`` groups and preserves leaves.
        3. Remapping after species/substance removal decrements IDs and drops pruned nodes.

    Preconditions:
        - Nested root tree with one all_of containing one any_of with two leaf nodes.

    Invariants Tested:
        - _condition_node_at_path navigates to correct nodes and raises IndexError on invalid paths.
        - _prune_empty_condition_groups returns None for None, preserves atomic nodes,
          and drops empty groups.
        - _remap_condition_references removes node at removed_id, decrements higher IDs,
          and returns None when the root itself is removed.
    """
    root = {
        "kind": "all_of",
        "conditions": [
            {
                "kind": "herbivore_presence",
                "herbivore_species_id": 1,
                "min_herbivore_population": 2,
            },
            {
                "kind": "any_of",
                "conditions": [
                    {"kind": "substance_active", "substance_id": 3},
                    {
                        "kind": "herbivore_presence",
                        "herbivore_species_id": 2,
                        "min_herbivore_population": 4,
                    },
                ],
            },
        ],
    }
    assert _condition_node_at_path(root, [1])["kind"] == "any_of"
    assert _condition_node_at_path(root, [1, 0])["substance_id"] == 3

    with pytest.raises(IndexError):
        _condition_node_at_path({"kind": "herbivore_presence"}, [0])
    with pytest.raises(IndexError):
        _condition_node_at_path({"kind": "all_of", "conditions": []}, [0])
    with pytest.raises(IndexError):
        _condition_node_at_path({"kind": "all_of", "conditions": ["bad"]}, [0])

    assert _prune_empty_condition_groups(None) is None
    assert _prune_empty_condition_groups({"kind": "substance_active", "substance_id": 1}) == {
        "kind": "substance_active",
        "substance_id": 1,
    }
    assert _prune_empty_condition_groups(
        {
            "kind": "all_of",
            "conditions": [
                {"kind": "any_of", "conditions": []},
                {"kind": "substance_active", "substance_id": 5},
                "ignored",
            ],
        }
    ) == {
        "kind": "all_of",
        "conditions": [{"kind": "substance_active", "substance_id": 5}],
    }

    remapped = _remap_condition_references(
        deepcopy(root),
        removed_herbivore_id=1,
        removed_substance_id=2,
    )
    assert remapped == {
        "kind": "all_of",
        "conditions": [
            {
                "kind": "any_of",
                "conditions": [
                    {"kind": "substance_active", "substance_id": 2},
                    {
                        "kind": "herbivore_presence",
                        "herbivore_species_id": 1,
                        "min_herbivore_population": 4,
                    },
                ],
            }
        ],
    }
    assert (
        _remap_condition_references(
            {
                "kind": "herbivore_presence",
                "herbivore_species_id": 0,
                "min_herbivore_population": 1,
            },
            removed_herbivore_id=0,
        )
        is None
    )
    assert (
        _remap_condition_references(
            {"kind": "substance_active", "substance_id": 0},
            removed_substance_id=0,
        )
        is None
    )
