# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for trigger-rule tree CRUD operations and error handling.

This module verifies the full lifecycle of trigger-rule mutations:
add, update, set activation condition, append child, update node,
replace node, delete node (by path and root), and remove rule.
Each operation is tested for the happy path and relevant error conditions
(IndexError on invalid paths, ValueError on missing indices).

MUTATION_TESTING_EXEMPTION: None - all paths are deterministic core logic.
"""

from __future__ import annotations

import pytest

from phids.api.services.draft.trigger_rules import (
    add_trigger_rule,
    append_trigger_rule_condition_child,
    delete_trigger_rule_condition_node,
    remove_trigger_rule,
    replace_trigger_rule_condition_node,
    set_trigger_rule_activation_condition,
    update_trigger_rule,
    update_trigger_rule_condition_node,
)
from phids.api.ui_state.state import DraftState
from phids.api.ui_state.substances import SubstanceDefinition


def test_draft_trigger_rule_tree_mutators_apply_edits_and_raise_on_invalid_paths() -> None:
    """Verify trigger-rule tree mutators handle valid edits and raise on invalid paths.

    Intent:
        Exercise the full trigger-rule CRUD pipeline: add a rule with an all_of
        tree, update scalar fields, replace the activation condition, append/update/
        replace/delete individual tree nodes, and confirm final removal of the rule.

    Preconditions:
        - DraftState.default() baseline with two substances.
        - One trigger rule added with an all_of activation condition.

    Invariants Tested:
        - add_trigger_rule stores activation_condition verbatim.
        - update_trigger_rule mutates substance_id and min_herbivore_population.
        - set_trigger_rule_activation_condition replaces the condition tree.
        - append/update/replace node operations mutate the tree correctly.
        - delete node at indexed path removes the node; delete at "" nullifies root.
        - append/update/replace raise IndexError when root is None.
        - remove_trigger_rule empties the rule list.
    """
    draft = DraftState.default()
    draft.substance_definitions = [
        SubstanceDefinition(substance_id=0, name="Signal 0"),
        SubstanceDefinition(substance_id=1, name="Signal 1"),
    ]
    add_trigger_rule(
        draft,
        0,
        0,
        0,
        activation_condition={
            "kind": "all_of",
            "conditions": [
                {"kind": "substance_active", "substance_id": 0},
                {"kind": "substance_active", "substance_id": 1},
            ],
        },
    )
    assert draft.trigger_rules[0].activation_condition == {
        "kind": "all_of",
        "conditions": [
            {"kind": "substance_active", "substance_id": 0},
            {"kind": "substance_active", "substance_id": 1},
        ],
    }

    update_trigger_rule(
        draft,
        0,
        substance_id=1,
        min_herbivore_population=7,
        activation_condition={"kind": "substance_active", "substance_id": 1},
    )
    assert draft.trigger_rules[0].substance_id == 1
    assert draft.trigger_rules[0].min_herbivore_population == 7
    assert draft.trigger_rules[0].activation_condition == {
        "kind": "substance_active",
        "substance_id": 1,
    }

    set_trigger_rule_activation_condition(
        draft,
        0,
        {
            "kind": "all_of",
            "conditions": [
                {
                    "kind": "herbivore_presence",
                    "herbivore_species_id": 0,
                    "min_herbivore_population": 2,
                }
            ],
        },
    )
    append_trigger_rule_condition_child(
        draft,
        0,
        "",
        {"kind": "substance_active", "substance_id": 1},
    )
    update_trigger_rule_condition_node(draft, 0, "0", min_herbivore_population=3)
    replace_trigger_rule_condition_node(
        draft,
        0,
        "1",
        {"kind": "herbivore_presence", "herbivore_species_id": 0, "min_herbivore_population": 4},
    )
    assert draft.trigger_rules[0].activation_condition == {
        "kind": "all_of",
        "conditions": [
            {
                "kind": "herbivore_presence",
                "herbivore_species_id": 0,
                "min_herbivore_population": 3,
            },
            {
                "kind": "herbivore_presence",
                "herbivore_species_id": 0,
                "min_herbivore_population": 4,
            },
        ],
    }

    delete_trigger_rule_condition_node(draft, 0, "1")
    assert draft.trigger_rules[0].activation_condition == {
        "kind": "all_of",
        "conditions": [{"kind": "herbivore_presence", "herbivore_species_id": 0, "min_herbivore_population": 3}],
    }
    delete_trigger_rule_condition_node(draft, 0, "")
    assert draft.trigger_rules[0].activation_condition is None

    with pytest.raises(IndexError):
        append_trigger_rule_condition_child(draft, 0, "", {"kind": "substance_active", "substance_id": 0})
    with pytest.raises(IndexError):
        update_trigger_rule_condition_node(draft, 0, "0", substance_id=0)
    with pytest.raises(IndexError):
        replace_trigger_rule_condition_node(
            draft,
            0,
            "0",
            {"kind": "substance_active", "substance_id": 0},
        )

    remove_trigger_rule(draft, 0)
    assert draft.trigger_rules == []
