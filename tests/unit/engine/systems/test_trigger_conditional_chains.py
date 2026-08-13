# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Invariant tests for complete trigger conditional chains.

Ensures that substance synthesis begins immediately upon initiator fulfillment,
but activation/emission is correctly gated by the activation condition.
"""

from __future__ import annotations

import pytest

from phids.api.schemas.triggers import (
    HerbivoreAttackInitiator,
    ResourceWithdrawalAction,
    SynthesizeSubstanceAction,
    TriggerConditionSchema,
)
from phids.engine.components.plant import PlantComponent
from phids.engine.components.substances import SubstanceComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.engine.systems.signaling.triggers import _phase_evaluate_triggers
from phids.engine.systems.signaling.types import CompiledTrigger


@pytest.mark.unit
def test_invariant_synthesis_starts_independent_of_activation_condition() -> None:
    """Verify that synthesis begins when the initiator is met, even if activation condition is not."""
    world = ECSWorld()
    env = GridEnvironment(width=10, height=10, num_signals=2, num_toxins=2)

    plant_entity = world.create_entity()
    plant = PlantComponent(
        entity_id=plant_entity.entity_id,
        species_id=1,
        x=5,
        y=5,
        energy=100.0,
        max_energy=100.0,
        base_energy=10.0,
        growth_rate=0.1,
        survival_threshold=5.0,
        reproduction_interval=10,
        seed_min_dist=1.0,
        seed_max_dist=2.0,
        seed_energy_cost=5.0,
    )
    world.add_component(plant_entity.entity_id, plant)

    action = SynthesizeSubstanceAction(
        substance_id=0,
        synthesis_duration=5,
        is_toxin=False,
        energy_cost_per_tick=0.0,
        irreversible=False,
    )

    schema = TriggerConditionSchema(
        initiator=HerbivoreAttackInitiator(herbivore_species_id=1, min_herbivore_population=10),
        activation_condition={"kind": "environmental_signal", "signal_id": 1, "min_concentration": 1.0},
        action=action,
    )

    # Note: Using .model_dump() on activation_condition since it is now typed as ConditionNode
    trig = CompiledTrigger(schema, schema.activation_condition.model_dump())
    trigger_conditions = {1: [trig]}

    owner_substance_by_key = {}
    active_substance_ids_by_owner = {}
    substance_entities = []
    swarm_population = {(5, 5, 1): 15}

    # Environment signal NOT met
    env.signal_layers[1, 5, 5] = 0.0

    _phase_evaluate_triggers(
        world,
        env,
        trigger_conditions,
        owner_substance_by_key,
        swarm_population,
        active_substance_ids_by_owner,
        substance_entities,
    )

    # Invariant: Synthesis must start because initiator was met.
    assert len(substance_entities) == 1
    sub = substance_entities[0].get_component(SubstanceComponent)
    assert not sub.active
    assert sub.triggered_this_tick


@pytest.mark.unit
def test_invariant_withdrawal_gated_by_activation_condition() -> None:
    """Verify that resource withdrawal requires BOTH initiator and activation condition."""
    world = ECSWorld()
    env = GridEnvironment(width=10, height=10, num_signals=2, num_toxins=2)

    plant_entity = world.create_entity()
    plant = PlantComponent(
        entity_id=plant_entity.entity_id,
        species_id=1,
        x=5,
        y=5,
        energy=100.0,
        max_energy=100.0,
        base_energy=10.0,
        growth_rate=0.1,
        survival_threshold=5.0,
        reproduction_interval=10,
        seed_min_dist=1.0,
        seed_max_dist=2.0,
        seed_energy_cost=5.0,
    )
    world.add_component(plant_entity.entity_id, plant)

    action = ResourceWithdrawalAction(apparent_nutrition_factor=0.1, withdrawal_duration=5)
    schema = TriggerConditionSchema(
        initiator=HerbivoreAttackInitiator(herbivore_species_id=1, min_herbivore_population=10),
        activation_condition={"kind": "environmental_signal", "signal_id": 1, "min_concentration": 1.0},
        action=action,
    )
    trig = CompiledTrigger(schema, schema.activation_condition.model_dump())
    trigger_conditions = {1: [trig]}

    owner_substance_by_key = {}
    active_substance_ids_by_owner = {}
    substance_entities = []
    swarm_population = {(5, 5, 1): 15}

    # Signal NOT met
    env.signal_layers[1, 5, 5] = 0.0
    _phase_evaluate_triggers(
        world,
        env,
        trigger_conditions,
        owner_substance_by_key,
        swarm_population,
        active_substance_ids_by_owner,
        substance_entities,
    )

    assert plant.withdrawal_ticks_remaining == 0

    # Signal MET
    env.signal_layers[1, 5, 5] = 1.0
    _phase_evaluate_triggers(
        world,
        env,
        trigger_conditions,
        owner_substance_by_key,
        swarm_population,
        active_substance_ids_by_owner,
        substance_entities,
    )

    assert plant.withdrawal_ticks_remaining == 5
