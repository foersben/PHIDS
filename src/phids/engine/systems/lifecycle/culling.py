# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Plant culling and cleanup logic."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from phids.engine.components.plant import PlantComponent
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld


def _cull_plant_if_dead(
    plant: PlantComponent,
    world: ECSWorld,
    env: GridEnvironment,
    dead_entity_ids: set[int],
    dead_entities: list[int],
    plant_death_causes: dict[str, int] | None = None,
) -> None:
    """Check plant survival, update cause registry, and clear from spatial grids.

    Args:
        plant: The plant component to check.
        world: The ECS world.
        env: The grid environment.
        dead_entity_ids: Set of dead entity ids.
        dead_entities: List of dead entities.
        plant_death_causes: Dictionary to store death causes.
    """
    if plant.entity_id in dead_entity_ids:
        return
    if plant.energy >= plant.survival_threshold:
        return

    cause_key = plant.last_energy_loss_cause or "death_background_deficit"
    if plant_death_causes is not None:
        plant_death_causes[cause_key] = plant_death_causes.get(cause_key, 0) + 1
    env.clear_plant_energy(plant.x, plant.y, plant.species_id)
    env.clear_structural_mass(plant.x, plant.y, plant.species_id)
    world.unregister_position(plant.entity_id, plant.x, plant.y)
    dead_entity_ids.add(plant.entity_id)
    dead_entities.append(plant.entity_id)
