# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Collection helpers for live dashboard payloads."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from phids.api.schemas.species import FloraSpeciesParams


def _collect_live_plants(
    snapshot: dict[str, Any],
    flora_names: dict[int, str],
    owned_substances: dict[int, list[dict[str, Any]]],
) -> dict[str, list[object]]:
    """Collect live plant properties from snapshot.

    Args:
        snapshot: The thread-safe snapshot dictionary.
        flora_names: Mapping of species IDs to display names.
        owned_substances: Mapping of plant IDs to their owned substances.

    Returns:
        Dictionary of lists containing plant properties.
    """
    plants_data = snapshot["plants"]
    signal_layers = snapshot["signal_layers"]
    toxin_layers = snapshot["toxin_layers"]
    num_signals = snapshot["num_signals"]
    num_toxins = snapshot["num_toxins"]

    plants: dict[str, list[object]] = {
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

    # For dense grid scenes (e.g. 256x256 benchmark with 19,663 plants), serializing every silent
    # plant in the live WebSocket stream payload causes 2.5MB payload sizes and client latency.
    # We serialize all plants when count < 1000, and for dense scenes we filter to active plant nodes
    # (emitting signals, toxins, or connected via mycorrhiza).
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


def _collect_live_swarms(
    snapshot: dict[str, Any],
    herbivore_names: dict[int, str],
) -> dict[str, list[object]]:
    """Collect live swarm properties from snapshot.

    Args:
        snapshot: The thread-safe snapshot dictionary.
        herbivore_names: Mapping of species IDs to display names.

    Returns:
        Dictionary of lists containing swarm properties.
    """
    swarms_data = snapshot["swarms"]
    toxin_layers = snapshot["toxin_layers"]

    swarms: dict[str, list[object]] = {
        "x": [],
        "y": [],
        "population": [],
        "species_id": [],
        "name": [],
        "energy": [],
        "energy_deficit": [],
        "repelled": [],
        "repelled_ticks_remaining": [],
        "toxin_level": [],
        "intoxicated": [],
    }
    for s in swarms_data:
        toxin_level = float(toxin_layers[:, s["x"], s["y"]].max()) if toxin_layers is not None else 0.0
        swarms["x"].append(s["x"])
        swarms["y"].append(s["y"])
        swarms["population"].append(s["population"])
        swarms["species_id"].append(s["species_id"])
        swarms["name"].append(herbivore_names.get(s["species_id"], f"Herbivore {s['species_id']}"))
        swarms["energy"].append(s["energy"])
        swarms["energy_deficit"].append(
            max(
                0.0,
                float(s["population"] * s["energy_min"] - s["energy"]),
            )
        )
        swarms["repelled"].append(s["repelled"])
        swarms["repelled_ticks_remaining"].append(s["repelled_ticks_remaining"])
        swarms["toxin_level"].append(toxin_level)
        swarms["intoxicated"].append(toxin_level > 0.0)
    return swarms


def _collect_flora_species(
    config_flora_species: list[FloraSpeciesParams],
    plant_energy_by_species: Any,
    width: int,
    height: int,
    live_flora_species_ids: set[int],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Collect active flora species metrics from snapshot.

    Args:
        config_flora_species: List of configured flora species.
        plant_energy_by_species: The total energy matrix keyed by species.
        width: The grid width.
        height: The grid height.
        live_flora_species_ids: The IDs of all non-extinct flora species.

    Returns:
        Tuple of basic species info and species energy info.
    """
    all_flora_species: list[dict[str, object]] = []
    species_energy: list[dict[str, object]] = []
    is_large_grid = width * height >= 10000
    for species in config_flora_species:
        species_id = species.species_id
        is_extinct = species_id not in live_flora_species_ids
        all_flora_species.append(
            {
                "species_id": species_id,
                "name": species.name,
                "extinct": is_extinct,
            }
        )
        if is_extinct or is_large_grid:
            continue
        if species_id < plant_energy_by_species.shape[0]:
            species_energy.append(
                {
                    "species_id": species_id,
                    "name": species.name,
                    "layer": plant_energy_by_species[species_id].tolist(),
                }
            )
        else:
            # Defensive fallback: species_id outside pre-allocated layer bounds.
            species_energy.append(
                {
                    "species_id": species_id,
                    "name": species.name,
                    "layer": [[0.0] * height for _ in range(width)],
                }
            )
    return all_flora_species, species_energy
