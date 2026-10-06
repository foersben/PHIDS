def _collect_live_plants(
    snapshot,
    flora_names,
    owned_substances,
):
    plants_data = snapshot["plants"]
    signal_layers = snapshot["signal_layers"]
    toxin_layers = snapshot["toxin_layers"]
    num_signals = snapshot["num_signals"]
    num_toxins = snapshot["num_toxins"]

    plants = {
        "entity_id": [],
        "species_id": [],
        "name": [],
        "x": [],
        "y": [],
        "energy": [],
        "max_energy": [],
        "structural_mass": [],
        "max_structural_mass": [],
        "fragility_pct": [],
        "incidental_risk_level": [],
        "root_link_count": [],
        "active_signal_ids": [],
        "active_toxin_ids": [],
    }

    for p in plants_data:
        plant_substances = owned_substances.get(p["entity_id"], [])
        local_signal_ids = (
            {signal_id for signal_id in range(num_signals) if float(signal_layers[signal_id, p["x"], p["y"]]) > 0.0}
            if signal_layers is not None
            else set()
        )

        local_toxin_ids = (
            {toxin_id for toxin_id in range(num_toxins) if float(toxin_layers[toxin_id, p["x"], p["y"]]) > 0.0}
            if toxin_layers is not None
            else set()
        )

        visible_signal_ids = sorted(
            local_signal_ids
            | {sub["substance_id"] for sub in plant_substances if not sub["is_toxin"] and sub["is_visible"]}
        )
        visible_toxin_ids = sorted(
            local_toxin_ids | {sub["substance_id"] for sub in plant_substances if sub["is_toxin"] and sub["is_visible"]}
        )

        plants["entity_id"].append(p["entity_id"])
        plants["species_id"].append(p["species_id"])
        plants["name"].append(flora_names.get(p["species_id"], f"Flora {p['species_id']}"))
        plants["x"].append(p["x"])
        plants["y"].append(p["y"])
        plants["energy"].append(p["energy"])
        plants["max_energy"].append(p.get("max_energy", 100.0))
        plants["structural_mass"].append(p.get("structural_mass", 0.0))
        plants["max_structural_mass"].append(p.get("max_structural_mass", 0.0))
        plants["fragility_pct"].append(p.get("fragility_pct", 100.0))
        plants["incidental_risk_level"].append(p.get("incidental_risk_level", "High Risk"))
        plants["root_link_count"].append(p["root_link_count"])
        plants["active_signal_ids"].append(visible_signal_ids)
        plants["active_toxin_ids"].append(visible_toxin_ids)
    return plants
