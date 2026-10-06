import dataclasses

def _remove_herbivore_trigger_rules(rules, species_id: int):
    new_rules = []
    for rule in rules:
        if rule.herbivore_species_id == species_id:
            continue
        new_rule = dataclasses.replace(rule)
        if new_rule.herbivore_species_id > species_id:
            new_rule.herbivore_species_id -= 1
        # Mock _remap_condition_references
        new_rule.activation_condition = new_rule.activation_condition
        new_rules.append(new_rule)
    return new_rules

def remove_herbivore(draft, species_id: int) -> None:
    idx = next(
        (
            i
            for i, pp in enumerate(draft.herbivore_species)
            if pp.__class__.__name__ == "HerbivoreSpeciesParams" and pp.species_id == species_id
        ),
        None,
    )
    if idx is None:
        raise ValueError(f"Herbivore species_id {species_id} not found.")

    del draft.herbivore_species[idx]
    if idx < len(draft.diet_matrix):
        del draft.diet_matrix[idx]

    draft.trigger_rules = _remove_herbivore_trigger_rules(draft.trigger_rules, species_id)

    draft.initial_swarms = [s for s in draft.initial_swarms if s.species_id != species_id]
