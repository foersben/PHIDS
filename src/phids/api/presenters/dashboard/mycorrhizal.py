# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Dashboard presenter for mycorrhizal root network links.

Defines payloads and utility functions to build and filter root communication links
between Manhattan-adjacent plant entities in both draft and live simulation modes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from phids.api.ui_state import DraftState
    from phids.engine.loop import SimulationLoop


class _MycorrhizalLinkPayload(TypedDict, total=False):
    """Serializable link payload used by draft and live mycorrhizal helpers."""

    plant_index_a: int
    plant_index_b: int
    entity_id_a: int
    entity_id_b: int
    x1: int
    y1: int
    x2: int
    y2: int
    inter_species: bool


# ---------------------------------------------------------------------------
# Mycorrhizal network link builders
# ---------------------------------------------------------------------------


def build_draft_mycorrhizal_links(draft: DraftState) -> list[_MycorrhizalLinkPayload]:
    """Infer potential mycorrhizal root links from adjacent draft plant placements.

    The mycorrhizal network in PHIDS is modelled as a graph of Manhattan-adjacent
    plant entities.  In draft mode, the live ECS world has not yet been instantiated,
    so adjacency is determined directly from the :attr:`~phids.api.ui_state.DraftState.initial_plants`
    placement list.  Two plants at Manhattan distance 1 are considered candidates for
    a root link; inter-species links are included only when
    :attr:`~phids.api.ui_state.DraftState.mycorrhizal_inter_species` is ``True``.

    Args:
        draft: The current server-side draft configuration.

    Returns:
        A list of link dictionaries, each containing ``plant_index_a``, ``plant_index_b``,
        ``x1``, ``y1``, ``x2``, ``y2``, and ``inter_species`` fields.

    """
    links: list[_MycorrhizalLinkPayload] = []
    for left_index, left in enumerate(draft.initial_plants):
        for right_index in range(left_index + 1, len(draft.initial_plants)):
            right = draft.initial_plants[right_index]
            if abs(left.x - right.x) + abs(left.y - right.y) != 1:
                continue
            inter_species = left.species_id != right.species_id
            if inter_species and not draft.mycorrhizal_inter_species:
                continue
            links.append(
                {
                    "plant_index_a": left_index,
                    "plant_index_b": right_index,
                    "x1": left.x,
                    "y1": left.y,
                    "x2": right.x,
                    "y2": right.y,
                    "inter_species": inter_species,
                }
            )
    return links


def _build_live_mycorrhizal_links(loop: SimulationLoop) -> list[_MycorrhizalLinkPayload]:
    """Serialise the unique set of root links currently active in the live ECS world.

    Each plant entity in the :class:`~phids.engine.core.ecs.ECSWorld` maintains a
    ``mycorrhizal_connections`` set of neighbour entity identifiers.  This function
    iterates over all live :class:`~phids.engine.components.plant.PlantComponent`
    instances and emits one canonical link record per unordered pair, using a
    ``seen_pairs`` set to prevent duplicate serialisation.  The resulting list is
    consumed by the canvas overlay renderer to draw the belowground network topology.

    Args:
        loop: The active simulation loop whose ECS world is queried.

    Returns:
        A list of link dictionaries containing ``entity_id_a``, ``entity_id_b``,
        ``x1``, ``y1``, ``x2``, ``y2``, and ``inter_species`` fields.

    """
    from phids.engine.components.plant import PlantComponent

    world = loop.world
    plant_lookup = {
        plant.entity_id: plant
        for entity in world.query(PlantComponent)
        for plant in [entity.get_component(PlantComponent)]
    }
    links: list[_MycorrhizalLinkPayload] = []
    seen_pairs: set[tuple[int, int]] = set()
    for plant_id, plant in plant_lookup.items():
        for neighbour_id in sorted(plant.mycorrhizal_connections):
            if neighbour_id not in plant_lookup:
                continue
            pair = (min(plant_id, neighbour_id), max(plant_id, neighbour_id))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            neighbour = plant_lookup[neighbour_id]
            links.append(
                {
                    "entity_id_a": plant_id,
                    "entity_id_b": neighbour_id,
                    "x1": plant.x,
                    "y1": plant.y,
                    "x2": neighbour.x,
                    "y2": neighbour.y,
                    "inter_species": plant.species_id != neighbour.species_id,
                }
            )
    return links


def _links_touching_cell(links: list[_MycorrhizalLinkPayload], x: int, y: int) -> list[_MycorrhizalLinkPayload]:
    """Filter a serialised link list to those whose endpoint coordinates include (x, y).

    This filter is applied when assembling the per-cell tooltip payload, ensuring that
    the mycorrhizal overlay shown for a specific cell reflects only the root links
    that are anchored at or terminate at that cell.

    Args:
        links: Serialised link records as produced by :func:`_build_live_mycorrhizal_links`
            or :func:`build_draft_mycorrhizal_links`.
        x: Target column index.
        y: Target row index.

    Returns:
        The subset of ``links`` where either endpoint matches ``(x, y)``.

    """
    return [link for link in links if (link["x1"] == x and link["y1"] == y) or (link["x2"] == x and link["y2"] == y)]


# ---------------------------------------------------------------------------
# Public presenter functions
# ---------------------------------------------------------------------------
