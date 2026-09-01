# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Evaluation logic for the signaling system phase.

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
import numpy.typing as npt

from phids.api.schemas.triggers import (
    EnvironmentalSignalInitiator,
    HerbivoreAttackInitiator,
)
from phids.engine.components.plant import PlantComponent

if TYPE_CHECKING:
    from phids.engine.components.substances import SubstanceComponent
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld, Entity
    from phids.engine.systems.signaling.spatial import SwarmPopulationIndex
    from phids.engine.systems.signaling.types import CompiledTrigger

from phids.engine.systems.signaling.triggers import (
    _evaluate_environmental_initiator_njit,
    _evaluate_herbivore_initiator_njit,
    _process_single_trigger,
    _process_single_trigger_action,
)


def _evaluate_single_trigger_for_species(
    trig: CompiledTrigger,
    initiator: EnvironmentalSignalInitiator | HerbivoreAttackInitiator,
    plants: list[PlantComponent],
    xs: npt.NDArray[np.int32],
    ys: npt.NDArray[np.int32],
    mask: npt.NDArray[np.bool_],
    swarm_grid: npt.NDArray[np.int32] | None,
    env: GridEnvironment,
    curve_map: dict[str, int],
    world: ECSWorld,
    owner_substance_by_key: dict[tuple[int, int], SubstanceComponent],
    swarm_population_by_cell_species: SwarmPopulationIndex | dict[tuple[int, int, int], int],
    active_substance_ids_by_owner: dict[int, set[int]],
    substance_entities: list[Entity],
) -> None:
    """Evaluates a single trigger across a subset of plants.

    Args:
        trig: Compiled trigger to evaluate.
        initiator: The trigger initiator schema.
        plants: List of plant components for the species.
        xs: Array of plant X coordinates.
        ys: Array of plant Y coordinates.
        mask: Boolean mask array for evaluation results.
        swarm_grid: Grid of swarm populations, if available.
        env: The grid environment.
        curve_map: Mapping of curve string names to integer constants.
        world: The ECSWorld instance.
        owner_substance_by_key: Mapping of owner to active substance components.
        swarm_population_by_cell_species: Spatial index of herbivore populations.
        active_substance_ids_by_owner: Set of active substance IDs per owner plant.
        substance_entities: List to append newly created substance entities to.
    """
    num_plants = len(plants)
    use_njit = False

    if isinstance(initiator, HerbivoreAttackInitiator):
        if swarm_grid is not None:
            _evaluate_herbivore_initiator_njit(
                xs,
                ys,
                initiator.herbivore_species_id,
                initiator.min_herbivore_population,
                swarm_grid,
                mask,
            )
            use_njit = True

    elif isinstance(initiator, EnvironmentalSignalInitiator):
        if 0 <= initiator.signal_id < env.num_signals:
            _evaluate_environmental_initiator_njit(
                xs,
                ys,
                env.signal_layers[initiator.signal_id],
                curve_map.get(initiator.response_curve, -1),
                initiator.min_concentration,
                initiator.half_saturation,
                initiator.hill_cooperativity,
                mask,
            )
            use_njit = True

    if use_njit:
        for i in range(num_plants):
            if mask[i]:
                _process_single_trigger_action(
                    trig,
                    plants[i],
                    world,
                    env,
                    owner_substance_by_key,
                    swarm_population_by_cell_species,
                    active_substance_ids_by_owner,
                    substance_entities,
                )
    else:
        for p in plants:
            _process_single_trigger(
                trig,
                p,
                world,
                env,
                owner_substance_by_key,
                swarm_population_by_cell_species,
                active_substance_ids_by_owner,
                substance_entities,
            )


def _phase_evaluate_triggers(
    world: ECSWorld,
    env: GridEnvironment,
    trigger_conditions: dict[int, list[CompiledTrigger]],
    owner_substance_by_key: dict[tuple[int, int], SubstanceComponent],
    swarm_population_by_cell_species: SwarmPopulationIndex | dict[tuple[int, int, int], int],
    active_substance_ids_by_owner: dict[int, set[int]],
    substance_entities: list[Entity],
) -> None:
    """Evaluates all trigger conditions for all active flora species."""
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
                trig=trig,
                initiator=trig.schema.initiator,
                plants=plants,
                xs=xs,
                ys=ys,
                mask=mask,
                swarm_grid=swarm_grid,
                env=env,
                curve_map=curve_map,
                world=world,
                owner_substance_by_key=owner_substance_by_key,
                swarm_population_by_cell_species=swarm_population_by_cell_species,
                active_substance_ids_by_owner=active_substance_ids_by_owner,
                substance_entities=substance_entities,
            )
