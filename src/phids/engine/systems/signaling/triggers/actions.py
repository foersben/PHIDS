# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Action logic for signaling triggers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from phids.api.schemas.triggers import ResourceWithdrawalAction, SynthesizeSubstanceAction
from phids.engine.components.substances import SubstanceComponent
from phids.engine.systems.signaling.conditions import _check_activation_condition
from phids.engine.systems.signaling.triggers.evaluation import _evaluate_initiator

if TYPE_CHECKING:
    from phids.engine.components.plant import PlantComponent
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld, Entity
    from phids.engine.systems.signaling.spatial import SwarmPopulationIndex
    from phids.engine.systems.signaling.types import CompiledTrigger


def _apply_synthesize_action(
    trig: CompiledTrigger,
    plant: PlantComponent,
    world: ECSWorld,
    owner_substance_by_key: dict[tuple[int, int], SubstanceComponent],
    substance_entities: list[Entity],
) -> None:
    """Applies a substance synthesis action resulting from an activated trigger.

    Args:
        trig: The compiled trigger containing the synthesis action configuration.
        plant: The plant component on which to apply the synthesis.
        world: The ECSWorld object managing entities.
        owner_substance_by_key: A registry mapping plant and substance IDs to existing components.
        substance_entities: A list tracking newly created entities for the substances.
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
    """Processes the execution of a single action from an activated trigger.

    Args:
        trig: The activated trigger configuration.
        plant: The plant component being modified.
        world: The ECSWorld object managing entities.
        env: The simulation grid environment.
        owner_substance_by_key: A lookup map for previously created substances.
        swarm_population_by_cell_species: The index tracking spatial herbivore populations.
        active_substance_ids_by_owner: Active substances mapped to their plant owners.
        substance_entities: A list of new entities created during action execution.
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
    """Evaluates a trigger and immediately processes its action if the initiator condition is met.

    Args:
        trig: The compiled trigger to evaluate.
        plant: The plant entity being checked.
        world: The ECSWorld object managing entities.
        env: The simulation grid environment.
        owner_substance_by_key: A lookup map for previously created substances.
        swarm_population_by_cell_species: The index tracking spatial herbivore populations.
        active_substance_ids_by_owner: Active substances mapped to their plant owners.
        substance_entities: A list of new entities created if an action is fired.
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
