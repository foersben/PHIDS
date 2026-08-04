# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Dashboard presenter for cell-specific details.

Assembles tooltip and sidebar payloads representing active plants, swarms,
mycorrhizal links, and diffused concentrations at a specific grid coordinate.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from phids.api.presenters.dashboard.mycorrhizal import (
    _build_live_mycorrhizal_links,
    _links_touching_cell,
)
from phids.api.presenters.dashboard.shared import (
    _coerce_int,
    _default_substance_name,
    validate_cell_coordinates,
)
from phids.api.presenters.dashboard.substances import (
    _fallback_live_substance_payload,
    _is_live_substance_visible,
    _serialize_live_substance,
)
from phids.engine.components.plant import PlantComponent
from phids.engine.components.substances import SubstanceComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.biotope import GridEnvironment

if TYPE_CHECKING:
    from phids.engine.components.substances import SubstanceComponent
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld
    from phids.engine.loop import SimulationLoop


def _get_live_substances(
    plant: PlantComponent,
    owned_substances: dict[int, list[SubstanceComponent]],
    env: GridEnvironment,
    herbivore_names: dict[int, str],
    substance_names: dict[int, str],
) -> list[dict[str, object]]:
    """Helper to collect and serialize visible active substances on a plant.

    This function gathers and serializes all active substances located on a plant, including
    both those directly owned by the plant entity and those diffused into the environment at
    the plant's location. It filters out invisible substances (e.g., toxins below threshold)
    and ensures consistent payload formatting for the UI.

    Args:
        plant: The plant component.
        owned_substances: The owned substances.
        env: The grid environment.
        herbivore_names: The herbivore names.
        substance_names: The substance names.

    Returns:
        The list of visible active substances.
    """
    plant_substances = sorted(
        (substance for substance in owned_substances.get(plant.entity_id, []) if _is_live_substance_visible(substance)),
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
    return visible_substances


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
    its energy state, camouflage, mycorrhizal connections, and active substances.

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
    return {
        "entity_id": plant.entity_id,
        "species_id": plant.species_id,
        "name": flora_names.get(plant.species_id, f"Flora {plant.species_id}"),
        "energy": float(plant.energy),
        "max_energy": float(plant.max_energy),
        "base_energy": float(plant.base_energy),
        "growth_rate": float(plant.growth_rate),
        "energy_ratio": (float(plant.energy) / float(plant.max_energy) if float(plant.max_energy) > 0.0 else 0.0),
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


def _build_live_swarm_payload(
    swarm: SwarmComponent,
    herbivore_names: dict[int, str],
    cell_toxin_peak: float,
    cell_signal_peak: float,
) -> dict[str, object]:
    """Helper to construct the detailed live swarm presentation structure.

    Args:
        swarm: The swarm component.
        herbivore_names: The herbivore names.
        cell_toxin_peak: The toxin peak in the cell.
        cell_signal_peak: The signal peak in the cell.

    Returns:
        The presentation structure.
    """
    return {
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
        "starvation_threshold": float(swarm.population) * float(swarm.energy_min),
        "energy_label": (f"{swarm.energy:.1f} (Min: {float(swarm.population) * float(swarm.energy_min):.1f})"),
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


def _collect_live_plants_and_swarms(
    x: int,
    y: int,
    world: ECSWorld,
    env: GridEnvironment,
    flora_names: dict[int, str],
    herbivore_names: dict[int, str],
    plant_lookup: dict[int, PlantComponent],
    owned_substances: dict[int, list[SubstanceComponent]],
    substance_names: dict[int, str],
    cell_toxin_peak: float,
    cell_signal_peak: float,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Helper to query the ECS registry and serialize co-located plants and swarms.

    Args:
        x: The x-coordinate of the cell.
        y: The y-coordinate of the cell.
        world: The ECS world.
        env: The grid environment.
        flora_names: A dictionary mapping flora species IDs to their names.
        herbivore_names: A dictionary mapping herbivore species IDs to their names.
        plant_lookup: A dictionary mapping plant entity IDs to their plant components.
        owned_substances: A dictionary mapping herbivore entity IDs to their owned substances.
        substance_names: A dictionary mapping substance IDs to their names.
        cell_toxin_peak: The peak toxin level in the cell.
        cell_signal_peak: The peak signal level in the cell.

    Returns:
        A tuple containing a list of plants and a list of swarms.
    """
    plants = []
    swarms = []
    for entity_id in sorted(world.entities_at(x, y)):
        if not world.has_entity(entity_id):
            continue
        entity = world.get_entity(entity_id)

        if entity.has_component(PlantComponent):
            plant = entity.get_component(PlantComponent)
            plants.append(
                _build_live_plant_payload(
                    plant, flora_names, plant_lookup, owned_substances, env, herbivore_names, substance_names
                )
            )

        if entity.has_component(SwarmComponent):
            swarm = entity.get_component(SwarmComponent)
            swarms.append(_build_live_swarm_payload(swarm, herbivore_names, cell_toxin_peak, cell_signal_peak))
    return plants, swarms


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

    cell_signal_peak = float(env.signal_layers[:, x, y].max()) if env.num_signals > 0 else 0.0
    cell_toxin_peak = float(env.toxin_layers[:, x, y].max()) if env.num_toxins > 0 else 0.0

    plants, swarms = _collect_live_plants_and_swarms(
        x,
        y,
        world,
        env,
        flora_names,
        herbivore_names,
        plant_lookup,
        owned_substances,
        substance_names,
        cell_toxin_peak,
        cell_signal_peak,
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
