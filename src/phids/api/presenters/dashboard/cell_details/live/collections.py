# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Live cell collections module."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from phids.api.presenters.dashboard.cell_details.live.plants import _build_live_plant_payload
from phids.api.presenters.dashboard.cell_details.live.swarms import _build_live_swarm_payload
from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent

if TYPE_CHECKING:
    from phids.engine.components.substances import SubstanceComponent
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld


def _collect_live_plants_and_swarms(
    x: int,
    y: int,
    world: ECSWorld,
    env: GridEnvironment,
    flora_names: dict[int, str],
    herbivore_names: dict[int, str],
    herbivore_params: dict[int, Any],
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
        herbivore_params: A dictionary mapping herbivore species IDs to their params.
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
    cell_plant_energy = 0.0
    for entity_id in sorted(world.entities_at(x, y)):
        if not world.has_entity(entity_id):
            continue
        entity = world.get_entity(entity_id)
        if entity.has_component(PlantComponent):
            plant = entity.get_component(PlantComponent)
            cell_plant_energy += plant.energy
            plants.append(
                _build_live_plant_payload(
                    plant, flora_names, plant_lookup, owned_substances, env, herbivore_names, substance_names
                )
            )

    for entity_id in sorted(world.entities_at(x, y)):
        if not world.has_entity(entity_id):
            continue
        entity = world.get_entity(entity_id)
        if entity.has_component(SwarmComponent):
            swarm = entity.get_component(SwarmComponent)
            swarms.append(
                _build_live_swarm_payload(
                    swarm,
                    herbivore_names,
                    herbivore_params,
                    cell_toxin_peak,
                    cell_signal_peak,
                    cell_plant_energy,
                )
            )
    return plants, swarms
