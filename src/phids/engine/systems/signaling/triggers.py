# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Trigger evaluation logic for the signaling system."""

from __future__ import annotations

from typing import TYPE_CHECKING

from phids.engine.components.plant import PlantComponent
from phids.engine.components.substances import SubstanceComponent

if TYPE_CHECKING:
    from phids.api.schemas.triggers import (
        EnvironmentalSignalInitiator,
        TriggerConditionSchema,
    )
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld, Entity


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
    trig: TriggerConditionSchema,
    plant: PlantComponent,
    env: GridEnvironment,
    swarm_population_by_cell_species: dict[tuple[int, int, int], int],
) -> bool:
    from phids.api.schemas.triggers import (
        EnvironmentalSignalInitiator,
        HerbivoreAttackInitiator,
    )

    if isinstance(trig.initiator, HerbivoreAttackInitiator):
        return (
            swarm_population_by_cell_species.get((plant.x, plant.y, trig.initiator.herbivore_species_id), 0)
            >= trig.initiator.min_herbivore_population
        )

    if isinstance(trig.initiator, EnvironmentalSignalInitiator):
        return _evaluate_environmental_signal(trig.initiator, plant, env)

    return False


def _apply_synthesize_action(
    trig: TriggerConditionSchema,
    plant: PlantComponent,
    world: ECSWorld,
    owner_substance_by_key: dict[tuple[int, int], SubstanceComponent],
    substance_entities: list[Entity],
) -> None:
    from phids.api.schemas.triggers import SynthesizeSubstanceAction

    assert isinstance(trig.action, SynthesizeSubstanceAction)
    substance_id = trig.action.substance_id
    existing_sub = owner_substance_by_key.get((plant.entity_id, substance_id))

    if existing_sub is None:
        new_entity = world.create_entity()
        existing_sub = SubstanceComponent(
            entity_id=new_entity.entity_id,
            substance_id=substance_id,
            owner_plant_id=plant.entity_id,
            is_toxin=trig.action.is_toxin,
            synthesis_duration=trig.action.synthesis_duration,
            synthesis_remaining=trig.action.synthesis_duration,
            lethal=trig.action.lethal,
            lethality_rate=trig.action.lethality_rate,
            repellent=trig.action.repellent,
            repellent_walk_ticks=trig.action.repellent_walk_ticks,
            aftereffect_ticks=trig.aftereffect_ticks,
            aftereffect_remaining_ticks=trig.aftereffect_ticks,
            activation_condition=(
                trig.activation_condition.model_dump(mode="json") if trig.activation_condition is not None else None
            ),
            energy_cost_per_tick=trig.action.energy_cost_per_tick,
            irreversible=trig.action.irreversible,
        )
        world.add_component(new_entity.entity_id, existing_sub)
        owner_substance_by_key[(plant.entity_id, substance_id)] = existing_sub
        substance_entities.append(new_entity)
    else:
        if (
            not existing_sub.active
            and existing_sub.synthesis_remaining <= 0
            and existing_sub.aftereffect_remaining_ticks <= 0
        ):
            existing_sub.synthesis_remaining = existing_sub.synthesis_duration

    existing_sub.triggered_this_tick = True


def _process_single_trigger(
    trig: TriggerConditionSchema,
    plant: PlantComponent,
    world: ECSWorld,
    env: GridEnvironment,
    owner_substance_by_key: dict[tuple[int, int], SubstanceComponent],
    swarm_population_by_cell_species: dict[tuple[int, int, int], int],
    active_substance_ids_by_owner: dict[int, set[int]],
    substance_entities: list[Entity],
) -> None:
    from phids.api.schemas.triggers import (
        ResourceWithdrawalAction,
        SynthesizeSubstanceAction,
    )

    initiator_met = _evaluate_initiator(trig, plant, env, swarm_population_by_cell_species)

    condition_met = False
    if trig.activation_condition is not None:
        from phids.engine.systems.signaling.conditions import _check_activation_condition

        condition_met = _check_activation_condition(
            plant,
            plant.entity_id,
            trig.activation_condition.model_dump(mode="json"),
            env,
            swarm_population_by_cell_species,
            active_substance_ids_by_owner,
        )

    if not (initiator_met or condition_met):
        return
    if isinstance(trig.action, ResourceWithdrawalAction):
        plant.target_nutrition_factor = trig.action.apparent_nutrition_factor
        plant.withdrawal_ticks_remaining = trig.action.withdrawal_duration
        return

    if not isinstance(trig.action, SynthesizeSubstanceAction):
        return

    _apply_synthesize_action(trig, plant, world, owner_substance_by_key, substance_entities)


def _phase_evaluate_triggers(
    world: ECSWorld,
    env: GridEnvironment,
    trigger_conditions: dict[int, list[TriggerConditionSchema]],
    owner_substance_by_key: dict[tuple[int, int], SubstanceComponent],
    swarm_population_by_cell_species: dict[tuple[int, int, int], int],
    active_substance_ids_by_owner: dict[int, set[int]],
    substance_entities: list[Entity],
) -> None:
    for entity in world.query(PlantComponent):
        plant = entity.get_component(PlantComponent)
        triggers = trigger_conditions.get(plant.species_id, [])

        for trig in triggers:
            _process_single_trigger(
                trig,
                plant,
                world,
                env,
                owner_substance_by_key,
                swarm_population_by_cell_species,
                active_substance_ids_by_owner,
                substance_entities,
            )
