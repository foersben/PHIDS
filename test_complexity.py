def _update_herbivore_presence(updates, herbivore_species_id, min_herbivore_population):
    if herbivore_species_id is not None:
        updates["herbivore_species_id"] = herbivore_species_id
    if min_herbivore_population is not None:
        updates["min_herbivore_population"] = max(1, min_herbivore_population)


def _update_substance_active(updates, substance_id):
    if substance_id is not None:
        updates["substance_id"] = substance_id


def _update_environmental_signal(updates, signal_id, min_concentration):
    if signal_id is not None:
        updates["signal_id"] = signal_id
    if min_concentration is not None:
        updates["min_concentration"] = max(0.0, min_concentration)


def _build_node_updates(
    current_kind: str,
    kind: str | None = None,
    herbivore_species_id: int | None = None,
    min_herbivore_population: int | None = None,
    substance_id: int | None = None,
    signal_id: int | None = None,
    min_concentration: float | None = None,
) -> dict[str, object]:
    updates: dict[str, object] = {}

    if current_kind == "herbivore_presence":
        _update_herbivore_presence(updates, herbivore_species_id, min_herbivore_population)
    elif current_kind == "substance_active":
        _update_substance_active(updates, substance_id)
    elif current_kind == "environmental_signal":
        _update_environmental_signal(updates, signal_id, min_concentration)
    elif current_kind in {"all_of", "any_of"} and kind is not None:
        updates["kind"] = kind

    return updates
