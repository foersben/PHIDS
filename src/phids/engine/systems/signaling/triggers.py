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
    import numpy as np
    import numpy.typing as npt

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
