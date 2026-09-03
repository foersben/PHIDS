# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Evaluation logic for triggers.

Extracted to reduce cognitive complexity and isolate njit evaluations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt
from numba import njit

from phids.api.schemas.triggers import (
    EnvironmentalSignalInitiator,
    HerbivoreAttackInitiator,
    ResourceWithdrawalAction,
    SynthesizeSubstanceAction,
)
from phids.engine.components.substances import SubstanceComponent
from phids.engine.systems.signaling.conditions import _check_activation_condition

if TYPE_CHECKING:
    from phids.engine.components.plant import PlantComponent
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld, Entity
    from phids.engine.systems.signaling.spatial import SwarmPopulationIndex
    from phids.engine.systems.signaling.types import CompiledTrigger


@njit(cache=True, fastmath=True)
def _evaluate_environmental_initiator_njit(
    xs: npt.NDArray[np.int32],
    ys: npt.NDArray[np.int32],
    signal_layer: npt.NDArray[np.float64],
    response_curve: int,
    min_concentration: float,
    half_saturation: float,
    hill_cooperativity: float,
    out_mask: npt.NDArray[np.bool_],
) -> None:
    """Evaluates an environmental signal initiator using Numba JIT.

    Args:
        xs: Array of plant X coordinates.
        ys: Array of plant Y coordinates.
        signal_layer: Environment signal concentration grid.
        response_curve: Response curve integer type (0=step, 1=hill, 2=logarithmic).
        min_concentration: Minimum required concentration.
        half_saturation: Hill curve half-saturation constant.
        hill_cooperativity: Hill curve cooperativity coefficient.
        out_mask: Boolean array to store the result of the evaluation.
    """
    for i in range(len(xs)):
        x = xs[i]
        y = ys[i]
        conc = signal_layer[x, y]

        if response_curve == 0:  # step
            out_mask[i] = conc >= min_concentration
        elif response_curve == 1:  # hill
            if conc > 0.0:
                cn = conc**hill_cooperativity
                priming_factor = cn / (half_saturation**hill_cooperativity + cn)
                out_mask[i] = priming_factor >= 0.05
            else:
                out_mask[i] = False
        elif response_curve == 2:  # logarithmic
            out_mask[i] = conc >= min_concentration
        else:
            out_mask[i] = False


@njit(cache=True, fastmath=True)
def _evaluate_herbivore_initiator_njit(
    xs: npt.NDArray[np.int32],
    ys: npt.NDArray[np.int32],
    species_id: int,
    min_population: int,
    swarm_grid: npt.NDArray[np.int32],
    out_mask: npt.NDArray[np.bool_],
) -> None:
    """Evaluates a herbivore population initiator using Numba JIT.

    Args:
        xs: Array of plant X coordinates.
        ys: Array of plant Y coordinates.
        species_id: Target herbivore species ID.
        min_population: Minimum required population size.
        swarm_grid: Herbivore swarm population grid array.
        out_mask: Boolean array to store the result of the evaluation.
    """
    for i in range(len(xs)):
        x = xs[i]
        y = ys[i]
        pop = swarm_grid[species_id, x, y]
        out_mask[i] = pop >= min_population


def _evaluate_environmental_signal(
    initiator: EnvironmentalSignalInitiator,
    plant: PlantComponent,
    env: GridEnvironment,
) -> bool:
    """Evaluates if a single plant meets an environmental signal condition.

    Args:
        initiator: The environmental signal initiator schema.
        plant: The target plant component.
        env: Grid environment containing signal layers.

    Returns:
        True if the signal condition is met, False otherwise.
    """
    if not (0 <= initiator.signal_id < env.num_signals):
        return False

    conc = float(env.signal_layers[initiator.signal_id, plant.x, plant.y])
    mode = initiator.response_curve

    if mode == "step":
        return conc >= initiator.min_concentration
    if mode == "hill":
        kd = initiator.half_saturation
        n = initiator.hill_cooperativity
        if conc > 0.0:
            cn = conc**n
            priming_factor = cn / (kd**n + cn)
            return bool(priming_factor >= 0.05)
        return False
    if mode == "logarithmic":
        return conc >= initiator.min_concentration

    return False


def _evaluate_initiator(
    trig: CompiledTrigger,
    plant: PlantComponent,
    env: GridEnvironment,
    swarm_population_by_cell_species: SwarmPopulationIndex | dict[tuple[int, int, int], int],
) -> bool:
    """Evaluates a trigger initiator for a single plant.

    Args:
        trig: Compiled trigger definition.
        plant: Target plant component.
        env: Grid environment.
        swarm_population_by_cell_species: Dictionary or index of swarm populations.

    Returns:
        True if the initiator condition is met, False otherwise.
    """
    if isinstance(trig.schema.initiator, HerbivoreAttackInitiator):
        return (
            swarm_population_by_cell_species.get((plant.x, plant.y, trig.schema.initiator.herbivore_species_id), 0)
            >= trig.schema.initiator.min_herbivore_population
        )

    if isinstance(trig.schema.initiator, EnvironmentalSignalInitiator):
        return _evaluate_environmental_signal(trig.schema.initiator, plant, env)

    return False


def _apply_synthesize_action(
    trig: CompiledTrigger,
    plant: PlantComponent,
    world: ECSWorld,
    owner_substance_by_key: dict[tuple[int, int], SubstanceComponent],
    substance_entities: list[Entity],
) -> None:
    """Applies a synthesize substance action to a plant.

    Args:
        trig: Compiled trigger containing the synthesize action.
        plant: Target plant component to synthesize substance for.
        world: ECS world context.
        owner_substance_by_key: Mapping from (plant_id, substance_id) to component.
        substance_entities: List tracking newly created substance entities.
    """
    assert isinstance(trig.schema.action, SynthesizeSubstanceAction)
    substance_id = trig.schema.action.substance_id
    existing_sub = owner_substance_by_key.get((plant.entity_id, substance_id))

    if existing_sub is None:
        new_entity = world.create_entity()
        existing_sub = SubstanceComponent(
            entity_id=new_entity.entity_id,
            substance_id=substance_id,
            owner_plant_id=plant.entity_id,
            is_toxin=trig.schema.action.is_toxin,
            synthesis_duration=trig.schema.action.synthesis_duration,
            synthesis_remaining=trig.schema.action.synthesis_duration,
            lethal=trig.schema.action.lethal,
            lethality_rate=trig.schema.action.lethality_rate,
            repellent=trig.schema.action.repellent,
            repellent_walk_ticks=trig.schema.action.repellent_walk_ticks,
            aftereffect_ticks=trig.schema.aftereffect_ticks,
            aftereffect_remaining_ticks=trig.schema.aftereffect_ticks,
            activation_condition=trig.activation_condition_dump,
            energy_cost_per_tick=trig.schema.action.energy_cost_per_tick,
            irreversible=trig.schema.action.irreversible,
        )
        world.add_component(new_entity.entity_id, existing_sub)
        owner_substance_by_key[(plant.entity_id, substance_id)] = existing_sub
        substance_entities.append(new_entity)
    else:
        if (
            not existing_sub.active
            and not existing_sub.triggered_last_tick
            and existing_sub.synthesis_remaining <= 0
            and existing_sub.aftereffect_remaining_ticks <= 0
        ):
            existing_sub.synthesis_remaining = existing_sub.synthesis_duration

    existing_sub.triggered_this_tick = True


def _process_single_trigger_action(
    trig: CompiledTrigger,
    plant: PlantComponent,
    world: ECSWorld,
    env: GridEnvironment,
    owner_substance_by_key: dict[tuple[int, int], SubstanceComponent],
    swarm_population_by_cell_species: SwarmPopulationIndex | dict[tuple[int, int, int], int],
    active_substance_ids_by_owner: dict[int, set[int]],
    substance_entities: list[Entity],
) -> None:
    """Processes a single trigger action for a plant if conditions are met.

    Args:
        trig: Compiled trigger definition.
        plant: Target plant component.
        world: ECS world context.
        env: Grid environment.
        owner_substance_by_key: Mapping of plant substances.
        swarm_population_by_cell_species: Dictionary or index of swarm populations.
        active_substance_ids_by_owner: Set of active substance IDs per plant.
        substance_entities: List to append new substance entities.
    """
    if isinstance(trig.schema.action, ResourceWithdrawalAction):
        if trig.schema.activation_condition is not None:
            condition_met = _check_activation_condition(
                plant,
                plant.entity_id,
                trig.activation_condition_dump,
                env,
                swarm_population_by_cell_species,
                active_substance_ids_by_owner,
            )
            if not condition_met:
                return
        plant.target_nutrition_factor = trig.schema.action.apparent_nutrition_factor
        plant.withdrawal_ticks_remaining = trig.schema.action.withdrawal_duration
        return

    if not isinstance(trig.schema.action, SynthesizeSubstanceAction):
        return

    _apply_synthesize_action(trig, plant, world, owner_substance_by_key, substance_entities)


def _process_single_trigger(
    trig: CompiledTrigger,
    plant: PlantComponent,
    world: ECSWorld,
    env: GridEnvironment,
    owner_substance_by_key: dict[tuple[int, int], SubstanceComponent],
    swarm_population_by_cell_species: SwarmPopulationIndex | dict[tuple[int, int, int], int],
    active_substance_ids_by_owner: dict[int, set[int]],
    substance_entities: list[Entity],
) -> None:
    """Evaluates a single trigger and processes its action if initiated.

    Args:
        trig: Compiled trigger definition.
        plant: Target plant component.
        world: ECS world context.
        env: Grid environment.
        owner_substance_by_key: Mapping of plant substances.
        swarm_population_by_cell_species: Dictionary or index of swarm populations.
        active_substance_ids_by_owner: Set of active substance IDs per plant.
        substance_entities: List to append new substance entities.
    """
    initiator_met = _evaluate_initiator(trig, plant, env, swarm_population_by_cell_species)
    if not initiator_met:
        return
    _process_single_trigger_action(
        trig,
        plant,
        world,
        env,
        owner_substance_by_key,
        swarm_population_by_cell_species,
        active_substance_ids_by_owner,
        substance_entities,
    )


def _process_njit_triggers_for_species(
    trig: CompiledTrigger,
    plants: list[PlantComponent],
    num_plants: int,
    mask: npt.NDArray[np.bool_],
    world: ECSWorld,
    env: GridEnvironment,
    owner_substance_by_key: dict[tuple[int, int], SubstanceComponent],
    swarm_population_by_cell_species: SwarmPopulationIndex | dict[tuple[int, int, int], int],
    active_substance_ids_by_owner: dict[int, set[int]],
    substance_entities: list[Entity],
) -> None:
    """Processes actions for a species using Numba JIT evaluation masks.

    Args:
        trig: Compiled trigger definition.
        plants: List of plant components for the species.
        num_plants: Total number of plants of this species.
        mask: Boolean mask indicating which plants met the initiator condition.
        world: ECS world context.
        env: Grid environment.
        owner_substance_by_key: Mapping of plant substances.
        swarm_population_by_cell_species: Dictionary or index of swarm populations.
        active_substance_ids_by_owner: Set of active substance IDs per plant.
        substance_entities: List to append new substance entities.
    """
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


def _process_standard_triggers_for_species(
    trig: CompiledTrigger,
    plants: list[PlantComponent],
    world: ECSWorld,
    env: GridEnvironment,
    owner_substance_by_key: dict[tuple[int, int], SubstanceComponent],
    swarm_population_by_cell_species: SwarmPopulationIndex | dict[tuple[int, int, int], int],
    active_substance_ids_by_owner: dict[int, set[int]],
    substance_entities: list[Entity],
) -> None:
    """Processes actions for a species using standard evaluation logic.

    Args:
        trig: Compiled trigger definition.
        plants: List of plant components for the species.
        world: ECS world context.
        env: Grid environment.
        owner_substance_by_key: Mapping of plant substances.
        swarm_population_by_cell_species: Dictionary or index of swarm populations.
        active_substance_ids_by_owner: Set of active substance IDs per plant.
        substance_entities: List to append new substance entities.
    """
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


def _evaluate_species_triggers(
    triggers: list[CompiledTrigger],
    plants: list[PlantComponent],
    world: ECSWorld,
    env: GridEnvironment,
    owner_substance_by_key: dict[tuple[int, int], SubstanceComponent],
    swarm_population_by_cell_species: SwarmPopulationIndex | dict[tuple[int, int, int], int],
    active_substance_ids_by_owner: dict[int, set[int]],
    substance_entities: list[Entity],
    curve_map: dict[str, int],
    swarm_grid: npt.NDArray[np.int32] | None,
) -> None:
    """Evaluates all triggers for a specific species.

    Args:
        triggers: List of compiled triggers for this species.
        plants: List of plant entities of this species.
        world: ECS world containing the simulation state.
        env: Grid environment handling spatial properties and signals.
        owner_substance_by_key: Map of existing substances by owner plant ID.
        swarm_population_by_cell_species: Spatial index of swarm populations.
        active_substance_ids_by_owner: Map of active substances.
        substance_entities: List to append new substance entities to.
        curve_map: Mapping of curve names to enum integers.
        swarm_grid: Herbivore swarm grid array.
    """
    num_plants = len(plants)
    xs = np.empty(num_plants, dtype=np.int32)
    ys = np.empty(num_plants, dtype=np.int32)
    for i, p in enumerate(plants):
        xs[i] = p.x
        ys[i] = p.y

    mask = np.empty(num_plants, dtype=np.bool_)

    for trig in triggers:
        initiator = trig.schema.initiator
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
            _process_njit_triggers_for_species(
                trig,
                plants,
                num_plants,
                mask,
                world,
                env,
                owner_substance_by_key,
                swarm_population_by_cell_species,
                active_substance_ids_by_owner,
                substance_entities,
            )
        else:
            _process_standard_triggers_for_species(
                trig,
                plants,
                world,
                env,
                owner_substance_by_key,
                swarm_population_by_cell_species,
                active_substance_ids_by_owner,
                substance_entities,
            )
