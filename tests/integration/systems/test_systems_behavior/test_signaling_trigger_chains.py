# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Integration tests validating the conditional trigger chains and invariants of the signaling system."""

from __future__ import annotations

from typing import TYPE_CHECKING

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
from phids.engine.systems.signaling import run_signaling
from phids.engine.systems.signaling.types import CompiledTrigger

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture
def run_tick() -> Callable[..., None]:
    """Helper to run a single signaling tick for a specific trigger schema."""

    def _run(
        world: ECSWorld,
        env: GridEnvironment,
        schema: TriggerConditionSchema,
        tick: int,
    ) -> None:
        trig = CompiledTrigger(
            schema=schema,
            activation_condition_dump=schema.activation_condition.model_dump(mode="json")
            if schema.activation_condition is not None
            else None,
        )
        run_signaling(
            world=world,
            env=env,
            trigger_conditions={0: [trig]},
            mycorrhizal_inter_species=False,
            signal_velocity=1,
            tick=tick,
        )

    return _run


def test_invariant_synthesis_starts_without_activation_condition(
    add_plant: Callable[..., int],
    add_swarm: Callable[..., int],
    run_tick: Callable[..., None],
) -> None:
    """Invariant: Synthesis starts immediately when the initiator is met, even if activation cond is false."""
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=2, num_toxins=2)

    add_plant(world, 2, 2, species_id=0, energy=20.0)
    add_swarm(world, 2, 2, species_id=0, pop=5)

    schema = TriggerConditionSchema(
        initiator=HerbivoreAttackInitiator(herbivore_species_id=0, min_herbivore_population=5),
        activation_condition={"kind": "substance_active", "substance_id": 15},  # Impossible condition
        action=SynthesizeSubstanceAction(substance_id=1, synthesis_duration=5, is_toxin=True),
    )

    run_tick(world, env, schema, 0)

    sub_entities = list(world.query(SubstanceComponent))
    assert len(sub_entities) == 1
    sub = sub_entities[0].get_component(SubstanceComponent)

    # Synthesis has started (duration - 1)
    assert sub.synthesis_remaining == 4
    assert sub.triggered_this_tick is True
    assert sub.active is False


def test_invariant_synthesis_completes_but_waits_for_activation(
    add_plant: Callable[..., int],
    add_swarm: Callable[..., int],
    run_tick: Callable[..., None],
) -> None:
    """Invariant: Synthesis completes but the substance remains inactive until activation condition is met."""
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=2, num_toxins=2)

    plant_id = add_plant(world, 2, 2, species_id=0, energy=20.0)
    add_swarm(world, 2, 2, species_id=0, pop=5)

    schema = TriggerConditionSchema(
        initiator=HerbivoreAttackInitiator(herbivore_species_id=0, min_herbivore_population=5),
        activation_condition={"kind": "substance_active", "substance_id": 0},  # Requires substance 0 to be active
        action=SynthesizeSubstanceAction(substance_id=1, synthesis_duration=2, is_toxin=True),
    )

    run_tick(world, env, schema, 0)  # Synthesis remaining -> 1
    run_tick(world, env, schema, 1)  # Synthesis remaining -> 0

    sub = next(
        e.get_component(SubstanceComponent)
        for e in world.query(SubstanceComponent)
        if e.get_component(SubstanceComponent).substance_id == 1
    )

    assert sub.synthesis_remaining == 0
    assert sub.active is False  # Unmet condition

    # Tick 2: Trigger is still met, synthesis is 0, condition still unmet
    run_tick(world, env, schema, 2)
    assert sub.active is False

    # Now simulate condition being met by adding a fake active substance 0
    dummy_sub = SubstanceComponent(entity_id=999, substance_id=0, owner_plant_id=plant_id, active=True)
    dummy_entity = world.create_entity()
    world.add_component(dummy_entity.entity_id, dummy_sub)

    # Tick 3: Trigger met, synthesis 0, condition met -> should activate
    run_tick(world, env, schema, 3)
    assert sub.active is True
    assert float(env.toxin_layers[1].max()) > 0.0


def test_invariant_resource_withdrawal_respects_activation_condition(
    add_plant: Callable[..., int],
    add_swarm: Callable[..., int],
    run_tick: Callable[..., None],
) -> None:
    """Invariant: Resource withdrawal must not activate if the activation condition is unmet."""
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=2, num_toxins=2)

    plant_id = add_plant(world, 2, 2, species_id=0, energy=20.0)
    add_swarm(world, 2, 2, species_id=0, pop=5)

    schema = TriggerConditionSchema(
        initiator=HerbivoreAttackInitiator(herbivore_species_id=0, min_herbivore_population=5),
        activation_condition={"kind": "substance_active", "substance_id": 0},  # Requires substance 0 to be active
        action=ResourceWithdrawalAction(apparent_nutrition_factor=0.5, withdrawal_duration=5),
    )

    run_tick(world, env, schema, 0)

    plant = world.get_entity(plant_id).get_component(PlantComponent)
    # Condition unmet, so withdrawal does not apply
    assert getattr(plant, "target_nutrition_factor", 1.0) == 1.0
    assert plant.withdrawal_ticks_remaining == 0

    # Simulate condition being met
    dummy_sub = SubstanceComponent(entity_id=999, substance_id=0, owner_plant_id=plant_id, active=True)
    dummy_entity = world.create_entity()
    world.add_component(dummy_entity.entity_id, dummy_sub)

    run_tick(world, env, schema, 1)

    # Condition met, withdrawal applies
    assert plant.target_nutrition_factor == 0.5
    assert plant.withdrawal_ticks_remaining == 4
