# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Trigger evaluation logic for the signaling system.

Hot-Path Import Resolution & Dynamic Module Overhead:
------------------------------------------------------------------
In interpreted high-level runtimes, dynamic `import` statements executed inside inner loop functions
incur non-trivial overhead. Each function-local import requires querying Python's global `sys.modules`
hash dictionary, verifying module locks, and performing frame attribute resolution.

In signaling evaluation loops operating across thousands of plant entities per tick
(O(N_plants * M_triggers)), dynamic import resolution introduces instruction cache churn and
dictionary lookup latency. Hoisting schema and component imports to module top-level resolves
symbols once at initial module load, allowing the interpreter to execute inner loops with direct
global variable access.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from phids.engine.components.plant import PlantComponent
from phids.engine.systems.signaling.evaluation.core import _evaluate_single_trigger_for_species

if TYPE_CHECKING:
    from phids.engine.components.substances import SubstanceComponent
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld, Entity
    from phids.engine.systems.signaling.spatial import SwarmPopulationIndex
    from phids.engine.systems.signaling.types import CompiledTrigger


def _phase_evaluate_triggers(
    world: ECSWorld,
    env: GridEnvironment,
    trigger_conditions: dict[int, list[CompiledTrigger]],
    owner_substance_by_key: dict[tuple[int, int], SubstanceComponent],
    swarm_population_by_cell_species: SwarmPopulationIndex | dict[tuple[int, int, int], int],
    active_substance_ids_by_owner: dict[int, set[int]],
    substance_entities: list[Entity],
) -> None:
    plants_by_species: dict[int, list[PlantComponent]] = {}
    for entity in world.query(PlantComponent):
        plant = entity.get_component(PlantComponent)
        plants_by_species.setdefault(plant.species_id, []).append(plant)

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
            _evaluate_single_trigger_for_species(
                trig,
                plants,
                xs,
                ys,
                mask,
                curve_map,
                swarm_grid,
                world,
                env,
                owner_substance_by_key,
                swarm_population_by_cell_species,
                active_substance_ids_by_owner,
                substance_entities,
            )
