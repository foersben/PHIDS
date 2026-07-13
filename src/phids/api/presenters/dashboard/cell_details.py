"""Dashboard presenter for cell-specific details.

Assembles tooltip and sidebar payloads representing active plants, swarms,
mycorrhizal links, and diffused concentrations at a specific grid coordinate.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from phids.api.presenters.dashboard.helpers import (
    _coerce_int,
    _default_substance_name,
    _describe_activation_condition,
    validate_cell_coordinates,
)
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
    """Assemble a rich tooltip payload for a single live-simulation grid cell.

    This function traverses the ECS world and double-buffered environmental layers for cell
    ``(x, y)``, collecting all plant entities (with their owned substance components and
    mycorrhizal network neighbours), swarm entities (with energy and repellency state), and
    per-channel signal and toxin concentrations.  The result is a structured dictionary
    consumed by the HTMX tooltip partial rendered when the operator hovers over a canvas cell.

    Entity lookups are performed via O(1) spatial hash queries (``world.entities_at(x, y)``),
    preserving the architectural constraint against O(N²) distance scans.  Environmental field
    values are read directly from the NumPy read buffer of
    :class:`~phids.engine.core.biotope.GridEnvironment`.

    Args:
        loop: The active :class:`~phids.engine.loop.SimulationLoop` whose ECS world and
            environment layers are queried.
        x: Column index of the target cell.
        y: Row index of the target cell.
        substance_names: Mapping from substance identifier to display name.  Injected by the
            caller to avoid implicit dependency on module-level mutable state.

    Returns:
        A dictionary with keys ``mode``, ``tick``, ``x``, ``y``, ``grid_width``,
        ``grid_height``, ``flow_field``, ``wind``, ``signal_peak``, ``toxin_peak``,
        ``signal_concentrations``, ``toxin_concentrations``, ``mycorrhiza``,
        ``plants``, and ``swarms``.

    Raises:
        HTTPException: HTTP 404 if ``(x, y)`` lies outside the configured grid bounds.

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

    plant_lookup = {
        plant.entity_id: plant
        for entity in world.query(PlantComponent)
        for plant in [entity.get_component(PlantComponent)]
    }
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
                if substance_key in visible_keys:
                    continue
                visible_substances.append(
                    _fallback_live_substance_payload(signal_id, is_toxin=False, substance_names=substance_names)
                )
                visible_keys.add(substance_key)
            for toxin_id in range(env.num_toxins):
                if float(env.toxin_layers[toxin_id, plant.x, plant.y]) <= 0.0:
                    continue
                substance_key = (toxin_id, True)
                if substance_key in visible_keys:
                    continue
                visible_substances.append(
                    _fallback_live_substance_payload(toxin_id, is_toxin=True, substance_names=substance_names)
                )
                visible_keys.add(substance_key)
            visible_substances.sort(
                key=lambda payload: (
                    payload.get("kind") == "toxin",
                    _coerce_int(payload.get("substance_id", -1), default=-1),
                )
            )
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
            plants.append(
                {
                    "entity_id": plant.entity_id,
                    "species_id": plant.species_id,
                    "name": flora_names.get(plant.species_id, f"Flora {plant.species_id}"),
                    "energy": float(plant.energy),
                    "max_energy": float(plant.max_energy),
                    "base_energy": float(plant.base_energy),
                    "growth_rate": float(plant.growth_rate),
                    # Relative metrics for UI tooltips
                    "energy_ratio": (
                        float(plant.energy) / float(plant.max_energy) if float(plant.max_energy) > 0.0 else 0.0
                    ),
                    "energy_label": (
                        f"{plant.energy:.1f} / {plant.max_energy:.1f}"
                        f" ({100.0 * float(plant.energy) / float(plant.max_energy):.1f}%)"
                        if float(plant.max_energy) > 0.0
                        else "N/A"
                    ),
                    "camouflage": plant.camouflage,
                    "camouflage_factor": float(plant.camouflage_factor),
                    "mycorrhizal_connections": len(plant.mycorrhizal_connections),
                    "mycorrhizal_neighbours": mycorrhizal_neighbours,
                    "active_substances": visible_substances,
                }
            )

        if entity.has_component(SwarmComponent):
            swarm = entity.get_component(SwarmComponent)
            swarms.append(
                {
                    "entity_id": swarm.entity_id,
                    "species_id": swarm.species_id,
                    "name": herbivore_names.get(swarm.species_id, f"Herbivore {swarm.species_id}"),
                    "population": swarm.population,
                    "initial_population": swarm.initial_population,
                    "energy": float(swarm.energy),
                    "energy_min": float(swarm.energy_min),
                    "energy_deficit": max(
                        0.0,
                        float(swarm.population * swarm.energy_min - swarm.energy),
                    ),
                    # Relative / contextual metrics for UI tooltips
                    "starvation_threshold": float(swarm.population) * float(swarm.energy_min),
                    "energy_label": (
                        f"{swarm.energy:.1f} (Min: {float(swarm.population) * float(swarm.energy_min):.1f})"
                    ),
                    "mitosis_progress": (
                        float(swarm.population) / float(swarm.split_population_threshold)
                        if swarm.split_population_threshold > 0
                        else None
                    ),
                    "mitosis_label": (
                        f"{swarm.population} / {swarm.split_population_threshold}"
                        f" ({100.0 * float(swarm.population) / float(swarm.split_population_threshold):.0f}%)"
                        if swarm.split_population_threshold > 0
                        else "No threshold"
                    ),
                    "repelled": swarm.repelled,
                    "repelled_ticks_remaining": swarm.repelled_ticks_remaining,
                    "intoxicated": cell_toxin_peak > 0.0,
                    "signal_level": cell_signal_peak,
                    "toxin_level": cell_toxin_peak,
                }
            )

    signal_concentrations = [
        {
            "substance_id": signal_id,
            "name": substance_names.get(signal_id, _default_substance_name(signal_id, is_toxin=False)),
            "value": float(env.signal_layers[signal_id, x, y]),
            "value_pct": min(100.0, float(env.signal_layers[signal_id, x, y]) * 100.0),
        }
        for signal_id in range(env.num_signals)
        if float(env.signal_layers[signal_id, x, y]) > 0.0
    ]
    toxin_concentrations = [
        {
            "substance_id": toxin_id,
            "name": substance_names.get(toxin_id, _default_substance_name(toxin_id, is_toxin=True)),
            "value": float(env.toxin_layers[toxin_id, x, y]),
            "value_pct": min(100.0, float(env.toxin_layers[toxin_id, x, y]) * 100.0),
        }
        for toxin_id in range(env.num_toxins)
        if float(env.toxin_layers[toxin_id, x, y]) > 0.0
    ]

    return {
        "mode": "live",
        "tick": loop.tick,
        "x": x,
        "y": y,
        "grid_width": env.width,
        "grid_height": env.height,
        "flow_field": float(env.flow_field[x, y]),
        "wind": {
            "x": float(env.wind_vector_x[x, y]),
            "y": float(env.wind_vector_y[x, y]),
        },
        "signal_peak": cell_signal_peak,
        "toxin_peak": cell_toxin_peak,
        "signal_concentrations": signal_concentrations,
        "toxin_concentrations": toxin_concentrations,
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
    """Assemble a tooltip payload for a single draft (pre-simulation) grid cell.

    When no live simulation is running, the operator-facing canvas displays the draft
    placement configuration.  This function resolves all plants, swarms, and configured
    trigger rules at cell ``(x, y)`` from the provided :class:`~phids.api.ui_state.DraftState`,
    including potential mycorrhizal root links inferred from adjacent plant positions.

    The returned payload mirrors the structural contract of :func:`build_live_cell_details`
    to allow the browser tooltip component to render both modes with a single template.

    Args:
        x: Column index of the target cell.
        y: Row index of the target cell.
        draft: The server-side draft configuration to query.  Must be provided explicitly
            to decouple this function from module-level singleton state.
        substance_names: Optional mapping from substance identifier to display name.
            If ``None``, substance names are resolved exclusively from
            ``draft.substance_definitions``.

    Returns:
        A dictionary with keys ``mode`` (``"draft"``), ``tick`` (``None``), ``x``, ``y``,
        ``grid_width``, ``grid_height``, ``flow_field`` (``None``), ``wind``,
        ``signal_peak``, ``toxin_peak``, ``signal_concentrations``, ``toxin_concentrations``,
        ``mycorrhiza``, ``plants``, and ``swarms``.

    Raises:
        HTTPException: HTTP 404 if ``(x, y)`` lies outside the draft grid bounds.

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
    # Build effective substance_names from draft definitions when no explicit mapping is provided.
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
