"""Focused mutation-pilot regressions for signaling trigger-condition branch semantics."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from phids.api.schemas import TriggerConditionSchema
from phids.engine.components.substances import SubstanceComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.engine.systems.signaling import run_signaling

pytestmark = pytest.mark.mutation_pilot


def _active_substances(world: ECSWorld) -> list[SubstanceComponent]:
    """Return all currently active substance components from the ECS world."""
    return [
        entity.get_component(SubstanceComponent)
        for entity in world.query(SubstanceComponent)
        if entity.get_component(SubstanceComponent).active
    ]


def test_herbivore_threshold_is_inclusive_at_exact_boundary(
    add_plant: Callable[..., int],
    add_swarm: Callable[..., int],
) -> None:
    """A trigger with min population N activates when co-located herbivores equal N exactly."""
    world = ECSWorld()
    env = GridEnvironment(width=4, height=4, num_signals=2, num_toxins=1)
    add_plant(world, 1, 1, species_id=0, energy=10.0)
    add_swarm(world, 1, 1, species_id=0, population=4, energy=4.0)

    trigger = TriggerConditionSchema(
        herbivore_species_id=0,
        min_herbivore_population=4,
        substance_id=1,
        synthesis_duration=1,
        is_toxin=False,
    )

    run_signaling(
        world,
        env,
        trigger_conditions={0: [trigger]},
        mycorrhizal_inter_species=False,
        signal_velocity=1,
        tick=0,
    )

    active = _active_substances(world)
    assert len(active) == 1
    assert active[0].substance_id == 1
    assert env.signal_layers[1, 1, 1] > 0.0


def test_any_of_condition_triggers_when_one_branch_is_true(
    add_plant: Callable[..., int],
) -> None:
    """An any_of predicate activates if at least one child condition evaluates to true."""
    world = ECSWorld()
    env = GridEnvironment(width=4, height=4, num_signals=2, num_toxins=1)
    add_plant(world, 1, 1, species_id=0, energy=10.0)
    env.signal_layers[0, 1, 1] = 0.4

    trigger = TriggerConditionSchema(
        herbivore_species_id=0,
        min_herbivore_population=99,
        substance_id=1,
        synthesis_duration=1,
        is_toxin=False,
        activation_condition={
            "kind": "any_of",
            "conditions": [
                {
                    "kind": "environmental_signal",
                    "signal_id": 0,
                    "min_concentration": 0.2,
                },
                {"kind": "substance_active", "substance_id": 13},
            ],
        },
    )

    run_signaling(
        world,
        env,
        trigger_conditions={0: [trigger]},
        mycorrhizal_inter_species=False,
        signal_velocity=1,
        tick=0,
    )

    active = _active_substances(world)
    assert len(active) == 1
    assert active[0].substance_id == 1


def test_all_of_condition_requires_every_child(
    add_plant: Callable[..., int],
) -> None:
    """An all_of predicate stays inactive when at least one child condition is false."""
    world = ECSWorld()
    env = GridEnvironment(width=4, height=4, num_signals=2, num_toxins=1)
    add_plant(world, 1, 1, species_id=0, energy=10.0)
    env.signal_layers[0, 1, 1] = 0.4

    trigger = TriggerConditionSchema(
        herbivore_species_id=0,
        min_herbivore_population=99,
        substance_id=1,
        synthesis_duration=1,
        is_toxin=False,
        activation_condition={
            "kind": "all_of",
            "conditions": [
                {
                    "kind": "environmental_signal",
                    "signal_id": 0,
                    "min_concentration": 0.2,
                },
                {"kind": "substance_active", "substance_id": 13},
            ],
        },
    )

    run_signaling(
        world,
        env,
        trigger_conditions={0: [trigger]},
        mycorrhizal_inter_species=False,
        signal_velocity=1,
        tick=0,
    )

    assert _active_substances(world) == []
