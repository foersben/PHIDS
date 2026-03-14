from __future__ import annotations

import asyncio
import logging

from phids.api.schemas import (
    DietCompatibilityMatrix,
    FloraSpeciesParams,
    InitialPlantPlacement,
    InitialSwarmPlacement,
    PredatorSpeciesParams,
    SimulationConfig,
)
from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.ecs import ECSWorld
from phids.engine.loop import SimulationLoop
from phids.telemetry.conditions import check_termination


def _base_config(max_ticks: int = 20) -> SimulationConfig:
    return SimulationConfig(
        grid_width=8,
        grid_height=8,
        max_ticks=max_ticks,
        tick_rate_hz=50.0,
        num_signals=2,
        num_toxins=2,
        wind_x=0.0,
        wind_y=0.0,
        flora_species=[
            FloraSpeciesParams(
                species_id=0,
                name="flora-0",
                base_energy=8.0,
                max_energy=30.0,
                growth_rate=2.0,
                survival_threshold=1.0,
                reproduction_interval=3,
                seed_min_dist=1.0,
                seed_max_dist=2.0,
                seed_energy_cost=1.0,
                triggers=[],
            )
        ],
        predator_species=[
            PredatorSpeciesParams(
                species_id=0,
                name="pred-0",
                energy_min=1.0,
                velocity=1,
                consumption_rate=1.0,
            )
        ],
        diet_matrix=DietCompatibilityMatrix(rows=[[True]]),
        initial_plants=[InitialPlantPlacement(species_id=0, x=2, y=2, energy=10.0)],
        initial_swarms=[InitialSwarmPlacement(species_id=0, x=2, y=2, population=3, energy=3.0)],
    )


def _world_with_counts(plant_species: list[int], predator_species: list[int]) -> ECSWorld:
    world = ECSWorld()
    for idx, sp in enumerate(plant_species):
        e = world.create_entity()
        p = PlantComponent(
            entity_id=e.entity_id,
            species_id=sp,
            x=idx,
            y=0,
            energy=5.0,
            max_energy=10.0,
            base_energy=5.0,
            growth_rate=1.0,
            survival_threshold=1.0,
            reproduction_interval=2,
            seed_min_dist=1.0,
            seed_max_dist=2.0,
            seed_energy_cost=1.0,
        )
        world.add_component(e.entity_id, p)

    for idx, sp in enumerate(predator_species):
        e = world.create_entity()
        s = SwarmComponent(
            entity_id=e.entity_id,
            species_id=sp,
            x=idx,
            y=1,
            population=4,
            initial_population=4,
            energy=0.0,
            energy_min=1.0,
            velocity=1,
            consumption_rate=1.0,
        )
        world.add_component(e.entity_id, s)

    return world


def test_termination_z1_max_ticks() -> None:
    world = _world_with_counts([0], [0])
    result = check_termination(world, tick=10, max_ticks=10)
    assert result.terminated is True
    assert result.reason.startswith("Z1")


def test_termination_z2_and_z4_specific_species_extinction() -> None:
    world = _world_with_counts([0], [0])

    z2 = check_termination(world, tick=0, max_ticks=100, z2_flora_species=1)
    assert z2.terminated is True
    assert "Z2" in z2.reason

    z4 = check_termination(world, tick=0, max_ticks=100, z4_predator_species=1)
    assert z4.terminated is True
    assert "Z4" in z4.reason


def test_termination_z3_z5_all_extinction() -> None:
    world = _world_with_counts([], [])

    z3 = check_termination(world, tick=0, max_ticks=100)
    assert z3.terminated is True
    assert "Z3" in z3.reason


def test_termination_z6_z7_thresholds() -> None:
    world = _world_with_counts([0], [0])

    z6 = check_termination(world, tick=0, max_ticks=100, z6_max_flora_energy=1.0)
    assert z6.terminated is True
    assert "Z6" in z6.reason

    z7 = check_termination(world, tick=0, max_ticks=100, z7_max_predator_population=1)
    assert z7.terminated is True
    assert "Z7" in z7.reason


def test_simulation_loop_step_updates_replay_and_telemetry() -> None:
    loop = SimulationLoop(_base_config(max_ticks=30))

    before_tick = loop.tick
    result = asyncio.run(loop.step())

    assert result.terminated is False
    assert loop.tick == before_tick + 1
    assert len(loop.replay) == 1
    assert loop.telemetry.dataframe.height >= 1
    latest = loop.telemetry.get_latest_metrics()
    assert latest is not None
    assert "death_herbivore_feeding" in latest
    assert "death_defense_maintenance" in latest


def test_simulation_loop_terminates_when_z1_reached(caplog) -> None:
    loop = SimulationLoop(_base_config(max_ticks=1))
    loop.tick = loop.config.max_ticks

    with caplog.at_level(logging.INFO, logger="phids.engine.loop"):
        result = asyncio.run(loop.step())

    assert result.terminated is True
    assert loop.terminated is True
    assert loop.running is False
    assert loop.termination_reason is not None
    assert "Simulation terminated at tick" in caplog.text
