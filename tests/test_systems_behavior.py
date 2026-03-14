from __future__ import annotations

import random

import pytest

from phids.api.schemas import (
    AllOfConditionSchema,
    AnyOfConditionSchema,
    EnemyPresenceConditionSchema,
    FloraSpeciesParams,
    SubstanceActiveConditionSchema,
    TriggerConditionSchema,
)
from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.components.substances import SubstanceComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.engine.systems.interaction import run_interaction
from phids.engine.systems.lifecycle import run_lifecycle
from phids.engine.systems.signaling import run_signaling


def _flora_params(species_id: int = 0) -> FloraSpeciesParams:
    return FloraSpeciesParams(
        species_id=species_id,
        name=f"flora-{species_id}",
        base_energy=10.0,
        max_energy=30.0,
        growth_rate=5.0,
        survival_threshold=1.0,
        reproduction_interval=1,
        seed_min_dist=1.0,
        seed_max_dist=1.0,
        seed_energy_cost=2.0,
        triggers=[],
    )


def _add_plant(world: ECSWorld, x: int, y: int, species_id: int = 0, energy: float = 10.0) -> int:
    e = world.create_entity()
    p = PlantComponent(
        entity_id=e.entity_id,
        species_id=species_id,
        x=x,
        y=y,
        energy=energy,
        max_energy=30.0,
        base_energy=10.0,
        growth_rate=5.0,
        survival_threshold=1.0,
        reproduction_interval=2,
        seed_min_dist=1.0,
        seed_max_dist=2.0,
        seed_energy_cost=2.0,
    )
    world.add_component(e.entity_id, p)
    world.register_position(e.entity_id, x, y)
    return e.entity_id


def _add_swarm(
    world: ECSWorld,
    x: int,
    y: int,
    species_id: int = 0,
    pop: int = 10,
    reproduction_divisor: float = 1.0,
) -> int:
    e = world.create_entity()
    s = SwarmComponent(
        entity_id=e.entity_id,
        species_id=species_id,
        x=x,
        y=y,
        population=pop,
        initial_population=max(1, pop // 2),
        energy=0.0,
        energy_min=1.0,
        velocity=1,
        consumption_rate=1.0,
        reproduction_energy_divisor=reproduction_divisor,
    )
    world.add_component(e.entity_id, s)
    world.register_position(e.entity_id, x, y)
    return e.entity_id


def test_lifecycle_establishes_mycorrhizal_connections_with_cost() -> None:
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=1, num_toxins=1)

    p1 = _add_plant(world, 1, 1, species_id=0, energy=10.0)
    p2 = _add_plant(world, 1, 2, species_id=0, energy=10.0)

    params = {0: _flora_params(0)}
    run_lifecycle(
        world,
        env,
        tick=1,
        flora_species_params=params,
        mycorrhizal_connection_cost=1.5,
        mycorrhizal_growth_interval_ticks=1,
        mycorrhizal_inter_species=False,
    )

    plant1 = world.get_entity(p1).get_component(PlantComponent)
    plant2 = world.get_entity(p2).get_component(PlantComponent)

    assert p2 in plant1.mycorrhizal_connections
    assert p1 in plant2.mycorrhizal_connections
    assert plant1.energy < 10.0
    assert plant2.energy < 10.0


def test_lifecycle_respects_interspecies_connection_switch() -> None:
    world = ECSWorld()
    env = GridEnvironment(width=4, height=4, num_signals=1, num_toxins=1)

    p1 = _add_plant(world, 1, 1, species_id=0, energy=8.0)
    p2 = _add_plant(world, 2, 1, species_id=1, energy=8.0)

    params = {0: _flora_params(0), 1: _flora_params(1)}
    run_lifecycle(
        world,
        env,
        tick=1,
        flora_species_params=params,
        mycorrhizal_connection_cost=1.0,
        mycorrhizal_growth_interval_ticks=1,
        mycorrhizal_inter_species=False,
    )

    plant1 = world.get_entity(p1).get_component(PlantComponent)
    assert p2 not in plant1.mycorrhizal_connections


def test_lifecycle_mycorrhiza_grows_one_link_per_interval() -> None:
    world = ECSWorld()
    env = GridEnvironment(width=6, height=4, num_signals=1, num_toxins=1)

    p1 = _add_plant(world, 1, 1, species_id=0, energy=12.0)
    p2 = _add_plant(world, 2, 1, species_id=0, energy=12.0)
    p3 = _add_plant(world, 3, 1, species_id=0, energy=12.0)

    for entity_id in (p1, p2, p3):
        plant = world.get_entity(entity_id).get_component(PlantComponent)
        plant.reproduction_interval = 999
        plant.seed_energy_cost = 999.0

    params = {0: _flora_params(0)}
    growth_interval = 4

    for tick in range(growth_interval - 1):
        run_lifecycle(
            world,
            env,
            tick=tick,
            flora_species_params=params,
            mycorrhizal_connection_cost=1.0,
            mycorrhizal_growth_interval_ticks=growth_interval,
            mycorrhizal_inter_species=False,
        )

    plant1 = world.get_entity(p1).get_component(PlantComponent)
    plant2 = world.get_entity(p2).get_component(PlantComponent)
    plant3 = world.get_entity(p3).get_component(PlantComponent)
    assert plant1.mycorrhizal_connections == set()
    assert plant2.mycorrhizal_connections == set()
    assert plant3.mycorrhizal_connections == set()

    run_lifecycle(
        world,
        env,
        tick=growth_interval - 1,
        flora_species_params=params,
        mycorrhizal_connection_cost=1.0,
        mycorrhizal_growth_interval_ticks=growth_interval,
        mycorrhizal_inter_species=False,
    )

    plant1 = world.get_entity(p1).get_component(PlantComponent)
    plant2 = world.get_entity(p2).get_component(PlantComponent)
    plant3 = world.get_entity(p3).get_component(PlantComponent)
    first_links = {
        tuple(sorted((left, right)))
        for left, plant in ((p1, plant1), (p2, plant2), (p3, plant3))
        for right in plant.mycorrhizal_connections
        if left < right
    }
    assert first_links in ({(p1, p2)}, {(p2, p3)})

    run_lifecycle(
        world,
        env,
        tick=(growth_interval * 2) - 1,
        flora_species_params=params,
        mycorrhizal_connection_cost=1.0,
        mycorrhizal_growth_interval_ticks=growth_interval,
        mycorrhizal_inter_species=False,
    )

    plant2 = world.get_entity(p2).get_component(PlantComponent)
    plant3 = world.get_entity(p3).get_component(PlantComponent)
    plant1 = world.get_entity(p1).get_component(PlantComponent)
    final_links = {
        tuple(sorted((left, right)))
        for left, plant in ((p1, plant1), (p2, plant2), (p3, plant3))
        for right in plant.mycorrhizal_connections
        if left < right
    }
    assert final_links == {(p1, p2), (p2, p3)}
    assert plant2.mycorrhizal_connections == {p1, p3}
    assert plant3.mycorrhizal_connections == {p2}


def test_lifecycle_mycorrhiza_can_select_non_top_left_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = ECSWorld()
    env = GridEnvironment(width=6, height=4, num_signals=1, num_toxins=1)

    p1 = _add_plant(world, 1, 1, species_id=0, energy=12.0)
    p2 = _add_plant(world, 2, 1, species_id=0, energy=12.0)
    p3 = _add_plant(world, 3, 1, species_id=0, energy=12.0)

    for entity_id in (p1, p2, p3):
        plant = world.get_entity(entity_id).get_component(PlantComponent)
        plant.reproduction_interval = 999
        plant.seed_energy_cost = 999.0

    monkeypatch.setattr(random, "choice", lambda seq: seq[-1])
    run_lifecycle(
        world,
        env,
        tick=0,
        flora_species_params={0: _flora_params(0)},
        mycorrhizal_connection_cost=1.0,
        mycorrhizal_growth_interval_ticks=1,
        mycorrhizal_inter_species=False,
    )

    plant2 = world.get_entity(p2).get_component(PlantComponent)
    plant3 = world.get_entity(p3).get_component(PlantComponent)
    assert plant2.mycorrhizal_connections == {p3}
    assert plant3.mycorrhizal_connections == {p2}


def test_interaction_diet_matrix_blocks_incompatible_feeding() -> None:
    world = ECSWorld()
    env = GridEnvironment(width=4, height=4, num_signals=1, num_toxins=1)

    plant_id = _add_plant(world, 1, 1, species_id=0, energy=10.0)
    swarm_id = _add_swarm(world, 1, 1, species_id=0, pop=5)

    plant = world.get_entity(plant_id).get_component(PlantComponent)
    swarm = world.get_entity(swarm_id).get_component(SwarmComponent)
    initial_energy = plant.energy

    run_interaction(world, env, diet_matrix=[[False]], tick=0)

    assert plant.energy == pytest.approx(initial_energy)
    assert swarm.energy == pytest.approx(0.0)
    assert swarm.population < 5

    env = GridEnvironment(width=4, height=4, num_signals=1, num_toxins=1)

    sid = _add_swarm(world, 1, 1, species_id=0, pop=10)
    swarm = world.get_entity(sid).get_component(SwarmComponent)
    swarm.initial_population = 5
    swarm.energy = 0.0

    run_interaction(world, env, diet_matrix=[[False]], tick=0)

    swarms = [e.get_component(SwarmComponent) for e in world.query(SwarmComponent)]
    assert len(swarms) >= 2
    assert sum(s.population for s in swarms) >= 10


def test_interaction_reproduction_can_trigger_same_tick_mitosis() -> None:
    world = ECSWorld()
    env = GridEnvironment(width=4, height=4, num_signals=1, num_toxins=1)

    sid = _add_swarm(world, 1, 1, species_id=0, pop=9)
    swarm = world.get_entity(sid).get_component(SwarmComponent)
    swarm.initial_population = 5
    swarm.energy_upkeep_per_individual = 0.0
    swarm.energy = 9.0

    run_interaction(world, env, diet_matrix=[[False]], tick=0)

    swarms = [e.get_component(SwarmComponent) for e in world.query(SwarmComponent)]
    assert len(swarms) == 2
    assert sum(s.population for s in swarms) == 10


def test_interaction_flow_field_movement_chooses_strongest_gradient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = ECSWorld()
    env = GridEnvironment(width=3, height=1, num_signals=1, num_toxins=1)
    env.flow_field[0, 0] = 9.0
    env.flow_field[1, 0] = 1.0
    env.flow_field[2, 0] = 10.0

    sid = _add_swarm(world, 1, 0, species_id=0, pop=4)
    swarm = world.get_entity(sid).get_component(SwarmComponent)

    monkeypatch.setattr(
        random,
        "choices",
        lambda seq, weights, k: [seq[weights.index(max(weights))]],
    )

    run_interaction(world, env, diet_matrix=[[False]], tick=0)

    assert (swarm.x, swarm.y) == (2, 0)


def test_interaction_moved_swarm_does_not_feed_in_same_tick(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = ECSWorld()
    env = GridEnvironment(width=3, height=1, num_signals=1, num_toxins=1)
    env.flow_field[0, 0] = 0.0
    env.flow_field[1, 0] = 1.0
    env.flow_field[2, 0] = 5.0

    plant_id = _add_plant(world, 2, 0, species_id=0, energy=10.0)
    swarm_id = _add_swarm(world, 1, 0, species_id=0, pop=5)
    swarm = world.get_entity(swarm_id).get_component(SwarmComponent)
    swarm.energy_upkeep_per_individual = 0.0

    monkeypatch.setattr(
        random,
        "choices",
        lambda seq, weights, k: [seq[weights.index(max(weights))]],
    )

    run_interaction(world, env, diet_matrix=[[True]], tick=0)

    plant = world.get_entity(plant_id).get_component(PlantComponent)
    assert (swarm.x, swarm.y) == (2, 0)
    assert plant.energy == pytest.approx(10.0)
    assert swarm.energy == pytest.approx(0.0)


def test_interaction_mitosis_offspring_can_diverge_next_tick(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = ECSWorld()
    env = GridEnvironment(width=5, height=1, num_signals=1, num_toxins=1)
    env.flow_field[:, 0] = 1.0

    swarm_id = _add_swarm(world, 2, 0, species_id=0, pop=12)
    swarm = world.get_entity(swarm_id).get_component(SwarmComponent)
    swarm.initial_population = 6
    swarm.energy_upkeep_per_individual = 0.0

    run_interaction(world, env, diet_matrix=[[False]], tick=0)

    calls = {"count": 0}

    def _split_pick(
        seq: list[tuple[int, int]], weights: list[float], k: int
    ) -> list[tuple[int, int]]:
        del weights, k
        calls["count"] += 1
        return [seq[1] if calls["count"] == 1 else seq[2]]

    monkeypatch.setattr(random, "choices", _split_pick)

    run_interaction(world, env, diet_matrix=[[False]], tick=1)

    positions = {
        (entity.get_component(SwarmComponent).x, entity.get_component(SwarmComponent).y)
        for entity in world.query(SwarmComponent)
    }
    assert len(positions) == 2


def test_interaction_reproduction_divisor_limits_growth() -> None:
    world = ECSWorld()
    env = GridEnvironment(width=6, height=2, num_signals=1, num_toxins=1)

    fast_id = _add_swarm(world, 1, 0, species_id=0, pop=6, reproduction_divisor=1.0)
    slow_id = _add_swarm(world, 4, 0, species_id=0, pop=6, reproduction_divisor=2.0)

    fast = world.get_entity(fast_id).get_component(SwarmComponent)
    slow = world.get_entity(slow_id).get_component(SwarmComponent)
    fast.initial_population = 100
    slow.initial_population = 100
    fast.energy_upkeep_per_individual = 0.0
    slow.energy_upkeep_per_individual = 0.0
    fast.energy = 24.0
    slow.energy = 24.0

    run_interaction(world, env, diet_matrix=[[False]], tick=0)

    assert fast.population > slow.population
    assert fast.population == 10
    assert slow.population == 8


def test_interaction_mitosis_conserves_odd_population() -> None:
    world = ECSWorld()
    env = GridEnvironment(width=4, height=4, num_signals=1, num_toxins=1)

    sid = _add_swarm(world, 1, 1, species_id=0, pop=11)
    swarm = world.get_entity(sid).get_component(SwarmComponent)
    swarm.initial_population = 5
    swarm.energy_upkeep_per_individual = 0.0

    run_interaction(world, env, diet_matrix=[[False]], tick=0)

    swarms = [e.get_component(SwarmComponent) for e in world.query(SwarmComponent)]
    assert len(swarms) == 2
    assert sum(s.population for s in swarms) == 11
    assert sorted(s.population for s in swarms) == [5, 6]


def test_signaling_spawns_configured_toxin_and_applies_properties() -> None:
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=2, num_toxins=2)

    plant_id = _add_plant(world, 2, 2, species_id=0, energy=12.0)
    _add_swarm(world, 2, 2, species_id=0, pop=10)

    trigger = TriggerConditionSchema(
        predator_species_id=0,
        min_predator_population=5,
        substance_id=1,
        synthesis_duration=1,
        is_toxin=True,
        lethal=True,
        lethality_rate=0.5,
        repellent=True,
        repellent_walk_ticks=3,
        aftereffect_ticks=2,
        energy_cost_per_tick=1.0,
    )

    run_signaling(
        world,
        env,
        trigger_conditions={0: [trigger]},
        mycorrhizal_inter_species=False,
        signal_velocity=1,
        tick=0,
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


def test_signaling_aggregates_co_located_swarm_population_for_trigger_threshold() -> None:
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=2, num_toxins=2)

    _add_plant(world, 2, 2, species_id=0, energy=12.0)
    _add_swarm(world, 2, 2, species_id=0, pop=3)
    _add_swarm(world, 2, 2, species_id=0, pop=3)

    trigger = TriggerConditionSchema(
        predator_species_id=0,
        min_predator_population=5,
        substance_id=1,
        synthesis_duration=1,
        is_toxin=True,
    )

    run_signaling(
        world,
        env,
        trigger_conditions={0: [trigger]},
        mycorrhizal_inter_species=False,
        signal_velocity=1,
        tick=0,
    )

    subs = [e.get_component(SubstanceComponent) for e in world.query(SubstanceComponent)]
    assert len(subs) == 1
    assert subs[0].active is True


def test_signaling_toxin_deactivates_when_trigger_species_is_gone() -> None:
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=2, num_toxins=2)

    _add_plant(world, 2, 2, species_id=0, energy=12.0)
    triggering_swarm_id = _add_swarm(world, 2, 2, species_id=0, pop=6)
    _add_swarm(world, 2, 2, species_id=1, pop=10)

    trigger = TriggerConditionSchema(
        predator_species_id=0,
        min_predator_population=5,
        substance_id=1,
        synthesis_duration=1,
        is_toxin=True,
        aftereffect_ticks=0,
    )

    run_signaling(
        world,
        env,
        trigger_conditions={0: [trigger]},
        mycorrhizal_inter_species=False,
        signal_velocity=1,
        tick=0,
    )

    world.unregister_position(triggering_swarm_id, 2, 2)
    world.collect_garbage([triggering_swarm_id])

    run_signaling(
        world,
        env,
        trigger_conditions={0: [trigger]},
        mycorrhizal_inter_species=False,
        signal_velocity=1,
        tick=1,
    )

    sub = next(e.get_component(SubstanceComponent) for e in world.query(SubstanceComponent))
    assert sub.active is False
    assert float(env.toxin_layers[1].max()) == 0.0


def test_signaling_toxin_lingers_for_aftereffect_then_deactivates() -> None:
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=2, num_toxins=2)

    _add_plant(world, 2, 2, species_id=0, energy=12.0)
    swarm_id = _add_swarm(world, 2, 2, species_id=0, pop=6)

    trigger = TriggerConditionSchema(
        predator_species_id=0,
        min_predator_population=5,
        substance_id=1,
        synthesis_duration=1,
        is_toxin=True,
        aftereffect_ticks=2,
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


def test_signaling_irreversible_toxin_stays_active_after_trigger_loss() -> None:
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=2, num_toxins=2)

    _add_plant(world, 2, 2, species_id=0, energy=12.0)
    swarm_id = _add_swarm(world, 2, 2, species_id=0, pop=6)

    trigger = TriggerConditionSchema(
        predator_species_id=0,
        min_predator_population=5,
        substance_id=1,
        synthesis_duration=1,
        is_toxin=True,
        aftereffect_ticks=0,
        irreversible=True,
    )

    run_signaling(world, env, {0: [trigger]}, False, 1, 0)
    world.unregister_position(swarm_id, 2, 2)
    world.collect_garbage([swarm_id])

    run_signaling(world, env, {0: [trigger]}, False, 1, 1)
    sub = next(e.get_component(SubstanceComponent) for e in world.query(SubstanceComponent))
    assert sub.active is True
    assert sub.triggered_this_tick is True
    assert float(env.toxin_layers[1].max()) > 0.0


def test_signaling_signal_lingers_for_aftereffect_then_deactivates() -> None:
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=2, num_toxins=2)

    _add_plant(world, 2, 2, species_id=0, energy=12.0)
    swarm_id = _add_swarm(world, 2, 2, species_id=0, pop=6)

    trigger = TriggerConditionSchema(
        predator_species_id=0,
        min_predator_population=5,
        substance_id=1,
        synthesis_duration=1,
        is_toxin=False,
        aftereffect_ticks=2,
    )

    run_signaling(
        world,
        env,
        trigger_conditions={0: [trigger]},
        mycorrhizal_inter_species=False,
        signal_velocity=1,
        tick=0,
    )

    world.unregister_position(swarm_id, 2, 2)
    world.collect_garbage([swarm_id])

    run_signaling(world, env, {0: [trigger]}, False, 1, 1)
    sub = next(e.get_component(SubstanceComponent) for e in world.query(SubstanceComponent))
    assert sub.active is True

    run_signaling(world, env, {0: [trigger]}, False, 1, 2)
    sub = next(e.get_component(SubstanceComponent) for e in world.query(SubstanceComponent))
    assert sub.active is False


def test_signaling_signal_with_zero_aftereffect_stops_emitting_next_tick() -> None:
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=2, num_toxins=2)

    _add_plant(world, 2, 2, species_id=0, energy=12.0)
    swarm_id = _add_swarm(world, 2, 2, species_id=0, pop=6)

    trigger = TriggerConditionSchema(
        predator_species_id=0,
        min_predator_population=5,
        substance_id=1,
        synthesis_duration=1,
        is_toxin=False,
        aftereffect_ticks=0,
    )

    run_signaling(world, env, {0: [trigger]}, False, 1, 0)
    assert float(env.signal_layers[1].max()) > 0.0

    env.signal_layers[:] = 0.0
    env._signal_layers_write[:] = 0.0
    world.unregister_position(swarm_id, 2, 2)
    world.collect_garbage([swarm_id])

    run_signaling(world, env, {0: [trigger]}, False, 1, 1)

    sub = next(e.get_component(SubstanceComponent) for e in world.query(SubstanceComponent))
    assert sub.active is False
    assert float(env.signal_layers[1].max()) == 0.0


def test_signaling_owner_death_stops_emission_and_existing_signal_decays() -> None:
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=2, num_toxins=2)

    plant_id = _add_plant(world, 2, 2, species_id=0, energy=12.0)
    _add_swarm(world, 2, 2, species_id=0, pop=6)

    trigger = TriggerConditionSchema(
        predator_species_id=0,
        min_predator_population=5,
        substance_id=1,
        synthesis_duration=1,
        is_toxin=False,
        aftereffect_ticks=2,
    )

    run_signaling(world, env, {0: [trigger]}, False, 1, 0)
    env.signal_layers[1, 2, 2] = 1.0
    env._signal_layers_write[:] = env.signal_layers

    world.unregister_position(plant_id, 2, 2)
    world.collect_garbage([plant_id])

    run_signaling(world, env, {0: [trigger]}, False, 1, 1)

    assert float(env.signal_layers[1].max()) < 1.0
    assert list(world.query(SubstanceComponent)) == []


def test_signaling_preemptively_collects_inactive_orphaned_substances() -> None:
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=2, num_toxins=2)

    plant_id = _add_plant(world, 2, 2, species_id=0, energy=12.0)
    sub_entity = world.create_entity()
    world.add_component(
        sub_entity.entity_id,
        SubstanceComponent(
            entity_id=sub_entity.entity_id,
            substance_id=1,
            owner_plant_id=plant_id,
            is_toxin=True,
            synthesis_duration=2,
            synthesis_remaining=1,
            active=False,
        ),
    )

    world.unregister_position(plant_id, 2, 2)
    world.collect_garbage([plant_id])

    run_signaling(world, env, {}, False, 1, 0)

    assert list(world.query(SubstanceComponent)) == []


def test_signaling_inactive_substance_does_not_reactivate_without_trigger() -> None:
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=2, num_toxins=2)

    _add_plant(world, 2, 2, species_id=0, energy=12.0)
    swarm_id = _add_swarm(world, 2, 2, species_id=0, pop=6)

    trigger = TriggerConditionSchema(
        predator_species_id=0,
        min_predator_population=5,
        substance_id=1,
        synthesis_duration=1,
        is_toxin=False,
        aftereffect_ticks=0,
    )

    run_signaling(world, env, {0: [trigger]}, False, 1, 0)
    world.unregister_position(swarm_id, 2, 2)
    world.collect_garbage([swarm_id])

    run_signaling(world, env, {0: [trigger]}, False, 1, 1)
    sub = next(e.get_component(SubstanceComponent) for e in world.query(SubstanceComponent))
    assert sub.active is False

    run_signaling(world, env, {0: [trigger]}, False, 1, 2)
    sub = next(e.get_component(SubstanceComponent) for e in world.query(SubstanceComponent))
    assert sub.active is False


def test_signaling_applies_toxin_damage_once_per_active_layer() -> None:
    world = ECSWorld()
    env = GridEnvironment(width=6, height=6, num_signals=2, num_toxins=2)

    _add_plant(world, 1, 1, species_id=0, energy=12.0)
    _add_plant(world, 4, 4, species_id=0, energy=12.0)
    swarm_a_id = _add_swarm(world, 1, 1, species_id=0, pop=10)
    swarm_b_id = _add_swarm(world, 4, 4, species_id=0, pop=10)

    trigger = TriggerConditionSchema(
        predator_species_id=0,
        min_predator_population=1,
        substance_id=1,
        synthesis_duration=1,
        is_toxin=True,
        lethal=True,
        lethality_rate=2.0,
    )

    run_signaling(world, env, {0: [trigger]}, False, 1, 0)

    swarm_a = world.get_entity(swarm_a_id).get_component(SwarmComponent)
    swarm_b = world.get_entity(swarm_b_id).get_component(SwarmComponent)
    assert swarm_a.population == 8
    assert swarm_b.population == 8
    assert float(env.toxin_layers[1, 1, 1]) > 0.0
    assert float(env.toxin_layers[1, 4, 4]) > 0.0


def test_signaling_toxins_remain_local_and_do_not_diffuse() -> None:
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=2, num_toxins=2)

    _add_plant(world, 2, 2, species_id=0, energy=12.0)
    swarm_id = _add_swarm(world, 2, 2, species_id=0, pop=6)

    trigger = TriggerConditionSchema(
        predator_species_id=0,
        min_predator_population=1,
        substance_id=1,
        synthesis_duration=1,
        is_toxin=True,
        aftereffect_ticks=1,
    )

    run_signaling(world, env, {0: [trigger]}, False, 1, 0)

    assert float(env.toxin_layers[1, 2, 2]) > 0.0
    assert float(env.toxin_layers[1, 2, 3]) == 0.0
    assert float(env.toxin_layers[1, 3, 2]) == 0.0

    world.unregister_position(swarm_id, 2, 2)
    world.collect_garbage([swarm_id])

    run_signaling(world, env, {0: [trigger]}, False, 1, 1)

    assert float(env.toxin_layers[1, 2, 2]) > 0.0
    assert float(env.toxin_layers[1, 2, 3]) == 0.0
    assert float(env.toxin_layers[1, 3, 2]) == 0.0


def test_signaling_precursor_gate_blocks_activation() -> None:
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=2, num_toxins=2)

    _add_plant(world, 1, 1, species_id=0, energy=10.0)
    _add_swarm(world, 1, 1, species_id=0, pop=10)

    trigger = TriggerConditionSchema(
        predator_species_id=0,
        min_predator_population=1,
        substance_id=1,
        synthesis_duration=1,
        is_toxin=True,
        activation_condition=SubstanceActiveConditionSchema(substance_id=0),
    )

    run_signaling(
        world,
        env,
        trigger_conditions={0: [trigger]},
        mycorrhizal_inter_species=False,
        signal_velocity=1,
        tick=0,
    )

    sub = next(e.get_component(SubstanceComponent) for e in world.query(SubstanceComponent))
    assert sub.active is False


def test_signaling_all_of_gate_supports_mixed_enemy_and_substance_predicates() -> None:
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=2, num_toxins=2)

    _add_plant(world, 2, 2, species_id=0, energy=12.0)
    _add_swarm(world, 2, 2, species_id=0, pop=6)
    _add_swarm(world, 2, 2, species_id=1, pop=3)

    signal_trigger = TriggerConditionSchema(
        predator_species_id=0,
        min_predator_population=5,
        substance_id=0,
        synthesis_duration=1,
        is_toxin=False,
    )
    toxin_trigger = TriggerConditionSchema(
        predator_species_id=0,
        min_predator_population=5,
        substance_id=1,
        synthesis_duration=1,
        is_toxin=True,
        activation_condition=AllOfConditionSchema(
            conditions=[
                SubstanceActiveConditionSchema(substance_id=0),
                EnemyPresenceConditionSchema(predator_species_id=1, min_predator_population=2),
            ]
        ),
    )

    run_signaling(world, env, {0: [signal_trigger, toxin_trigger]}, False, 1, 0)

    substances = sorted(
        (entity.get_component(SubstanceComponent) for entity in world.query(SubstanceComponent)),
        key=lambda substance: substance.substance_id,
    )
    assert len(substances) == 2
    assert substances[0].active is True
    assert substances[1].active is True


def test_signaling_any_of_gate_allows_alternative_enemy_or_substance_paths() -> None:
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=2, num_toxins=2)

    _add_plant(world, 2, 2, species_id=0, energy=12.0)
    _add_swarm(world, 2, 2, species_id=0, pop=6)
    _add_swarm(world, 2, 2, species_id=1, pop=2)

    toxin_trigger = TriggerConditionSchema(
        predator_species_id=0,
        min_predator_population=5,
        substance_id=1,
        synthesis_duration=1,
        is_toxin=True,
        activation_condition=AnyOfConditionSchema(
            conditions=[
                SubstanceActiveConditionSchema(substance_id=0),
                EnemyPresenceConditionSchema(predator_species_id=1, min_predator_population=2),
            ]
        ),
    )

    run_signaling(world, env, {0: [toxin_trigger]}, False, 1, 0)

    sub = next(e.get_component(SubstanceComponent) for e in world.query(SubstanceComponent))
    assert sub.active is True


def test_repelled_swarm_performs_random_walk(monkeypatch: pytest.MonkeyPatch) -> None:
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=1, num_toxins=1)

    sid = _add_swarm(world, 2, 2, species_id=0, pop=6)
    swarm = world.get_entity(sid).get_component(SwarmComponent)
    swarm.repelled = True
    swarm.repelled_ticks_remaining = 2

    monkeypatch.setattr(random, "choice", lambda seq: seq[1])
    run_interaction(world, env, diet_matrix=[[False]], tick=0)

    assert (swarm.x, swarm.y) != (2, 2)
    assert swarm.repelled_ticks_remaining == 1
