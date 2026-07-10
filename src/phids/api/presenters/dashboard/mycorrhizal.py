from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from phids.api.ui_state import DraftState
    from phids.engine.loop import SimulationLoop


class _MycorrhizalLinkPayload(TypedDict, total=False):
    x1: float
    y1: float
    x2: float
    y2: float
    inter_species: bool
    plant_index_a: int
    plant_index_b: int


def build_draft_mycorrhizal_links(draft: DraftState) -> list[_MycorrhizalLinkPayload]:
    """Generate rendering vectors for potential mycorrhizal networks in draft mode.

    The engine determines valid connections spatially via Manhattan distance at the moment
    of scenario compilation. Because the engine does not exist in draft mode, this
    function statically evaluates spatial proximity across the draft placements to preview
    which plants will form shared root networks.

    Args:
        draft: The current :class:`~phids.api.ui_state.DraftState`.

    Returns:
        A list of link dictionaries containing spatial coordinates and network metadata.
    """
    if not draft.mycorrhizal_inter_species and not any(p.species_id for p in draft.initial_plants):
        pass

    coords: set[tuple[int, int]] = {(p.x, p.y) for p in draft.initial_plants}
    species_map: dict[tuple[int, int], int] = {(p.x, p.y): p.species_id for p in draft.initial_plants}
    index_map: dict[tuple[int, int], int] = {(p.x, p.y): idx for idx, p in enumerate(draft.initial_plants)}

    links: list[_MycorrhizalLinkPayload] = []
    seen: set[tuple[int, int]] = set()

    for x, y in coords:
        s1 = species_map[(x, y)]
        idx1 = index_map[(x, y)]
        for dx, dy in ((1, 0), (0, 1)):
            nx, ny = x + dx, y + dy
            if (nx, ny) in coords:
                s2 = species_map[(nx, ny)]
                idx2 = index_map[(nx, ny)]
                inter = s1 != s2
                if inter and not draft.mycorrhizal_inter_species:
                    continue
                pair = tuple(sorted((idx1, idx2)))
                if pair in seen:
                    continue
                seen.add(pair)

                links.append(
                    {
                        "x1": float(x),
                        "y1": float(y),
                        "x2": float(nx),
                        "y2": float(ny),
                        "inter_species": inter,
                        "plant_index_a": idx1,
                        "plant_index_b": idx2,
                    }
                )
    return links


def _build_live_mycorrhizal_links(loop: SimulationLoop) -> list[_MycorrhizalLinkPayload]:
    from phids.engine.components.plant import PlantComponent

    world = loop.world
    links: list[_MycorrhizalLinkPayload] = []
    seen: set[tuple[int, int]] = set()

    for entity in world.query(PlantComponent):
        plant = entity.get_component(PlantComponent)
        s1 = plant.species_id
        for target_id in plant.mycorrhizal_connections:
            pair = tuple(sorted((plant.entity_id, target_id)))
            if pair in seen:
                continue
            seen.add(pair)

            if not world.has_entity(target_id):
                continue
            target_entity = world.get_entity(target_id)
            if not target_entity.has_component(PlantComponent):
                continue
            target = target_entity.get_component(PlantComponent)
            links.append(
                {
                    "x1": float(plant.x),
                    "y1": float(plant.y),
                    "x2": float(target.x),
                    "y2": float(target.y),
                    "inter_species": s1 != target.species_id,
                }
            )
    return links


def _links_touching_cell(links: list[_MycorrhizalLinkPayload], x: int, y: int) -> list[_MycorrhizalLinkPayload]:
    return [
        link
        for link in links
        if (int(link["x1"]) == x and int(link["y1"]) == y) or (int(link["x2"]) == x and int(link["y2"]) == y)
    ]
