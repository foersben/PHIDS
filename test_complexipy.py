from phids.telemetry.export.core import TelemetryRows


def get_phasespace_axis(
    rows: TelemetryRows,
    species_id: int,
    is_flora: bool,
    names: dict[int, str] | None,
) -> tuple[list[float], str]:
    if species_id == 0:
        return _get_phasespace_axis_total(rows, is_flora)
    return _get_phasespace_axis_species(rows, species_id, is_flora, names)


def _get_phasespace_axis_total(
    rows: TelemetryRows,
    is_flora: bool,
) -> tuple[list[float], str]:
    if is_flora:
        return [float(r.get("flora_population", 0)) for r in rows], "Flora (Total)"
    return [float(r.get("herbivore_population", 0)) for r in rows], "Herbivores (Total)"


def _get_phasespace_axis_species(
    rows: TelemetryRows,
    species_id: int,
    is_flora: bool,
    names: dict[int, str] | None,
) -> tuple[list[float], str]:
    if is_flora:
        y = [float(r.get("plant_pop_by_species", {}).get(species_id, 0)) for r in rows]
        name = (names or {}).get(species_id, f"Flora {species_id}")
    else:
        y = [float(r.get("swarm_pop_by_species", {}).get(species_id, 0)) for r in rows]
        name = (names or {}).get(species_id, f"Herbivore {species_id}")
    return y, name
