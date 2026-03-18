"""Integration checks for lifecycle reproduction gates and culling behavior."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from phids.api.schemas import SimulationConfig
from phids.engine.components.plant import PlantComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.engine.systems.lifecycle import _attempt_reproduction, run_lifecycle


def test_attempt_reproduction_handles_success_and_blocking_cases(
    monkeypatch: pytest.MonkeyPatch,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify reproduction succeeds on free cells and is blocked by occupancy or energy gates."""
    params = config_builder().flora_species[0]
    flora_params = {0: params}
    env = GridEnvironment(width=5, height=5, num_signals=1, num_toxins=1)

    success_world = ECSWorld()
    parent_entity = success_world.create_entity()
    parent = PlantComponent(
        entity_id=parent_entity.entity_id,
        species_id=0,
        x=2,
        y=2,
        energy=10.0,
        max_energy=20.0,
        base_energy=10.0,
        growth_rate=5.0,
        survival_threshold=1.0,
        reproduction_interval=1,
        seed_min_dist=1.0,
        seed_max_dist=1.0,
        seed_energy_cost=2.0,
    )
    parent.last_reproduction_tick = -10
    success_world.add_component(parent_entity.entity_id, parent)
    success_world.register_position(parent_entity.entity_id, 2, 2)

    values = iter([0.0, 1.0])
    monkeypatch.setattr("phids.engine.systems.lifecycle.random.uniform", lambda a, b: next(values))
    offspring = _attempt_reproduction(parent, 5, success_world, env, flora_params)
    assert len(offspring) == 1
    assert offspring[0].x == 3
    assert offspring[0].y == 2
    assert offspring[0].last_reproduction_tick == 5

    blocked_world = ECSWorld()
    blocked_parent_entity = blocked_world.create_entity()
    blocked_parent = PlantComponent(
        entity_id=blocked_parent_entity.entity_id,
        species_id=0,
        x=2,
        y=2,
        energy=10.0,
        max_energy=20.0,
        base_energy=10.0,
        growth_rate=5.0,
        survival_threshold=1.0,
        reproduction_interval=1,
        seed_min_dist=1.0,
        seed_max_dist=1.0,
        seed_energy_cost=2.0,
    )
    blocked_parent.last_reproduction_tick = -10
    blocked_world.add_component(blocked_parent_entity.entity_id, blocked_parent)
    blocked_world.register_position(blocked_parent_entity.entity_id, 2, 2)

    occupant_entity = blocked_world.create_entity()
    occupant = PlantComponent(
        entity_id=occupant_entity.entity_id,
        species_id=0,
        x=3,
        y=2,
        energy=10.0,
        max_energy=20.0,
        base_energy=10.0,
        growth_rate=5.0,
        survival_threshold=1.0,
        reproduction_interval=1,
        seed_min_dist=1.0,
        seed_max_dist=1.0,
        seed_energy_cost=2.0,
    )
    blocked_world.add_component(occupant_entity.entity_id, occupant)
    blocked_world.register_position(occupant_entity.entity_id, 3, 2)

    values = iter([0.0, 1.0])
    monkeypatch.setattr("phids.engine.systems.lifecycle.random.uniform", lambda a, b: next(values))
    blocked = _attempt_reproduction(blocked_parent, 5, blocked_world, env, flora_params)
    assert blocked == []
    assert blocked_parent.energy == pytest.approx(10.0)

    low_energy_parent = PlantComponent(
        entity_id=99,
        species_id=0,
        x=0,
        y=0,
        energy=1.0,
        max_energy=20.0,
        base_energy=10.0,
        growth_rate=5.0,
        survival_threshold=1.0,
        reproduction_interval=1,
        seed_min_dist=1.0,
        seed_max_dist=1.0,
        seed_energy_cost=2.0,
    )
    assert _attempt_reproduction(low_energy_parent, 5, blocked_world, env, flora_params) == []

    threshold_parent = PlantComponent(
        entity_id=100,
        species_id=0,
        x=0,
        y=0,
        energy=2.5,
        max_energy=20.0,
        base_energy=10.0,
        growth_rate=5.0,
        survival_threshold=1.0,
        reproduction_interval=1,
        seed_min_dist=1.0,
        seed_max_dist=1.0,
        seed_energy_cost=2.0,
    )
    threshold_parent.last_reproduction_tick = -10
    assert _attempt_reproduction(threshold_parent, 5, blocked_world, env, flora_params) == []
    assert threshold_parent.energy == pytest.approx(2.5)


def test_newborn_reproduction_respects_cooldown_and_energy_constraints(
    monkeypatch: pytest.MonkeyPatch,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify newborns reproduce only after cooldown expiry and sufficient energy accrual."""
    params = config_builder().flora_species[0]
    params.reproduction_interval = 3
    params.seed_energy_cost = 4.0
    params.seed_min_dist = 1.0
    params.seed_max_dist = 1.0
    flora_params = {0: params}

    env = GridEnvironment(width=7, height=7, num_signals=1, num_toxins=1)
    world = ECSWorld()

    parent_entity = world.create_entity()
    parent = PlantComponent(
        entity_id=parent_entity.entity_id,
        species_id=0,
        x=2,
        y=3,
        energy=20.0,
        max_energy=40.0,
        base_energy=10.0,
        growth_rate=5.0,
        survival_threshold=1.0,
        reproduction_interval=params.reproduction_interval,
        seed_min_dist=params.seed_min_dist,
        seed_max_dist=params.seed_max_dist,
        seed_energy_cost=params.seed_energy_cost,
    )
    parent.last_reproduction_tick = -100
    world.add_component(parent_entity.entity_id, parent)
    world.register_position(parent_entity.entity_id, parent.x, parent.y)

    values = iter([0.0, 1.0, 0.0, 1.0])
    monkeypatch.setattr("phids.engine.systems.lifecycle.random.uniform", lambda a, b: next(values))

    birth_tick = 10
    newborn_list = _attempt_reproduction(parent, birth_tick, world, env, flora_params)
    assert len(newborn_list) == 1
    newborn = newborn_list[0]
    assert newborn.last_reproduction_tick == birth_tick

    for attempt_tick in range(birth_tick, birth_tick + newborn.reproduction_interval):
        newborn.energy = 100.0
        assert _attempt_reproduction(newborn, attempt_tick, world, env, flora_params) == []

    boundary_tick = birth_tick + newborn.reproduction_interval
    newborn.energy = newborn.seed_energy_cost - 0.1
    assert _attempt_reproduction(newborn, boundary_tick, world, env, flora_params) == []

    newborn.energy = newborn.seed_energy_cost + 5.0
    before_entities = len(list(world.query(PlantComponent)))
    offspring = _attempt_reproduction(newborn, boundary_tick, world, env, flora_params)
    after_entities = len(list(world.query(PlantComponent)))

    assert len(offspring) == 1
    assert after_entities == before_entities + 1


def test_attempt_reproduction_applies_downwind_bias_when_wind_is_present(
    monkeypatch: pytest.MonkeyPatch,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify non-zero local wind shifts anemochorous seed placement downwind."""
    params = config_builder().flora_species[0]
    params.seed_min_dist = 1.0
    params.seed_max_dist = 1.0
    params.seed_drop_height = 2.0
    params.seed_terminal_velocity = 0.5
    flora_params = {0: params}

    env = GridEnvironment(width=12, height=8, num_signals=1, num_toxins=1)
    env.set_uniform_wind(1.2, 0.0)
    world = ECSWorld()
    parent_entity = world.create_entity()
    parent = PlantComponent(
        entity_id=parent_entity.entity_id,
        species_id=0,
        x=3,
        y=3,
        energy=20.0,
        max_energy=20.0,
        base_energy=10.0,
        growth_rate=5.0,
        survival_threshold=1.0,
        reproduction_interval=1,
        seed_min_dist=1.0,
        seed_max_dist=1.0,
        seed_energy_cost=2.0,
        seed_drop_height=params.seed_drop_height,
        seed_terminal_velocity=params.seed_terminal_velocity,
    )
    parent.last_reproduction_tick = -10
    world.add_component(parent_entity.entity_id, parent)
    world.register_position(parent_entity.entity_id, parent.x, parent.y)

    values = iter([0.0, 1.0])
    monkeypatch.setattr("phids.engine.systems.lifecycle.random.uniform", lambda a, b: next(values))
    monkeypatch.setattr("phids.engine.systems.lifecycle.random.gauss", lambda mu, sigma: mu)

    offspring = _attempt_reproduction(parent, 5, world, env, flora_params)
    assert len(offspring) == 1
    assert offspring[0].x >= 8
    assert offspring[0].y == 3


def test_run_lifecycle_culls_dead_plants_and_prunes_missing_links(
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify lifecycle removes non-viable plants and prunes stale mycorrhizal references."""
    world = ECSWorld()
    env = GridEnvironment(width=4, height=4, num_signals=1, num_toxins=1)
    params = {0: config_builder().flora_species[0]}

    alive_entity = world.create_entity()
    alive_plant = PlantComponent(
        entity_id=alive_entity.entity_id,
        species_id=0,
        x=1,
        y=1,
        energy=5.0,
        max_energy=20.0,
        base_energy=10.0,
        growth_rate=0.0,
        survival_threshold=1.0,
        reproduction_interval=10,
        seed_min_dist=1.0,
        seed_max_dist=1.0,
        seed_energy_cost=2.0,
    )
    alive_plant.mycorrhizal_connections.add(999)
    world.add_component(alive_entity.entity_id, alive_plant)
    world.register_position(alive_entity.entity_id, 1, 1)

    dead_entity = world.create_entity()
    dead_plant = PlantComponent(
        entity_id=dead_entity.entity_id,
        species_id=0,
        x=2,
        y=1,
        energy=0.5,
        max_energy=20.0,
        base_energy=0.5,
        growth_rate=0.0,
        survival_threshold=1.0,
        reproduction_interval=10,
        seed_min_dist=1.0,
        seed_max_dist=1.0,
        seed_energy_cost=2.0,
    )
    world.add_component(dead_entity.entity_id, dead_plant)
    world.register_position(dead_entity.entity_id, 2, 1)

    run_lifecycle(
        world,
        env,
        tick=1,
        flora_species_params=params,
        mycorrhizal_connection_cost=10.0,
        mycorrhizal_inter_species=False,
    )

    assert world.has_entity(alive_entity.entity_id) is True
    assert world.has_entity(dead_entity.entity_id) is False
    assert alive_plant.mycorrhizal_connections == set()


def test_run_lifecycle_growth_is_incremental_at_late_ticks(
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify lifecycle growth remains incremental and stable at high tick counts."""
    world = ECSWorld()
    env = GridEnvironment(width=4, height=4, num_signals=1, num_toxins=1)
    params = {0: config_builder().flora_species[0]}

    plant_entity = world.create_entity()
    plant = PlantComponent(
        entity_id=plant_entity.entity_id,
        species_id=0,
        x=1,
        y=1,
        energy=10.0,
        max_energy=20.0,
        base_energy=10.0,
        growth_rate=5.0,
        survival_threshold=1.0,
        reproduction_interval=999,
        seed_min_dist=1.0,
        seed_max_dist=1.0,
        seed_energy_cost=999.0,
    )
    world.add_component(plant_entity.entity_id, plant)
    world.register_position(plant_entity.entity_id, 1, 1)

    run_lifecycle(world, env, tick=1000, flora_species_params=params)

    grown = world.get_entity(plant_entity.entity_id).get_component(PlantComponent)
    assert grown.energy == pytest.approx(10.5)
