"""Mycorrhizal link presentation layer.

This module isolates the logic for extracting, mapping, and serialising mycorrhizal network
connections from both the draft scenario state and the live ECS runtime environment.
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


def build_draft_mycorrhizal_links(draft: DraftState) -> list[_MycorrhizalLinkPayload]:
    """Infer potential mycorrhizal root links from adjacent draft plant placements.

    In the draft state, plants do not possess active ECS components. Instead, the network
    is predicted by evaluating Moore neighbourhood adjacency across the ``initial_plants``
    collection. If inter-species networking is disabled in the draft configuration, adjacent
    plants of differing species are skipped.

    Args:
        draft: The current draft scenario state.

    Returns:
        A list of serialised link dictionaries suitable for JSON serialisation and canvas
        overlay rendering. Duplicate bi-directional links are deduplicated.
    """
    links: list[_MycorrhizalLinkPayload] = []
    plants = draft.initial_plants
    for idx_a, plant_a in enumerate(plants):
        for idx_b, plant_b in enumerate(plants):
            if idx_b <= idx_a:
                continue
            dx = abs(plant_a.x - plant_b.x)
            dy = abs(plant_a.y - plant_b.y)
            if dx + dy == 1:
                inter_species = plant_a.species_id != plant_b.species_id
                if inter_species and not draft.mycorrhizal_inter_species:
                    continue
                links.append(
                    _MycorrhizalLinkPayload(
                        plant_index_a=idx_a,
                        plant_index_b=idx_b,
                        x1=plant_a.x,
                        y1=plant_a.y,
                        x2=plant_b.x,
                        y2=plant_b.y,
                        inter_species=inter_species,
                    )
                )
    return links


def _build_live_mycorrhizal_links(loop: SimulationLoop) -> list[_MycorrhizalLinkPayload]:
    """Serialise the unique set of root links currently active in the live ECS world.

    This function iterates through all :class:`~phids.engine.components.plant.PlantComponent`
    instances, traversing their explicit ``mycorrhizal_connections`` adjacency lists.
    To prevent the renderer from drawing overlapping lines, each bi-directional connection
    is sorted by entity ID and emitted exactly once.

    Args:
        loop: The active :class:`~phids.engine.loop.SimulationLoop` whose ECS world is
            interrogated.

    Returns:
        A deduplicated list of serialised root link dictionaries.
    """
    from phids.engine.components.plant import PlantComponent

    world = loop.world
    plant_lookup = {
        plant.entity_id: plant
        for entity in world.query(PlantComponent)
        for plant in [entity.get_component(PlantComponent)]
    }
    seen_links = set()
    links: list[_MycorrhizalLinkPayload] = []
    for plant_id, plant in plant_lookup.items():
        for neighbour_id in sorted(plant.mycorrhizal_connections):
            if neighbour_id not in plant_lookup:
                continue
            neighbour = plant_lookup[neighbour_id]
            link_key = tuple(sorted([plant_id, neighbour_id]))
            if link_key in seen_links:
                continue
            seen_links.add(link_key)
            links.append(
                _MycorrhizalLinkPayload(
                    entity_id_a=plant_id,
                    entity_id_b=neighbour_id,
                    x1=plant.x,
                    y1=plant.y,
                    x2=neighbour.x,
                    y2=neighbour.y,
                    inter_species=plant.species_id != neighbour.species_id,
                )
            )
    return links


def _links_touching_cell(links: list[_MycorrhizalLinkPayload], x: int, y: int) -> list[_MycorrhizalLinkPayload]:
    """Filter a serialised link list to those whose endpoint coordinates include (x, y).

    Used by the tooltip presenter routines to determine which network connections
    involve the cell currently hovered by the operator.

    Args:
        links: Complete list of active network links.
        x: Column index of the target cell.
        y: Row index of the target cell.

    Returns:
        A subset list containing only those links anchored at ``(x, y)``.
    """
    return [link for link in links if (link["x1"] == x and link["y1"] == y) or (link["x2"] == x and link["y2"] == y)]
