# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Dashboard presenter for cell-specific details.

Assembles tooltip and sidebar payloads representing active plants, swarms,
mycorrhizal links, and diffused concentrations at a specific grid coordinate.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from phids.api.presenters.dashboard.mycorrhizal import (
    _links_touching_cell,
    _MycorrhizalLinkPayload,
    build_draft_mycorrhizal_links,
)
from phids.api.presenters.dashboard.shared import (
    _default_substance_name,
    _describe_activation_condition,
    validate_cell_coordinates,
)

if TYPE_CHECKING:
    from phids.api.ui_state.placements import PlacedPlant
    from phids.api.ui_state.state import DraftState
    from phids.api.ui_state.substances import SubstanceDefinition
    from phids.api.ui_state.triggers import TriggerRule


def _build_preview_plant_payload(
    index: int,
    plant: PlacedPlant,
    draft: DraftState,
    preview_links: list[_MycorrhizalLinkPayload],
    flora_names: dict[int, str],
    herbivore_names: dict[int, str],
    substances: dict[int, SubstanceDefinition],
    effective_substance_names: dict[int, str],
    rules_by_flora: dict[int, list[TriggerRule]],
) -> dict[str, object]:
    """Helper to construct the detailed draft plant presentation structure.

    The result is computed without reference to live simulation data: it reflects only the initial
    configuration and neighbor relationships at the moment the draft was created.

    Args:
        index: The index of the plant.
        plant: The plant component.
        draft: The draft state.
        preview_links: A list of mycorrhizal links.
        flora_names: A dictionary mapping flora species IDs to their names.
        herbivore_names: A dictionary mapping herbivore species IDs to their names.
        substances: A dictionary mapping substance IDs to their definitions.
        effective_substance_names: A dictionary mapping substance IDs to their effective names.
        rules_by_flora: A dictionary mapping flora species IDs to their trigger rules.

    Returns:
        A dictionary containing the plant presentation structure.
    """
    mycorrhizal_neighbours = []
    for link in preview_links:
        is_left = int(link["plant_index_a"]) == index
        is_right = int(link["plant_index_b"]) == index
        if not is_left and not is_right:
            continue
        other_index = int(link["plant_index_b"] if is_left else link["plant_index_a"])
        other = draft.initial_plants[other_index]
        mycorrhizal_neighbours.append(
            {
                "name": flora_names.get(other.species_id, f"Flora {other.species_id}"),
                "x": other.x,
                "y": other.y,
                "inter_species": bool(link["inter_species"]),
            }
        )
    return {
        "index": index,
        "species_id": plant.species_id,
        "name": flora_names.get(plant.species_id, f"Flora {plant.species_id}"),
        "energy": float(plant.energy),
        "mycorrhizal_connections": len(mycorrhizal_neighbours),
        "mycorrhizal_neighbours": mycorrhizal_neighbours,
        "configured_trigger_rules": [
            {
                "substance_id": rule.substance_id,
                "substance_name": (
                    substances[rule.substance_id].name
                    if rule.substance_id in substances
                    else _default_substance_name(rule.substance_id, is_toxin=False)
                ),
                "herbivore_species_id": rule.herbivore_species_id,
                "herbivore_name": herbivore_names.get(
                    rule.herbivore_species_id,
                    f"Herbivore {rule.herbivore_species_id}",
                ),
                "min_herbivore_population": rule.min_herbivore_population,
                "activation_condition": rule.activation_condition,
                "activation_condition_summary": _describe_activation_condition(
                    rule.activation_condition,
                    herbivore_names=herbivore_names,
                    substance_names=effective_substance_names,
                ),
            }
            for rule in rules_by_flora.get(plant.species_id, [])
        ],
    }


def _collect_preview_plants(
    x: int,
    y: int,
    draft: DraftState,
    preview_links: list[_MycorrhizalLinkPayload],
    flora_names: dict[int, str],
    herbivore_names: dict[int, str],
    substances: dict[int, SubstanceDefinition],
    effective_substance_names: dict[int, str],
    rules_by_flora: dict[int, list[TriggerRule]],
) -> list[dict[str, object]]:
    """Helper to collect and serialize draft plants at a target cell.

    Filters plants by coordinates and delegates per-plant formatting to
    `_build_preview_plant_payload`; used by `get_cell_details` to populate the
    "plants" list in the cell-details payload when the active view is a draft
    layout rather than a live simulation snapshot.

    Args:
        x: The x coordinate of the cell.
        y: The y coordinate of the cell.
        draft: The draft state.
        preview_links: A list of mycorrhizal links.
        flora_names: A dictionary mapping flora species IDs to their names.
        herbivore_names: A dictionary mapping herbivore species IDs to their names.
        substances: A dictionary mapping substance IDs to their definitions.
        effective_substance_names: A dictionary mapping substance IDs to their effective names.
        rules_by_flora: A dictionary mapping flora species IDs to their trigger rules.

    Returns:
        A list of dictionaries containing the plant presentation structure.
    """
    plants = []
    for index, plant in enumerate(draft.initial_plants):
        if plant.x != x or plant.y != y:
            continue
        plants.append(
            _build_preview_plant_payload(
                index,
                plant,
                draft,
                preview_links,
                flora_names,
                herbivore_names,
                substances,
                effective_substance_names,
                rules_by_flora,
            )
        )
    return plants


def _prepare_draft_metadata(
    draft: DraftState,
    substance_names: dict[int, str] | None,
) -> tuple[
    dict[int, str],
    dict[int, str],
    dict[int, SubstanceDefinition],
    dict[int, str],
    dict[int, list[TriggerRule]],
]:
    """Prepare and index flora, herbivore, and trigger rule metadata from draft state.

    Args:
        draft: The draft state.
        substance_names: The substance names.

    Returns:
        A tuple containing the flora names, herbivore names, substances, effective substance names, and trigger rules.
    """
    flora_names: dict[int, str] = {
        getattr(species, "species_id", index): getattr(species, "name", f"Flora {index}")
        for index, species in enumerate(draft.flora_species)
    }
    herbivore_names: dict[int, str] = {
        getattr(species, "species_id", index): getattr(species, "name", f"Herbivore {index}")
        for index, species in enumerate(draft.herbivore_species)
    }
    substances = {definition.substance_id: definition for definition in draft.substance_definitions}
    effective_substance_names = (
        substance_names
        if substance_names is not None
        else {definition.substance_id: definition.name for definition in draft.substance_definitions}
    )

    rules_by_flora: dict[int, list[TriggerRule]] = {}
    for rule in draft.trigger_rules:
        rules_by_flora.setdefault(rule.flora_species_id, []).append(rule)

    return flora_names, herbivore_names, substances, effective_substance_names, rules_by_flora


def _collect_preview_swarms(
    x: int,
    y: int,
    draft: DraftState,
    herbivore_names: dict[int, str],
) -> list[dict[str, object]]:
    """Helper to collect and serialize draft swarms at a target cell.

    Args:
        x: The x coordinate of the cell.
        y: The y coordinate of the cell.
        draft: The draft state.
        herbivore_names: The herbivore names.

    Returns:
        The list of draft swarms.
    """
    return [
        {
            "index": index,
            "species_id": swarm.species_id,
            "name": herbivore_names.get(swarm.species_id, f"Herbivore {swarm.species_id}"),
            "population": swarm.population,
            "energy": float(swarm.energy),
        }
        for index, swarm in enumerate(draft.initial_swarms)
        if swarm.x == x and swarm.y == y
    ]


def build_preview_cell_details(
    x: int,
    y: int,
    *,
    draft: DraftState,
    substance_names: dict[int, str] | None = None,
) -> dict[str, object]:
    """Assemble a tooltip payload for a single draft (pre-simulation) grid cell.

    Args:
        x: The x coordinate of the cell.
        y: The y coordinate of the cell.
        draft: The draft state.
        substance_names: The substance names.

    Returns:
        The presentation structure.
    """
    validate_cell_coordinates(x, y, draft.grid_width, draft.grid_height)

    flora_names, herbivore_names, substances, effective_substance_names, rules_by_flora = _prepare_draft_metadata(
        draft, substance_names
    )

    preview_links = build_draft_mycorrhizal_links(draft)
    touching_links = _links_touching_cell(preview_links, x, y)

    plants = _collect_preview_plants(
        x, y, draft, preview_links, flora_names, herbivore_names, substances, effective_substance_names, rules_by_flora
    )

    swarms = _collect_preview_swarms(x, y, draft, herbivore_names)

    return {
        "mode": "draft",
        "tick": None,
        "x": x,
        "y": y,
        "grid_width": draft.grid_width,
        "grid_height": draft.grid_height,
        "flow_field": None,
        "wind": {"x": draft.wind_x, "y": draft.wind_y},
        "signal_peak": 0.0,
        "toxin_peak": 0.0,
        "signal_concentrations": [],
        "toxin_concentrations": [],
        "mycorrhiza": {
            "enabled": bool(touching_links),
            "link_count": len(touching_links),
            "inter_species_enabled": draft.mycorrhizal_inter_species,
            "connection_cost": float(draft.mycorrhizal_connection_cost),
            "signal_velocity": draft.mycorrhizal_signal_velocity,
            "links": [
                {
                    "from": {"x": int(link["x1"]), "y": int(link["y1"])},
                    "to": {"x": int(link["x2"]), "y": int(link["y2"])},
                    "inter_species": bool(link["inter_species"]),
                }
                for link in touching_links
            ],
        },
        "plants": plants,
        "swarms": swarms,
    }
