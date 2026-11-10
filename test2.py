def _get_species_population_series(rows, species_id, is_flora):
    if is_flora:
        return [float(r.get("plant_pop_by_species", {}).get(species_id, 0)) for r in rows]
    return [float(r.get("swarm_pop_by_species", {}).get(species_id, 0)) for r in rows]


def _get_total_population_series(rows, is_flora):
    if is_flora:
        return [float(r.get("flora_population", 0)) for r in rows]
    return [float(r.get("herbivore_population", 0)) for r in rows]


def _get_species_name(species_id, is_flora, names):
    if is_flora:
        return (names or {}).get(species_id, f"Flora {species_id}")
    return (names or {}).get(species_id, f"Herbivore {species_id}")


def get_phasespace_axis(
    rows: list,
    species_id: int,
    is_flora: bool,
    names: dict[int, str] | None,
) -> tuple[list[float], str]:
    if species_id == 0:
        return _get_total_population_series(rows, is_flora), "Flora (Total)" if is_flora else "Herbivores (Total)"

    return _get_species_population_series(rows, species_id, is_flora), _get_species_name(species_id, is_flora, names)
