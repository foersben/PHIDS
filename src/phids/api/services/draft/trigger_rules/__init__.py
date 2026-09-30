# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Draft-state mutation module for trigger rules and conditions.

Provides pure functions to add, remove, and update trigger rules, as well as complex
tree-manipulation functions for editing the hierarchical activation condition nodes.
Also exposes read-only query helpers (e.g. ``get_condition_node``) so callers never
need to import private ``ui_state`` path-resolution utilities directly.
"""

from __future__ import annotations

from phids.api.services.draft.trigger_rules.conditions import (
    append_trigger_rule_condition_child,
    default_activation_condition_for_rule,
    delete_trigger_rule_condition_node,
    get_condition_node,
    parse_activation_condition_json,
    replace_trigger_rule_condition_node,
    set_trigger_rule_activation_condition,
    update_trigger_rule_condition_node,
)
from phids.api.services.draft.trigger_rules.core import (
    add_trigger_rule,
    remove_trigger_rule,
    trigger_rule_by_index,
    update_trigger_rule,
)

__all__ = [
    "add_trigger_rule",
    "append_trigger_rule_condition_child",
    "default_activation_condition_for_rule",
    "delete_trigger_rule_condition_node",
    "get_condition_node",
    "parse_activation_condition_json",
    "remove_trigger_rule",
    "replace_trigger_rule_condition_node",
    "set_trigger_rule_activation_condition",
    "trigger_rule_by_index",
    "update_trigger_rule",
    "update_trigger_rule_condition_node",
]
