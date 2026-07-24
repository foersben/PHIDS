# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Shared pytest fixtures for PHIDS test modules.

This fixture module provides lightweight, reusable ECS and biotope constructors
so unit and integration suites can avoid repetitive setup boilerplate while
preserving deterministic state isolation per test invocation.
"""

from __future__ import annotations

# ruff: noqa: I001, E402, TC003

import asyncio
from collections.abc import AsyncGenerator, Callable
import contextlib
import os

# Configure Hypothesis storage directory inside the project's hidden .cache folder.
# Must be set before importing hypothesis or pytest to override default creation.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["HYPOTHESIS_STORAGE_DIRECTORY"] = os.path.join(_PROJECT_ROOT, ".cache/hypothesis")

from httpx import ASGITransport, AsyncClient
from hypothesis import database, settings
import pytest
import pytest_asyncio

from phids.api import main as api_main
from phids.api.main import app
from phids.api.schemas import (
    DietCompatibilityMatrix,
    FloraSpeciesParams,
    HerbivoreResistancesSchema,
    HerbivoreSpeciesParams,
    InitialPlantPlacement,
    InitialSwarmPlacement,
    PassiveDefensesSchema,
    SimulationConfig,
)
from phids.api.ui_state import reset_draft
from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld

# Register and load a profile redirecting the Hypothesis example database
settings.register_profile(
    "default",
    database=database.DirectoryBasedExampleDatabase(".cache/hypothesis"),
)
settings.load_profile("default")


@pytest_asyncio.fixture(autouse=True)
async def safe_global_reset() -> AsyncGenerator[None]:
    """Reset global API state and cancel dangling simulation tasks around each test.

    Yields:
        None after performing initial draft reset.
    """
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
async def api_client() -> AsyncGenerator[AsyncClient]:
    """Provide a shared AsyncClient bound to the in-process FastAPI application.

    Yields:
        An AsyncClient bound to the FastAPI app, using ASGITransport.
    """
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
def empty_world() -> ECSWorld:
    """Return a fresh ECS world with no entities registered.

    Returns:
        A pristine ECSWorld instance.
    """
    return ECSWorld()


@pytest.fixture
def standard_biotope() -> GridEnvironment:
    """Return a deterministic 50x50 environment with two signal and toxin layers.

    Returns:
        A GridEnvironment instance configured with a 50x50 grid shape,
        2 layers for signal substances, and 2 layers for toxin substances.
    """
    return GridEnvironment(width=50, height=50, num_signals=2, num_toxins=2)


@pytest.fixture
def config_builder() -> Callable[..., SimulationConfig]:
    """Return a callable that builds the shared baseline SimulationConfig.

    Returns:
        A builder function that returns a configured SimulationConfig instance.
    """

    def _config(max_ticks: int = 5) -> SimulationConfig:
        """Create a baseline SimulationConfig.

        Args:
            max_ticks: Maximum duration in ticks for the simulation.

        Returns:
            A SimulationConfig instance populated with test defaults.
        """
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
                    passive_defenses=PassiveDefensesSchema(mechanical_damage_per_bite=0.0, digestibility_modifier=1.0),
                )
            ],
            herbivore_species=[
                HerbivoreSpeciesParams(
                    species_id=0,
                    name="herbivore",
                    energy_min=1.0,
                    velocity=1,
                    consumption_rate=1.0,
                    resistances=HerbivoreResistancesSchema(),
                )
            ],
            diet_matrix=DietCompatibilityMatrix(rows=[[True]]),
            initial_plants=[InitialPlantPlacement(species_id=0, x=2, y=2, energy=10.0)],
            initial_swarms=[InitialSwarmPlacement(species_id=0, x=2, y=2, population=3, energy=3.0)],
        )

    return _config


@pytest.fixture
def loop_config_builder() -> Callable[..., SimulationConfig]:
    """Return a callable that builds the shared loop/termination SimulationConfig baseline.

    Returns:
        A builder function that returns a configured SimulationConfig instance.
    """

    def _base_config(max_ticks: int = 20) -> SimulationConfig:
        """Create a baseline SimulationConfig for loop and termination verification.

        Args:
            max_ticks: Maximum duration in ticks for the simulation.

        Returns:
            A SimulationConfig instance populated with test defaults.
        """
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
                    passive_defenses=PassiveDefensesSchema(mechanical_damage_per_bite=0.0, digestibility_modifier=1.0),
                )
            ],
            herbivore_species=[
                HerbivoreSpeciesParams(
                    species_id=0,
                    name="herbivore-0",
                    energy_min=1.0,
                    velocity=1,
                    consumption_rate=1.0,
                    resistances=HerbivoreResistancesSchema(),
                )
            ],
            diet_matrix=DietCompatibilityMatrix(rows=[[True]]),
            initial_plants=[InitialPlantPlacement(species_id=0, x=2, y=2, energy=10.0)],
            initial_swarms=[InitialSwarmPlacement(species_id=0, x=2, y=2, population=3, energy=3.0)],
        )

    return _base_config


@pytest.fixture
def add_plant() -> Callable[..., int]:
    """Return a callable that spawns and registers a plant entity.

    Returns:
        A callable that creates a plant entity, attaches a PlantComponent to it,
        registers its position in the world's spatial hash, and returns the entity ID.
    """

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
        """Spawn a plant entity in the ECS world.

        Args:
            world: The ECSWorld registry instance.
            x: Grid coordinate along the X-axis.
            y: Grid coordinate along the Y-axis.
            species_id: Identifier index of the flora species.
            energy: Initial energy reserve for the plant entity.
            max_energy: Maximum energy capacity for the plant entity.
            base_energy: Base energy value used in lifecycle calculations.
            growth_rate: Energy growth rate applied per tick.
            survival_threshold: Energy threshold below which the entity dies.
            reproduction_interval: Ticks required between reproduction checks.
            seed_min_dist: Minimum dispersal distance for offspring seeds.
            seed_max_dist: Maximum dispersal distance for offspring seeds.
            seed_energy_cost: Energy cost deducted upon reproduction.

        Returns:
            The unique integer entity ID of the spawned plant.
        """
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
    """Return a callable that spawns and registers a swarm entity.

    Returns:
        A callable that creates a swarm entity, attaches a SwarmComponent to it,
        registers its position in the world's spatial hash, and returns the entity ID.
    """

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
        split_population_threshold: int = 1000,
    ) -> int:
        """Spawn a swarm entity in the ECS world.

        Args:
            world: The ECSWorld registry instance.
            x: Grid coordinate along the X-axis.
            y: Grid coordinate along the Y-axis.
            species_id: Identifier index of the herbivore species.
            population: Initial population headcount. Alias of `pop`.
            pop: Initial population headcount. Alias of `population`.
            energy: Initial energy reserve for the swarm entity.
            energy_min: Minimum energy threshold per individual.
            velocity: Movement cooldown period in ticks.
            consumption_rate: Feeding speed multiplier per individual.
            reproduction_divisor: Reproduction throttle divisor.
            reproduction_energy_divisor: Explicit reproduction threshold override.
            split_population_threshold: Mitosis split population size limit.

        Returns:
            The unique integer entity ID of the spawned swarm.

        Raises:
            ValueError: If both pop and population are specified with conflicting values.
        """
        if pop is not None and population is not None and pop != population:
            raise ValueError("Specify either 'pop' or 'population' with the same value")
        final_population: int = population if population is not None else (pop if pop is not None else 10)
        final_reproduction_divisor: float = (
            reproduction_energy_divisor if reproduction_energy_divisor is not None else reproduction_divisor
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
                split_population_threshold=split_population_threshold,
            ),
        )
        world.register_position(entity.entity_id, x, y)
        return entity.entity_id

    return _add_swarm
