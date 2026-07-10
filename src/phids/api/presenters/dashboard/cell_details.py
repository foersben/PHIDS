from __future__ import annotations

from typing import TYPE_CHECKING

from phids.api.presenters.dashboard.helpers import _coerce_int, _default_substance_name, validate_cell_coordinates
from phids.api.presenters.dashboard.mycorrhizal import (
    _build_live_mycorrhizal_links,
    _links_touching_cell,
    build_draft_mycorrhizal_links,
)
from phids.api.presenters.dashboard.substances import (
    _fallback_live_substance_payload,
    _is_live_substance_visible,
    _serialize_live_substance,
)

if TYPE_CHECKING:
    from phids.api.ui_state import DraftState, TriggerRule
    from phids.engine.components.substances import SubstanceComponent
    from phids.engine.loop import SimulationLoop


def build_live_cell_details(
    loop: SimulationLoop,
    x: int,
    y: int,
    *,
    substance_names: dict[int, str],
) -> dict[str, object]:
    """Build the detailed JSON payload for a single cell in a live simulation.

    This presenter merges physical layer data (signal and toxin peaks), entity
    component state (substance inventories, energy, population), and topological
    networks (mycorrhizal connections) for all entities coincident at the given
    coordinate.

    Args:
        loop: The active :class:`~phids.engine.loop.SimulationLoop` instance.
        x: Column coordinate of the queried cell.
        y: Row coordinate of the queried cell.
        substance_names: A mapping from numeric substance IDs to human-readable names.

    Returns:
        A dictionary matching the HTMX UI schema for the cell details modal.
    """
    from phids.engine.components.plant import PlantComponent
    from phids.engine.components.substances import SubstanceComponent
    from phids.engine.components.swarm import SwarmComponent

    env = loop.env
    world = loop.world
    validate_cell_coordinates(x, y, env.width, env.height)

    flora_names = {species.species_id: species.name for species in loop.config.flora_species}
    herbivore_names = {species.species_id: species.name for species in loop.config.herbivore_species}

    owned_substances: dict[int, list[SubstanceComponent]] = {}
    for entity in world.query(SubstanceComponent):
        substance = entity.get_component(SubstanceComponent)
        owned_substances.setdefault(substance.owner_plant_id, []).append(substance)

    live_links = _build_live_mycorrhizal_links(loop)
    touching_links = _links_touching_cell(live_links, x, y)

    plants: list[dict[str, object]] = []
    swarms: list[dict[str, object]] = []

    cell_signal_peak = float(env.signal_layers[:, x, y].max()) if env.num_signals > 0 else 0.0
    cell_toxin_peak = float(env.toxin_layers[:, x, y].max()) if env.num_toxins > 0 else 0.0

    for entity_id in sorted(world.entities_at(x, y)):
        if not world.has_entity(entity_id):
            continue
        entity = world.get_entity(entity_id)

        if entity.has_component(PlantComponent):
            plant = entity.get_component(PlantComponent)
            plant_substances = sorted(
                (
                    substance
                    for substance in owned_substances.get(plant.entity_id, [])
                    if _is_live_substance_visible(substance)
                ),
                key=lambda substance: (substance.is_toxin, substance.substance_id),
            )
            visible_substances = [
                _serialize_live_substance(
                    substance,
                    herbivore_names=herbivore_names,
                    substance_names=substance_names,
                )
                for substance in plant_substances
            ]
            visible_keys = {
                (
                    _coerce_int(payload.get("substance_id", -1), default=-1),
                    payload.get("kind") == "toxin",
                )
                for payload in visible_substances
            }
            for signal_id in range(env.num_signals):
                if float(env.signal_layers[signal_id, plant.x, plant.y]) <= 0.0:
                    continue
                substance_key = (signal_id, False)
                if substance_key not in visible_keys:
                    visible_substances.append(
                        _fallback_live_substance_payload(signal_id, is_toxin=False, substance_names=substance_names)
                    )
            for toxin_id in range(env.num_toxins):
                if float(env.toxin_layers[toxin_id, plant.x, plant.y]) <= 0.0:
                    continue
                substance_key = (toxin_id, True)
                if substance_key not in visible_keys:
                    visible_substances.append(
                        _fallback_live_substance_payload(toxin_id, is_toxin=True, substance_names=substance_names)
                    )

            mycorrhizal_neighbours = []
            for link in touching_links:
                is_left = int(link["x1"]) == plant.x and int(link["y1"]) == plant.y
                is_right = int(link["x2"]) == plant.x and int(link["y2"]) == plant.y
                if not is_left and not is_right:
                    continue
                nx = int(link["x2"] if is_left else link["x1"])
                ny = int(link["y2"] if is_left else link["y1"])
                for nid in world.entities_at(nx, ny):
                    if not world.has_entity(nid):
                        continue
                    n_entity = world.get_entity(nid)
                    if n_entity.has_component(PlantComponent):
                        n_plant = n_entity.get_component(PlantComponent)
                        if (
                            n_plant.entity_id in plant.mycorrhizal_connections
                            or plant.entity_id in n_plant.mycorrhizal_connections
                        ):
                            mycorrhizal_neighbours.append(
                                {
                                    "entity_id": n_plant.entity_id,
                                    "name": flora_names.get(n_plant.species_id, f"Flora {n_plant.species_id}"),
                                    "x": n_plant.x,
                                    "y": n_plant.y,
                                    "inter_species": plant.species_id != n_plant.species_id,
                                }
                            )

            plants.append(
                {
                    "entity_id": plant.entity_id,
                    "species_id": plant.species_id,
                    "name": flora_names.get(plant.species_id, f"Flora {plant.species_id}"),
                    "energy": float(plant.energy),
                    "mycorrhizal_connections": len(plant.mycorrhizal_connections),
                    "mycorrhizal_neighbours": mycorrhizal_neighbours,
                    "configured_trigger_rules": [],
                    "active_substances": visible_substances,
                }
            )
        elif entity.has_component(SwarmComponent):
            swarm = entity.get_component(SwarmComponent)
            swarms.append(
                {
                    "entity_id": swarm.entity_id,
                    "species_id": swarm.species_id,
                    "name": herbivore_names.get(swarm.species_id, f"Herbivore {swarm.species_id}"),
                    "population": swarm.population,
                    "energy": float(swarm.energy),
                    "repelled": swarm.repelled,
                    "local_toxin_exposure": (float(env.toxin_layers[:, x, y].max()) if env.num_toxins > 0 else 0.0),
                }
            )

    return {
        "mode": "live",
        "tick": loop.tick,
        "x": x,
        "y": y,
        "grid_width": env.width,
        "grid_height": env.height,
        "flow_field": float(env.flow_field[x, y]),
        "wind": {"x": env.wind_vector_x[x, y], "y": env.wind_vector_y[x, y]},
        "signal_peak": cell_signal_peak,
        "toxin_peak": cell_toxin_peak,
        "signal_concentrations": [
            {
                "substance_id": i,
                "name": substance_names.get(i, _default_substance_name(i, is_toxin=False)),
                "concentration": float(env.signal_layers[i, x, y]),
            }
            for i in range(env.num_signals)
        ],
        "toxin_concentrations": [
            {
                "substance_id": i,
                "name": substance_names.get(i, _default_substance_name(i, is_toxin=True)),
                "concentration": float(env.toxin_layers[i, x, y]),
            }
            for i in range(env.num_toxins)
        ],
        "mycorrhiza": {
            "enabled": bool(touching_links),
            "link_count": len(touching_links),
            "inter_species_enabled": loop.config.mycorrhizal_inter_species,
            "connection_cost": float(loop.config.mycorrhizal_connection_cost),
            "signal_velocity": loop.config.mycorrhizal_signal_velocity,
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


def build_preview_cell_details(
    x: int,
    y: int,
    *,
    draft: DraftState,
    substance_names: dict[int, str] | None = None,
) -> dict[str, object]:
    """Build the detailed JSON payload for a single cell in the draft editor.

    Unlike the live simulation payload, draft details do not include dynamic
    engine state (like energy gradients or field diffusion). Instead, they map
    configuration primitives (such as unresolved trigger rules) into the UI schema
    so the operator can preview spatial rules before scenario initialization.

    Args:
        x: Column coordinate of the queried cell.
        y: Row coordinate of the queried cell.
        draft: The current :class:`~phids.api.ui_state.DraftState`.
        substance_names: Optional explicit substance name mapping. If not provided,
            it is derived dynamically from the draft definitions.

    Returns:
        A dictionary matching the HTMX UI schema for the draft cell preview modal.
    """
    validate_cell_coordinates(x, y, draft.grid_width, draft.grid_height)

    flora_names = {
        getattr(species, "species_id", index): getattr(species, "name", f"Flora {index}")
        for index, species in enumerate(draft.flora_species)
    }
    herbivore_names = {
        getattr(species, "species_id", index): getattr(species, "name", f"Herbivore {index}")
        for index, species in enumerate(draft.herbivore_species)
    }
    substances = {definition.substance_id: definition for definition in draft.substance_definitions}
    effective_substance_names: dict[int, str] = (
        substance_names
        if substance_names is not None
        else {definition.substance_id: definition.name for definition in draft.substance_definitions}
    )

    rules_by_flora: dict[int, list[TriggerRule]] = {}
    for rule in draft.trigger_rules:
        rules_by_flora.setdefault(rule.flora_species_id, []).append(rule)

    preview_links = build_draft_mycorrhizal_links(draft)
    touching_links = _links_touching_cell(preview_links, x, y)

    plants: list[dict[str, object]] = []
    for index, plant in enumerate(draft.initial_plants):
        if plant.x != x or plant.y != y:
            continue
        mycorrhizal_neighbours = []
        for link in preview_links:
            is_left = int(link["plant_index_a"]) == index
            is_right = int(link["plant_index_b"]) == index
            if not is_left and not is_right:
                continue
            _other_index = int(link["plant_index_b"] if is_left else link["plant_index_a"])
            other = draft.initial_plants[_other_index]
            mycorrhizal_neighbours.append(
                {
                    "name": flora_names.get(other.species_id, f"Flora {other.species_id}"),
                    "x": other.x,
                    "y": other.y,
                    "inter_species": bool(link["inter_species"]),
                }
            )
        from phids.api.presenters.dashboard.helpers import _describe_activation_condition

        plants.append(
            {
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
                        "activation_condition_summary": _describe_activation_condition(
                            rule.activation_condition,
                            herbivore_names=herbivore_names,
                            substance_names=effective_substance_names,
                        ),
                        "activation_condition": rule.activation_condition,
                    }
                    for rule in rules_by_flora.get(plant.species_id, [])
                ],
                "active_substances": [],
            }
        )

    swarms = [
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
