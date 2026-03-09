from __future__ import annotations

import random

import pytest

from phytodynamics.api.schemas import FloraSpeciesParams, TriggerConditionSchema
from phytodynamics.engine.components.plant import PlantComponent
from phytodynamics.engine.components.swarm import SwarmComponent
from phytodynamics.engine.components.substances import SubstanceComponent
from phytodynamics.engine.core.biotope import GridEnvironment
from phytodynamics.engine.core.ecs import ECSWorld
from phytodynamics.engine.systems.interaction import run_interaction
from phytodynamics.engine.systems.lifecycle import run_lifecycle
from phytodynamics.engine.systems.signaling import run_signaling


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


def _add_swarm(world: ECSWorld, x: int, y: int, species_id: int = 0, pop: int = 10) -> int:
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
        mycorrhizal_inter_species=False,
    )

    plant1 = world.get_entity(p1).get_component(PlantComponent)
    assert p2 not in plant1.mycorrhizal_connections


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
    assert swarm.starvation_ticks >= 1


def test_interaction_mitosis_splits_population() -> None:
    world = ECSWorld()
    env = GridEnvironment(width=4, height=4, num_signals=1, num_toxins=1)

    sid = _add_swarm(world, 1, 1, species_id=0, pop=10)
    swarm = world.get_entity(sid).get_component(SwarmComponent)
    swarm.initial_population = 5
    swarm.energy = 0.0

    run_interaction(world, env, diet_matrix=[[False]], tick=0)

    swarms = [e.get_component(SwarmComponent) for e in world.query(SwarmComponent)]
    assert len(swarms) >= 2
    assert sum(s.population for s in swarms) >= 10


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
        precursor_signal_id=-1,
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


def test_signaling_precursor_gate_blocks_activation() -> None:
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=2, num_toxins=2)

    _add_plant(world, 1, 1, species_id=0, energy=10.0)
    _add_swarm(world, 1, 1, species_id=0, pop=10)

    trigger = TriggerConditionSchema(
        predator_species_id=0,
        min_predator_population=1,
        substance_id=1,
        synthesis_duration=0,
        is_toxin=True,
        precursor_signal_id=0,
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
