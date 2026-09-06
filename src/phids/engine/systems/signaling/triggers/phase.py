# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Phase execution logic for signaling triggers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt

from phids.api.schemas.triggers import EnvironmentalSignalInitiator, HerbivoreAttackInitiator
from phids.engine.components.plant import PlantComponent
from phids.engine.systems.signaling.triggers.actions import _process_single_trigger, _process_single_trigger_action
from phids.engine.systems.signaling.triggers.evaluation import (
    _evaluate_environmental_initiator_njit,
    _evaluate_herbivore_initiator_njit,
)

if TYPE_CHECKING:
    from phids.engine.components.substances import SubstanceComponent
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld, Entity
    from phids.engine.systems.signaling.spatial import SwarmPopulationIndex
    from phids.engine.systems.signaling.types import CompiledTrigger


def _process_compiled_trigger_for_species(
    trig: CompiledTrigger,
    plants: list[PlantComponent],
    xs: npt.NDArray[np.int32],
    ys: npt.NDArray[np.int32],
    mask: npt.NDArray[np.bool_],
    world: ECSWorld,
    env: GridEnvironment,
    owner_substance_by_key: dict[tuple[int, int], SubstanceComponent],
    swarm_population_by_cell_species: SwarmPopulationIndex | dict[tuple[int, int, int], int],
    active_substance_ids_by_owner: dict[int, set[int]],
    substance_entities: list[Entity],
    curve_map: dict[str, int],
    swarm_grid: npt.NDArray[np.int32] | None,
) -> None:
    """Evaluates a compiled trigger for all plants of a specific species, delegating to fast paths if possible.

    Args:
        trig: The compiled trigger to evaluate.
        plants: A list of plant components for the selected species.
        xs: An array of pre-extracted x-coordinates.
        ys: An array of pre-extracted y-coordinates.
        mask: A pre-allocated boolean array for vectorized condition evaluation results.
        world: The ECSWorld object managing entities.
        env: The grid environment containing signal data.
        owner_substance_by_key: A lookup map for previously created substances.
        swarm_population_by_cell_species: The index tracking spatial herbivore populations.
        active_substance_ids_by_owner: Active substances mapped to their plant owners.
        substance_entities: A list to append newly created entities.
        curve_map: A dictionary translating curve strings to integer ids.
        swarm_grid: The raw 3D array of swarm populations for Numba-jitted methods.
    """
    initiator = trig.schema.initiator
    use_njit = False
    num_plants = len(plants)

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
    """Executes the trigger evaluation phase for all plant species in the signaling loop.

    Args:
        world: The ECSWorld object managing active entities.
        env: The simulation grid environment and its signal layers.
        trigger_conditions: A map of species IDs to their applicable compiled triggers.
        owner_substance_by_key: A registry mapping plant and substance IDs to existing components.
        swarm_population_by_cell_species: The current state of spatial herbivore populations.
        active_substance_ids_by_owner: Map of active substance IDs owned by each plant.
        substance_entities: A list to collect newly synthesized entity components.
    """
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
            _process_compiled_trigger_for_species(
                trig,
                plants,
                xs,
                ys,
                mask,
                world,
                env,
                owner_substance_by_key,
                swarm_population_by_cell_species,
                active_substance_ids_by_owner,
                substance_entities,
                curve_map,
                swarm_grid,
            )
