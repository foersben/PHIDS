# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Trigger evaluation loop logic for the signaling system."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt

from phids.api.schemas.triggers import (
    EnvironmentalSignalInitiator,
    HerbivoreAttackInitiator,
)


if TYPE_CHECKING:
    from phids.engine.components.plant import PlantComponent
    from phids.engine.components.substances import SubstanceComponent
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld, Entity
    from phids.engine.systems.signaling.spatial import SwarmPopulationIndex
    from phids.engine.systems.signaling.types import CompiledTrigger


def _evaluate_single_trigger_for_species(
    trig: CompiledTrigger,
    plants: list[PlantComponent],
    xs: npt.NDArray[np.int32],
    ys: npt.NDArray[np.int32],
    mask: npt.NDArray[np.bool_],
    world: ECSWorld,
    env: GridEnvironment,
    owner_substance_by_key: dict[tuple[int, int], SubstanceComponent],
    swarm_population_by_cell_species: SwarmPopulationIndex | dict[tuple[int, int, int], int],
    swarm_grid: npt.NDArray[np.int32] | None,
    curve_map: dict[str, int],
    active_substance_ids_by_owner: dict[int, set[int]],
    substance_entities: list[Entity],
) -> None:
    from phids.engine.systems.signaling.triggers import _evaluate_environmental_initiator_njit, _evaluate_herbivore_initiator_njit, _process_single_trigger, _process_single_trigger_action
    """Evaluates a single compiled trigger for a population of plants.

    Args:
        trig: The compiled trigger to evaluate.
        plants: The population of plants to check.
        xs: An array of plant x-coordinates.
        ys: An array of plant y-coordinates.
        mask: An array for njit trigger boolean results.
        world: The ECS world.
        env: The grid environment.
        owner_substance_by_key: Substance lookup dictionary.
        swarm_population_by_cell_species: The spatial hash of swarms.
        swarm_grid: The optional numpy grid array of swarms.
        curve_map: Mapping for response curves.
        active_substance_ids_by_owner: Currently active substance tracker.
        substance_entities: Global list tracking created entities.
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


def _evaluate_triggers_for_species(
    triggers: list[CompiledTrigger],
    plants: list[PlantComponent],
    world: ECSWorld,
    env: GridEnvironment,
    owner_substance_by_key: dict[tuple[int, int], SubstanceComponent],
    swarm_population_by_cell_species: SwarmPopulationIndex | dict[tuple[int, int, int], int],
    swarm_grid: npt.NDArray[np.int32] | None,
    curve_map: dict[str, int],
    active_substance_ids_by_owner: dict[int, set[int]],
    substance_entities: list[Entity],
) -> None:
    """Evaluates all triggers for a single species population.

    Args:
        triggers: The list of compiled triggers for this species.
        plants: The plants of this species.
        world: The ECS world.
        env: The grid environment.
        owner_substance_by_key: Mapping from (plant_id, substance_id) to component.
        swarm_population_by_cell_species: Swarm density tracking.
        swarm_grid: Array of swarm densities for njit evaluation.
        curve_map: Mapping for environmental response curves.
        active_substance_ids_by_owner: Mapping from owner to active substance ids.
        substance_entities: New entities to add.
    """
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
            world,
            env,
            owner_substance_by_key,
            swarm_population_by_cell_species,
            swarm_grid,
            curve_map,
            active_substance_ids_by_owner,
            substance_entities,
        )
