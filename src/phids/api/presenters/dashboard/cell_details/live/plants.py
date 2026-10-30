# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Live plant presenters.

Helper functions for extracting plant states and payloads.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from phids.api.presenters.dashboard.cell_details.live.substances import _get_live_substances
from phids.api.presenters.dashboard.shared import calculate_structural_fragility_and_risk

if TYPE_CHECKING:
    from phids.engine.components.plant import PlantComponent
    from phids.engine.components.substances import SubstanceComponent
    from phids.engine.core.biotope import GridEnvironment


def _get_live_mycorrhizal_neighbours(
    plant: PlantComponent,
    plant_lookup: dict[int, PlantComponent],
    flora_names: dict[int, str],
) -> list[dict[str, object]]:
    """Helper to collect mycorrhizal neighbors details.

    Args:
        plant: The plant component.
        plant_lookup: The plant lookup.
        flora_names: The flora names.

    Returns:
        The list of mycorrhizal neighbors.
    """
    mycorrhizal_neighbours = []
    for neighbour_id in sorted(plant.mycorrhizal_connections):
        neighbour = plant_lookup.get(neighbour_id)
        if neighbour is None:
            continue
        mycorrhizal_neighbours.append(
            {
                "entity_id": neighbour.entity_id,
                "name": flora_names.get(neighbour.species_id, f"Flora {neighbour.species_id}"),
                "x": neighbour.x,
                "y": neighbour.y,
                "inter_species": neighbour.species_id != plant.species_id,
            }
        )
    return mycorrhizal_neighbours


def _build_live_plant_payload(
    plant: PlantComponent,
    flora_names: dict[int, str],
    plant_lookup: dict[int, PlantComponent],
    owned_substances: dict[int, list[SubstanceComponent]],
    env: GridEnvironment,
    herbivore_names: dict[int, str],
    substance_names: dict[int, str],
) -> dict[str, object]:
    """Helper to construct the detailed live plant presentation structure.

    This function builds the presentation structure for a live plant, including
    its energy state, dual-proxy structural mass, fragility level, mycorrhizal connections,
    and active substances.

    Args:
        plant: The plant component.
        flora_names: The flora names.
        plant_lookup: The plant lookup.
        owned_substances: The owned substances.
        env: The grid environment.
        herbivore_names: The herbivore names.
        substance_names: The substance names.

    Returns:
        The presentation structure.
    """
    visible_substances = _get_live_substances(plant, owned_substances, env, herbivore_names, substance_names)
    mycorrhizal_neighbours = _get_live_mycorrhizal_neighbours(plant, plant_lookup, flora_names)

    struct_mass = plant.structural_mass
    max_struct = plant.max_structural_mass
    struct_ratio = struct_mass / max_struct if max_struct > 0.0 else 0.0
    struct_upkeep = plant.survival_threshold * 0.5 * min(1.0, struct_ratio) if max_struct > 0.0 else 0.0
    _fragility, fragility_pct, risk_level = calculate_structural_fragility_and_risk(struct_mass, max_struct)

    return {
        "entity_id": plant.entity_id,
        "species_id": plant.species_id,
        "name": flora_names.get(plant.species_id, f"Flora {plant.species_id}"),
        "energy": plant.energy,
        "max_energy": plant.max_energy,
        "base_energy": plant.base_energy,
        "growth_rate": plant.growth_rate,
        "energy_ratio": (plant.energy / plant.max_energy if plant.max_energy > 0.0 else 0.0),
        "energy_label": (
            f"{plant.energy:.1f} / {plant.max_energy:.1f} ({100.0 * plant.energy / plant.max_energy:.1f}%)"
            if plant.max_energy > 0.0
            else "N/A"
        ),
        "structural_mass": struct_mass,
        "max_structural_mass": max_struct,
        "structural_mass_pct": min(100.0, struct_ratio * 100.0),
        "growth_rate_structural": plant.growth_rate_structural,
        "structural_upkeep_fee": struct_upkeep,
        "fragility_pct": fragility_pct,
        "incidental_risk_level": risk_level,
        "is_woody_mature": max_struct > 0.0 and struct_mass >= max_struct,
        "camouflage": plant.camouflage,
        "camouflage_factor": plant.camouflage_factor,
        "mycorrhizal_connections": len(plant.mycorrhizal_connections),
        "mycorrhizal_neighbours": mycorrhizal_neighbours,
        "active_substances": visible_substances,
    }
