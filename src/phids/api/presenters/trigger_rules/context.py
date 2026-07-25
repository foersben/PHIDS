"""Trigger rules context presentation logic."""

import json

from phids.api.presenters.dashboard.shared import _describe_activation_condition
from phids.api.ui_state import DraftState


def trigger_rules_template_context(draft: DraftState) -> dict[str, object]:
    """Assemble the canonical template context for trigger-rule partial rendering.

    Args:
        draft: Active draft scenario state used as the authoritative builder source.

    Returns:
        Template context dictionary containing species registries, trigger rows, condition summaries,
        and condition-node editing metadata.
    """
    herbivore_names = {
        getattr(species, "species_id", index): getattr(species, "name", f"Herbivore {index}")
        for index, species in enumerate(draft.herbivore_species)
    }
    substance_names = {definition.substance_id: definition.name for definition in draft.substance_definitions}
    return {
        "flora_species": draft.flora_species,
        "herbivore_species": draft.herbivore_species,
        "trigger_rules": draft.trigger_rules,
        "substances": draft.substance_definitions,
        "trigger_rule_condition_json": {
            index: json.dumps(rule.activation_condition, indent=2) if rule.activation_condition is not None else ""
            for index, rule in enumerate(draft.trigger_rules)
        },
        "trigger_rule_condition_summary": {
            index: _describe_activation_condition(
                rule.activation_condition,
                herbivore_names=herbivore_names,
                substance_names=substance_names,
            )
            for index, rule in enumerate(draft.trigger_rules)
        },
        "condition_group_kinds": ["all_of", "any_of"],
        "condition_leaf_kinds": [
            "herbivore_presence",
            "substance_active",
            "environmental_signal",
        ],
    }
