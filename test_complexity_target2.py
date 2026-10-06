import dataclasses

def _remove_flora_trigger_rules(rules, species_id: int):
    new_rules = []
    for rule in rules:
        if rule.flora_species_id == species_id:
            continue
        new_rule = dataclasses.replace(rule)
        if new_rule.flora_species_id > species_id:
            new_rule.flora_species_id -= 1
        new_rules.append(new_rule)
    return new_rules

def remove_flora(draft, species_id: int) -> None:
    idx = next(
        (
            i
            for i, fp in enumerate(draft.flora_species)
            if fp.__class__.__name__ == "FloraSpeciesParams" and fp.species_id == species_id
        ),
        None,
    )
    if idx is None:
        raise ValueError(f"Flora species_id {species_id} not found.")

    del draft.flora_species[idx]
    for row in draft.diet_matrix:
        if idx < len(row):
            del row[idx]

    draft.trigger_rules = _remove_flora_trigger_rules(draft.trigger_rules, species_id)

    draft.initial_plants = [p for p in draft.initial_plants if p.species_id != species_id]
