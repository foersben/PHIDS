# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Mycorrhiza live cell details extraction."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from phids.engine.components.plant import PlantComponent


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
