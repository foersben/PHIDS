"""Shared pytest fixtures for PHIDS test modules.

This fixture module provides lightweight, reusable ECS and biotope constructors
so unit and integration suites can avoid repetitive setup boilerplate while
preserving deterministic state isolation per test invocation.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncGenerator, Callable

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from phids.api import main as api_main
from phids.api.main import app
from phids.api.schemas import (
    DietCompatibilityMatrix,
    FloraSpeciesParams,
    HerbivoreSpeciesParams,
    InitialPlantPlacement,
    InitialSwarmPlacement,
    SimulationConfig,
)
from phids.api.ui_state import reset_draft
from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld


@pytest_asyncio.fixture(autouse=True)
async def safe_global_reset() -> AsyncGenerator[None, None]:
    """Reset global API state and cancel dangling simulation tasks around each test."""
    reset_draft()
    yield
    task = api_main._sim_task
    if task is not None and not task.done():
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    api_main._sim_task = None
    api_main._sim_loop = None
    api_main._sim_substance_names = {}


@pytest_asyncio.fixture
async def api_client() -> AsyncGenerator[AsyncClient, None]:
    """Provide a shared AsyncClient bound to the in-process FastAPI application."""
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
def empty_world() -> ECSWorld:
    """Return a fresh ECS world with no entities registered."""
    return ECSWorld()


@pytest.fixture
def standard_biotope() -> GridEnvironment:
    """Return a deterministic 50x50 environment with two signal and toxin layers."""
    return GridEnvironment(width=50, height=50, num_signals=2, num_toxins=2)


@pytest.fixture
def config_builder() -> Callable[..., SimulationConfig]:
    """Return a callable that builds the shared baseline SimulationConfig."""

    def _config(max_ticks: int = 5) -> SimulationConfig:
        return SimulationConfig(
            grid_width=8,
            grid_height=8,
            max_ticks=max_ticks,
            tick_rate_hz=20.0,
            num_signals=2,
            num_toxins=2,
            wind_x=0.0,
            wind_y=0.0,
            flora_species=[
                FloraSpeciesParams(
                    species_id=0,
                    name="grass",
                    base_energy=10.0,
                    max_energy=20.0,
                    growth_rate=5.0,
                    survival_threshold=1.0,
                    reproduction_interval=2,
                    seed_min_dist=1.0,
                    seed_max_dist=2.0,
                    seed_energy_cost=2.0,
                    triggers=[],
                )
            ],
            herbivore_species=[
                HerbivoreSpeciesParams(
                    species_id=0,
                    name="herbivore",
                    energy_min=1.0,
                    velocity=1,
                    consumption_rate=1.0,
                )
            ],
            diet_matrix=DietCompatibilityMatrix(rows=[[True]]),
            initial_plants=[InitialPlantPlacement(species_id=0, x=2, y=2, energy=10.0)],
            initial_swarms=[
                InitialSwarmPlacement(species_id=0, x=2, y=2, population=3, energy=3.0)
            ],
        )

    return _config


@pytest.fixture
def loop_config_builder() -> Callable[..., SimulationConfig]:
    """Return a callable that builds the shared loop/termination SimulationConfig baseline."""

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
            herbivore_species=[
                HerbivoreSpeciesParams(
                    species_id=0,
                    name="herbivore-0",
                    energy_min=1.0,
                    velocity=1,
                    consumption_rate=1.0,
                )
            ],
            diet_matrix=DietCompatibilityMatrix(rows=[[True]]),
            initial_plants=[InitialPlantPlacement(species_id=0, x=2, y=2, energy=10.0)],
            initial_swarms=[
                InitialSwarmPlacement(species_id=0, x=2, y=2, population=3, energy=3.0)
            ],
        )

    return _base_config


@pytest.fixture
def add_plant() -> Callable[..., int]:
    """Return a callable that spawns and registers a baseline plant entity."""

    def _add_plant(
        world: ECSWorld,
        x: int,
        y: int,
        species_id: int = 0,
        energy: float = 10.0,
        max_energy: float = 30.0,
        base_energy: float = 10.0,
        growth_rate: float = 5.0,
        survival_threshold: float = 1.0,
        reproduction_interval: int = 2,
        seed_min_dist: float = 1.0,
        seed_max_dist: float = 2.0,
        seed_energy_cost: float = 2.0,
    ) -> int:
        entity = world.create_entity()
        world.add_component(
            entity.entity_id,
            PlantComponent(
                entity_id=entity.entity_id,
                species_id=species_id,
                x=x,
                y=y,
                energy=energy,
                max_energy=max_energy,
                base_energy=base_energy,
                growth_rate=growth_rate,
                survival_threshold=survival_threshold,
                reproduction_interval=reproduction_interval,
                seed_min_dist=seed_min_dist,
                seed_max_dist=seed_max_dist,
                seed_energy_cost=seed_energy_cost,
            ),
        )
        world.register_position(entity.entity_id, x, y)
        return entity.entity_id

    return _add_plant


@pytest.fixture
def add_swarm() -> Callable[..., int]:
    """Return a callable that spawns and registers a baseline swarm entity."""

    def _add_swarm(
        world: ECSWorld,
        x: int,
        y: int,
        species_id: int = 0,
        population: int | None = None,
        pop: int | None = None,
        energy: float = 0.0,
        energy_min: float = 1.0,
        velocity: int = 1,
        consumption_rate: float = 1.0,
        reproduction_divisor: float = 1.0,
        reproduction_energy_divisor: float | None = None,
    ) -> int:
        if pop is not None and population is not None and pop != population:
            raise ValueError("Specify either 'pop' or 'population' with the same value")
        final_population = (
            population if population is not None else (pop if pop is not None else 10)
        )
        final_reproduction_divisor = (
            reproduction_energy_divisor
            if reproduction_energy_divisor is not None
            else reproduction_divisor
        )

        entity = world.create_entity()
        world.add_component(
            entity.entity_id,
            SwarmComponent(
                entity_id=entity.entity_id,
                species_id=species_id,
                x=x,
                y=y,
                population=final_population,
                initial_population=max(1, final_population // 2),
                energy=energy,
                energy_min=energy_min,
                velocity=velocity,
                consumption_rate=consumption_rate,
                reproduction_energy_divisor=final_reproduction_divisor,
            ),
        )
        world.register_position(entity.entity_id, x, y)
        return entity.entity_id

    return _add_swarm
