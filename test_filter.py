def _species_map(row, key):
    pass


def _filter_dict(d: dict[int, object], keep: set[int]) -> dict[int, object]:
    return {k: v for k, v in d.items() if k in keep}


def _filter_single_row(
    row: dict,
    flora_keep: set[int] | None,
    herbivore_keep: set[int] | None,
) -> dict:
    clone = dict(row)
    if flora_keep is not None:
        clone["plant_pop_by_species"] = _filter_dict(_species_map(row, "plant_pop_by_species"), flora_keep)
        clone["plant_energy_by_species"] = _filter_dict(_species_map(row, "plant_energy_by_species"), flora_keep)
        clone["defense_cost_by_species"] = _filter_dict(_species_map(row, "defense_cost_by_species"), flora_keep)
    if herbivore_keep is not None:
        clone["swarm_pop_by_species"] = _filter_dict(_species_map(row, "swarm_pop_by_species"), herbivore_keep)
    return clone
