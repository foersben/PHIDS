# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Integration tests for PHIDS volatile organic compound (VOC) signaling and systemic defense mechanisms."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from phids.api.schemas.triggers import (
    HerbivoreAttackInitiator,
    SynthesizeSubstanceAction,
    TriggerConditionSchema,
)
from phids.engine.components.plant import PlantComponent
from phids.engine.components.substances import SubstanceComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.engine.systems.signaling import run_signaling
from phids.shared.constants import SUBSTANCE_EMIT_RATE

if TYPE_CHECKING:
    from collections.abc import Callable


def test_signaling_spawns_configured_toxin_and_applies_properties(
    add_plant: Callable[..., int], add_swarm: Callable[..., int]
) -> None:
    """Verify signaling creates configured toxin entities with expected runtime flags."""
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=2, num_toxins=2)
    plant_id = add_plant(world, 2, 2, species_id=0, energy=12.0)
    add_swarm(world, 2, 2, species_id=0, pop=10)
    trigger = TriggerConditionSchema(
        initiator=HerbivoreAttackInitiator(herbivore_species_id=0, min_herbivore_population=5),
        aftereffect_ticks=2,
        action=SynthesizeSubstanceAction(
            substance_id=1,
            synthesis_duration=1,
            is_toxin=True,
            lethal=True,
            lethality_rate=0.5,
            repellent=True,
            repellent_walk_ticks=3,
            energy_cost_per_tick=1.0,
        ),
    )
    run_signaling(
        world, env, trigger_conditions={0: [trigger]}, mycorrhizal_inter_species=False, signal_velocity=1, tick=0
    )
    subs = [e.get_component(SubstanceComponent) for e in world.query(SubstanceComponent)]
    assert len(subs) == 1
    sub = subs[0]
    assert sub.is_toxin is True
    assert sub.active is True
    assert sub.repellent is True
    assert sub.lethal is True
    assert sub.repellent_walk_ticks == 3
    plant = world.get_entity(plant_id).get_component(PlantComponent)
    assert plant.energy < 12.0


def test_signaling_aggregates_co_located_swarm_population_for_trigger_threshold(
    add_plant: Callable[..., int], add_swarm: Callable[..., int]
) -> None:
    """Verify trigger checks aggregate co-located swarm populations before activation."""
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=2, num_toxins=2)
    add_plant(world, 2, 2, species_id=0, energy=12.0)
    add_swarm(world, 2, 2, species_id=0, pop=3)
    add_swarm(world, 2, 2, species_id=0, pop=3)
    trigger = TriggerConditionSchema(
        initiator=HerbivoreAttackInitiator(herbivore_species_id=0, min_herbivore_population=5),
        action=SynthesizeSubstanceAction(substance_id=1, synthesis_duration=1, is_toxin=True),
    )
    run_signaling(
        world, env, trigger_conditions={0: [trigger]}, mycorrhizal_inter_species=False, signal_velocity=1, tick=0
    )
    subs = [e.get_component(SubstanceComponent) for e in world.query(SubstanceComponent)]
    assert len(subs) == 1
    assert subs[0].active is True


def test_signaling_toxin_deactivates_when_trigger_species_is_gone(
    add_plant: Callable[..., int], add_swarm: Callable[..., int]
) -> None:
    """Verify toxin deactivates when its triggering herbivore species is absent."""
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=2, num_toxins=2)
    add_plant(world, 2, 2, species_id=0, energy=12.0)
    triggering_swarm_id = add_swarm(world, 2, 2, species_id=0, pop=6)
    add_swarm(world, 2, 2, species_id=1, pop=10)
    trigger = TriggerConditionSchema(
        initiator=HerbivoreAttackInitiator(herbivore_species_id=0, min_herbivore_population=5),
        aftereffect_ticks=0,
        action=SynthesizeSubstanceAction(substance_id=1, synthesis_duration=1, is_toxin=True),
    )
    run_signaling(
        world, env, trigger_conditions={0: [trigger]}, mycorrhizal_inter_species=False, signal_velocity=1, tick=0
    )
    world.unregister_position(triggering_swarm_id, 2, 2)
    world.collect_garbage([triggering_swarm_id])
    run_signaling(
        world, env, trigger_conditions={0: [trigger]}, mycorrhizal_inter_species=False, signal_velocity=1, tick=1
    )
    sub = next(e.get_component(SubstanceComponent) for e in world.query(SubstanceComponent))
    assert sub.active is False
    assert float(env.toxin_layers[1].max()) == 0.0


def test_signaling_toxin_lingers_for_aftereffect_then_deactivates(
    add_plant: Callable[..., int], add_swarm: Callable[..., int]
) -> None:
    """Verify toxin remains active through aftereffect ticks and then deactivates."""
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=2, num_toxins=2)
    add_plant(world, 2, 2, species_id=0, energy=12.0)
    swarm_id = add_swarm(world, 2, 2, species_id=0, pop=6)
    trigger = TriggerConditionSchema(
        initiator=HerbivoreAttackInitiator(herbivore_species_id=0, min_herbivore_population=5),
        aftereffect_ticks=2,
        action=SynthesizeSubstanceAction(substance_id=1, synthesis_duration=1, is_toxin=True),
    )
    run_signaling(world, env, {0: [trigger]}, False, 1, 0)
    world.unregister_position(swarm_id, 2, 2)
    world.collect_garbage([swarm_id])
    run_signaling(world, env, {0: [trigger]}, False, 1, 1)
    sub = next(e.get_component(SubstanceComponent) for e in world.query(SubstanceComponent))
    assert sub.active is True
    run_signaling(world, env, {0: [trigger]}, False, 1, 2)
    sub = next(e.get_component(SubstanceComponent) for e in world.query(SubstanceComponent))
    assert sub.active is False


def test_signaling_irreversible_toxin_stays_active_after_trigger_loss(
    add_plant: Callable[..., int], add_swarm: Callable[..., int]
) -> None:
    """Verify irreversible toxins stay active even after trigger disappearance."""
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=2, num_toxins=2)
    add_plant(world, 2, 2, species_id=0, energy=12.0)
    swarm_id = add_swarm(world, 2, 2, species_id=0, pop=6)
    trigger = TriggerConditionSchema(
        initiator=HerbivoreAttackInitiator(herbivore_species_id=0, min_herbivore_population=5),
        aftereffect_ticks=0,
        action=SynthesizeSubstanceAction(substance_id=1, synthesis_duration=1, is_toxin=True, irreversible=True),
    )
    run_signaling(world, env, {0: [trigger]}, False, 1, 0)
    world.unregister_position(swarm_id, 2, 2)
    world.collect_garbage([swarm_id])
    run_signaling(world, env, {0: [trigger]}, False, 1, 1)
    sub = next(e.get_component(SubstanceComponent) for e in world.query(SubstanceComponent))
    assert sub.active is True
    assert sub.triggered_this_tick is True
    assert float(env.toxin_layers[1].max()) > 0.0


def test_signaling_toxin_lethal_kill_garbage_collects_swarm_immediately(
    add_plant: Callable[..., int], add_swarm: Callable[..., int]
) -> None:
    """Validate that a swarm annihilated by a lethal toxin is immediately GC'd within signaling phase."""
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=1, num_toxins=2)
    add_plant(world, 2, 2, species_id=0, energy=20.0)
    swarm_id = add_swarm(world, 2, 2, species_id=0, pop=5)
    trigger = TriggerConditionSchema(
        initiator=HerbivoreAttackInitiator(herbivore_species_id=0, min_herbivore_population=1),
        action=SynthesizeSubstanceAction(
            substance_id=1, synthesis_duration=1, is_toxin=True, lethal=True, lethality_rate=100.0
        ),
    )
    run_signaling(world, env, {0: [trigger]}, False, 1, 0)
    assert list(world.query(SwarmComponent)) == []
    assert not world.has_entity(swarm_id)


async def test_signaling_relay_splits_fixed_budget_across_air_and_roots(
    add_plant: Callable[..., int],
    add_swarm: Callable[..., int],
) -> None:
    """Signal emission is mass-conservative across airborne and root-relay targets."""
    world = ECSWorld()
    env = GridEnvironment(width=7, height=5, num_signals=1, num_toxins=1)
    env.diffuse_signals = lambda **_kwargs: None  # type: ignore[method-assign]
    source_id = add_plant(world, 3, 2, species_id=0, energy=20.0)
    n1 = add_plant(world, 2, 2, species_id=0, energy=20.0)
    n2 = add_plant(world, 4, 2, species_id=0, energy=20.0)
    source = world.get_entity(source_id).get_component(PlantComponent)
    source.mycorrhizal_connections = {n1, n2}
    add_swarm(world, 3, 2, species_id=0, pop=3)
    trigger = TriggerConditionSchema(
        initiator=HerbivoreAttackInitiator(herbivore_species_id=0, min_herbivore_population=1),
        action=SynthesizeSubstanceAction(substance_id=0, synthesis_duration=1, is_toxin=False),
    )
    run_signaling(world, env, {0: [trigger]}, False, 1, 0)
    total_signal_mass = float(env.signal_layers[0].sum())
    assert total_signal_mass == pytest.approx(SUBSTANCE_EMIT_RATE)


def test_signaling_aborts_incomplete_synthesis_when_trigger_leaves(
    add_plant: Callable[..., int],
    add_swarm: Callable[..., int],
) -> None:
    """Verify incomplete synthesis is cleared and aborted if triggering threat leaves mid-synthesis."""
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=2, num_toxins=2)
    add_plant(world, 2, 2, species_id=0, energy=12.0)
    swarm_id = add_swarm(world, 2, 2, species_id=0, pop=6)

    # Synthesis duration is 3 ticks
    trigger = TriggerConditionSchema(
        initiator=HerbivoreAttackInitiator(herbivore_species_id=0, min_herbivore_population=5),
        action=SynthesizeSubstanceAction(substance_id=1, synthesis_duration=3, is_toxin=True),
    )

    # Tick 0: Trigger fires, synthesis starts (synthesis_remaining decrements from 3 to 2)
    run_signaling(world, env, {0: [trigger]}, False, 1, 0)
    sub = next(e.get_component(SubstanceComponent) for e in world.query(SubstanceComponent))
    assert sub.active is False
    assert sub.synthesis_remaining == 2
    assert sub.triggered_this_tick is True

    # Swarm leaves before synthesis completes
    world.unregister_position(swarm_id, 2, 2)
    world.collect_garbage([swarm_id])

    # Tick 1: Threat is gone. Incomplete synthesis must be aborted and synthesis_remaining cleared.
    run_signaling(world, env, {0: [trigger]}, False, 1, 1)
    sub = next(e.get_component(SubstanceComponent) for e in world.query(SubstanceComponent))
    assert sub.active is False
    assert sub.synthesis_remaining == 0
    assert sub.triggered_this_tick is False
