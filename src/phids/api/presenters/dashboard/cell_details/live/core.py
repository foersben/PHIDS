# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Dashboard presenter for cell-specific details.

Assembles tooltip and sidebar payloads representing active plants, swarms,
mycorrhizal links, and diffused concentrations at a specific grid coordinate.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from phids.api.presenters.dashboard.cell_details.live.collections import (
    _collect_live_plants_and_swarms,
)
from phids.api.presenters.dashboard.mycorrhizal import (
    _build_live_mycorrhizal_links_for_cell,
)
from phids.api.presenters.dashboard.shared import (
    _default_substance_name,
    validate_cell_coordinates,
)

if TYPE_CHECKING:
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

    env = loop.env
    world = loop.world
    validate_cell_coordinates(x, y, env.width, env.height)

    flora_names = {species.species_id: species.name for species in loop.config.flora_species}
    herbivore_names = {species.species_id: species.name for species in loop.config.herbivore_species}
    herbivore_params = {species.species_id: species for species in loop.config.herbivore_species}

    owned_substances: dict[int, list[SubstanceComponent]] = {}
    for entity in world.query(SubstanceComponent):
        substance = entity.get_component(SubstanceComponent)
        owned_substances.setdefault(substance.owner_plant_id, []).append(substance)

    plant_lookup = {
        plant.entity_id: plant
        for entity in world.query(PlantComponent)
        for plant in [entity.get_component(PlantComponent)]
    }
    touching_links = _build_live_mycorrhizal_links_for_cell(loop, x, y)

    cell_signal_peak = float(env.signal_layers[:, x, y].max()) if env.num_signals > 0 else 0.0
    cell_toxin_peak = float(env.toxin_layers[:, x, y].max()) if env.num_toxins > 0 else 0.0

    plants, swarms = _collect_live_plants_and_swarms(
        x,
        y,
        world,
        env,
        flora_names,
        herbivore_names,
        herbivore_params,
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
            "connection_cost": loop.config.mycorrhizal_connection_cost,
            "signal_velocity": loop.config.mycorrhizal_signal_velocity,
            "links": [
                {
                    "from": {"x": link["x1"], "y": link["y1"]},
                    "to": {"x": link["x2"], "y": link["y2"]},
                    "inter_species": link["inter_species"],
                }
                for link in touching_links
            ],
        },
        "plants": plants,
        "swarms": swarms,
    }
