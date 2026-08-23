# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Trigger evaluation logic for the signaling system."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from phids.engine.components.plant import PlantComponent
from phids.engine.systems.signaling.triggers.batch import _evaluate_trigger_batch

if TYPE_CHECKING:
    from phids.engine.components.substances import SubstanceComponent
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld, Entity
    from phids.engine.systems.signaling.spatial import SwarmPopulationIndex
    from phids.engine.systems.signaling.types import CompiledTrigger


def _group_plants_by_species(world: ECSWorld) -> dict[int, list[PlantComponent]]:
    """Groups all plant components in the world by their species ID.

    Args:
        world: The ECS world instance.

    Returns:
        A dictionary mapping species IDs to lists of plant components.
    """
    plants_by_species: dict[int, list[PlantComponent]] = {}
    for entity in world.query(PlantComponent):
        plant = entity.get_component(PlantComponent)
        plants_by_species.setdefault(plant.species_id, []).append(plant)
    return plants_by_species


def _phase_evaluate_triggers(
    world: ECSWorld,
    env: GridEnvironment,
    trigger_conditions: dict[int, list[CompiledTrigger]],
    owner_substance_by_key: dict[tuple[int, int], SubstanceComponent],
    swarm_population_by_cell_species: SwarmPopulationIndex | dict[tuple[int, int, int], int],
    active_substance_ids_by_owner: dict[int, set[int]],
    substance_entities: list[Entity],
) -> None:
    """Evaluates environmental and herbivore triggers against all plants.

    Iterates through configured species triggers and determines whether any
    activation conditions (environmental signal or herbivore population) are
    met, subsequently applying the respective substance synthesis or withdrawal actions.

    Args:
        world: The ECS world instance.
        env: The grid environment containing signal layers.
        trigger_conditions: Dictionary mapping species ID to lists of compiled triggers.
        owner_substance_by_key: Mapping from (plant_id, substance_id) to substance component.
        swarm_population_by_cell_species: Swarm population grouped by cell and species.
        active_substance_ids_by_owner: Mapping from plant_id to active substance IDs.
        substance_entities: List to which newly created substance entities are appended.
    """
    plants_by_species = _group_plants_by_species(world)
    curve_map = {"step": 0, "hill": 1, "logarithmic": 2}
    swarm_grid = getattr(swarm_population_by_cell_species, "_grid", None)

    for species_id, triggers in trigger_conditions.items():
        if not triggers:
            continue

        plants = plants_by_species.get(species_id, [])
        if not plants:
            continue

        num_plants = len(plants)
        xs = np.empty(num_plants, dtype=np.int32)
        ys = np.empty(num_plants, dtype=np.int32)
        for i, p in enumerate(plants):
            xs[i] = p.x
            ys[i] = p.y

        mask = np.empty(num_plants, dtype=np.bool_)

        for trig in triggers:
            _evaluate_trigger_batch(
                trig,
                plants,
                xs,
                ys,
                mask,
                world,
                env,
                swarm_grid,
                owner_substance_by_key,
                swarm_population_by_cell_species,
                active_substance_ids_by_owner,
                substance_entities,
                curve_map,
            )
