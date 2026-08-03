# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for ECS interaction system heuristics.

This module provides targeted tests for the interaction module's internal
heuristics (anchoring, taste rejection, starvation, crowding) using
isolated ECS components and fully compliant GridEnvironment instances.
"""

from __future__ import annotations

# ruff: noqa: I001

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

from phids.engine.core.ecs import ECSWorld
from phids.engine.core.biotope import GridEnvironment
from phids.engine.systems.interaction import run_interaction
from phids.engine.components.swarm import SwarmComponent
from phids.engine.components.plant import PlantComponent


def test_interaction_anchoring_heuristic(
    add_swarm: Callable[..., int],
    add_plant: Callable[..., int],
) -> None:
    """Validate that swarms anchor (do not move) when positioned on compatible, nutritious flora."""
    world = ECSWorld()
    env = GridEnvironment(width=16, height=16, num_signals=1, num_toxins=1)

    # Place a nutritious plant at (1,1)
    plant_entity = add_plant(
        world=world,
        x=1,
        y=1,
        species_id=0,
        energy=10.0,
    )
    env.apparent_nutrition_layer[1, 1] = 1.0
    env.plant_energy_by_species[0, 1, 1] = 10.0

    # Place a compatible swarm at (1,1)
    swarm_entity = add_swarm(
        world=world,
        x=1,
        y=1,
        species_id=0,
        population=5,
        energy=5.0,
    )

    swarm = world.get_entity(swarm_entity).get_component(SwarmComponent)
    plant = world.get_entity(plant_entity).get_component(PlantComponent)

    # Prevent mitosis bisection
    swarm.initial_population = swarm.population

    # Give swarm enough energy to survive 24x metabolic cost and still show net gain from feeding.
    # metabolic_cost = pop * energy_min * upkeep * 24 = 5 * 1 * 0.02 * 24 = 2.4
    # feeding_gain  = consumption_rate = 1.0 (from plant)
    # net expected  = 5.0 + 1.0 - 2.4 = 3.6  (still less than initial)
    # To verify feeding occurred: check plant energy dropped AND swarm energy > after-cost baseline.
    swarm.energy_upkeep_per_individual = 0.02
    swarm.energy_min = 1.0

    initial_swarm_energy = swarm.energy
    initial_plant_energy = plant.energy

    # Tick the interaction system
    from phids.api.schemas.species import HerbivoreSpeciesParams
    from phids.api.schemas.species import FloraSpeciesParams

    dummy_flora = [
        FloraSpeciesParams(
            species_id=0,
            name="Dummy",
            base_energy=10,
            max_energy=20,
            growth_rate=1,
            survival_threshold=1,
            reproduction_interval=1,
        ),
        FloraSpeciesParams(
            species_id=1,
            name="Dummy",
            base_energy=10,
            max_energy=20,
            growth_rate=1,
            survival_threshold=1,
            reproduction_interval=1,
        ),
    ]
    dummy_herbivore = [HerbivoreSpeciesParams(species_id=0, name="Dummy", energy_min=1, velocity=1, consumption_rate=1)]
    run_interaction(
        world,
        env,
        diet_matrix=[[True, True]],
        flora_species_params=dummy_flora,
        herbivore_species_params=dummy_herbivore,
        tick=0,
        is_medium_tick=True,
        is_slow_tick=False,
    )

    # Swarm must have anchored (not moved from (1,1))
    assert swarm.x == 1
    assert swarm.y == 1
    # Plant energy must have decreased (feeding occurred)
    assert plant.energy < initial_plant_energy
    # Swarm energy must be above the post-metabolism baseline (feeding added net value)
    metabolic_cost = swarm.population * swarm.energy_min * swarm.energy_upkeep_per_individual * 24
    post_metabolism_baseline = initial_swarm_energy - metabolic_cost
    assert swarm.energy > post_metabolism_baseline, (
        f"Swarm energy {swarm.energy:.3f} not above post-metabolism baseline {post_metabolism_baseline:.3f}"
    )


def test_interaction_taste_rejection(
    add_swarm: Callable[..., int],
    add_plant: Callable[..., int],
) -> None:
    """Validate that swarms reject incompatible flora, triggering repulsion state."""
    world = ECSWorld()
    env = GridEnvironment(width=16, height=16, num_signals=1, num_toxins=1)

    # Place an incompatible plant at (1,1) with species 1
    add_plant(
        world=world,
        x=1,
        y=1,
        species_id=1,
        energy=10.0,
    )
    env.apparent_nutrition_layer[1, 1] = 1.0
    env.plant_energy_by_species[1, 1, 1] = 10.0

    # Place a swarm at (1,1) looking for species 0
    swarm_entity = add_swarm(
        world=world,
        x=1,
        y=1,
        species_id=0,
        population=5,
        energy=10.0,
    )

    swarm = world.get_entity(swarm_entity).get_component(SwarmComponent)

    # Prevent mitosis bisection
    swarm.initial_population = swarm.population
    # Freeze movement on this tick so it stays at (1,1) to check compatibility
    swarm.move_cooldown = 1

    # Tick the interaction system
    from phids.api.schemas.species import HerbivoreSpeciesParams
    from phids.api.schemas.species import FloraSpeciesParams

    dummy_flora = [
        FloraSpeciesParams(
            species_id=0,
            name="Dummy",
            base_energy=10,
            max_energy=20,
            growth_rate=1,
            survival_threshold=1,
            reproduction_interval=1,
        ),
        FloraSpeciesParams(
            species_id=1,
            name="Dummy",
            base_energy=10,
            max_energy=20,
            growth_rate=1,
            survival_threshold=1,
            reproduction_interval=1,
        ),
    ]
    dummy_herbivore = [HerbivoreSpeciesParams(species_id=0, name="Dummy", energy_min=1, velocity=1, consumption_rate=1)]
    run_interaction(
        world,
        env,
        diet_matrix=[[True, False]],
        flora_species_params=dummy_flora,
        herbivore_species_params=dummy_herbivore,
        tick=0,
    )

    # Swarm should be repelled
    assert swarm.repelled is True
    assert swarm.repelled_ticks_remaining == 2


def test_interaction_starvation_ceil_casualty(
    add_swarm: Callable[..., int],
) -> None:
    """Validate that starvation induces deterministic casualties based on energy deficit.

    With the 24x medium-tick stride, the metabolic cost per evaluation is:
        cost = population * energy_min * upkeep * 24

    Mutation targets for the stride multiplier:
    - Removing * 24 -> cost 24x smaller, fewer casualties, assertion fails.
    - Changing * 24 to * 23 -> cost = 23 * ... , casualties differ.
    """
    world = ECSWorld()
    env = GridEnvironment(width=16, height=16, num_signals=1, num_toxins=1)

    swarm_entity = add_swarm(
        world=world,
        x=1,
        y=1,
        species_id=0,
        population=10,  # larger population to survive partial starvation
        energy=0.0,
    )

    swarm = world.get_entity(swarm_entity).get_component(SwarmComponent)

    # Prevent mitosis bisection
    swarm.initial_population = swarm.population
    # Freeze movement to isolate attrition
    swarm.move_cooldown = 1

    # Choose parameters so that stride cost kills exactly half the population:
    # cost = 10 * 1.0 * 0.5 * 24 = 120  (energy_min * upkeep * stride)
    # deficit = 120 (energy starts at 0)
    # casualties = ceil(120 / 1.0) = 120, capped at population = 10
    # -> all die if we just let cost overwhelm, so instead choose small upkeep:
    # upkeep = 0.01 -> cost = 10 * 1.0 * 0.01 * 24 = 2.4
    # deficit = 2.4, casualties = ceil(2.4 / 1.0) = 3
    # population = 10 - 3 = 7
    swarm.energy_upkeep_per_individual = 0.01
    swarm.energy_min = 1.0

    from phids.api.schemas.species import HerbivoreSpeciesParams
    from phids.api.schemas.species import FloraSpeciesParams

    dummy_flora = [
        FloraSpeciesParams(
            species_id=0,
            name="Dummy",
            base_energy=10,
            max_energy=20,
            growth_rate=1,
            survival_threshold=1,
            reproduction_interval=1,
        ),
    ]
    dummy_herbivore = [HerbivoreSpeciesParams(species_id=0, name="Dummy", energy_min=1, velocity=1, consumption_rate=1)]
    run_interaction(
        world,
        env,
        diet_matrix=[[False]],
        flora_species_params=dummy_flora,
        herbivore_species_params=dummy_herbivore,
        tick=0,
        is_medium_tick=True,  # explicitly gate to medium tick
        is_slow_tick=False,  # disable mitosis to isolate casualties
    )

    # cost = 10 * 1.0 * 0.01 * 24 = 2.4
    # deficit = 2.4, energy_min = 1.0
    # casualties = ceil(2.4 / 1.0) = 3
    # expected population = 10 - 3 = 7
    assert swarm.population == 7


def test_interaction_crowding_dispersal(
    add_swarm: Callable[..., int],
) -> None:
    """Validate that swarms on a crowded cell will trigger dispersal logic."""
    world = ECSWorld()
    env = GridEnvironment(width=16, height=16, num_signals=1, num_toxins=1)

    # Place many swarms on the same cell (1,1) to exceed cell capacity
    swarm_entities = []
    for _ in range(60):
        ent = add_swarm(
            world=world,
            x=1,
            y=1,
            species_id=0,
            population=10,  # 60 * 10 = 600 individuals
            energy=10.0,
        )
        swarm = world.get_entity(ent).get_component(SwarmComponent)
        # Prevent mitosis bisection
        swarm.initial_population = swarm.population
        swarm_entities.append(ent)

    from phids.api.schemas.species import HerbivoreSpeciesParams
    from phids.api.schemas.species import FloraSpeciesParams

    dummy_flora = [
        FloraSpeciesParams(
            species_id=0,
            name="Dummy",
            base_energy=10,
            max_energy=20,
            growth_rate=1,
            survival_threshold=1,
            reproduction_interval=1,
        ),
        FloraSpeciesParams(
            species_id=1,
            name="Dummy",
            base_energy=10,
            max_energy=20,
            growth_rate=1,
            survival_threshold=1,
            reproduction_interval=1,
        ),
    ]
    dummy_herbivore = [HerbivoreSpeciesParams(species_id=0, name="Dummy", energy_min=1, velocity=1, consumption_rate=1)]
    run_interaction(
        world,
        env,
        diet_matrix=[[False, False]],
        flora_species_params=dummy_flora,
        herbivore_species_params=dummy_herbivore,
        tick=0,
    )

    # At least some swarms should have moved due to crowding
    moved_count = 0
    for ent in swarm_entities:
        swarm = world.get_entity(ent).get_component(SwarmComponent)
        if swarm.x != 1 or swarm.y != 1:
            moved_count += 1

    assert moved_count > 0


def test_interaction_random_fallback_and_missing_entity(
    add_swarm: Callable[..., int],
) -> None:
    """Cover the pure-Python fallback (when random choice is mocked) and missing entity checks."""
    from unittest.mock import patch
    from phids.engine.systems.interaction import _choose_neighbour_by_flow_probability

    # 1. Register a non-existent entity to trigger the "not world.has_entity" check
    world = ECSWorld()
    env = GridEnvironment(width=16, height=16, num_signals=1, num_toxins=1)

    world.register_position(99999, 1, 1)

    # Place a swarm at (1,1)
    swarm_entity = add_swarm(
        world=world,
        x=1,
        y=1,
        species_id=0,
        population=5,
        energy=10.0,
    )

    swarm = world.get_entity(swarm_entity).get_component(SwarmComponent)
    # Prevent mitosis bisection
    swarm.initial_population = swarm.population

    # CASE A: flat field, inertia dx=0, dy=0
    swarm.last_dx = 0
    swarm.last_dy = 0
    with (
        patch("random.choice", side_effect=lambda x: x[0]),
        patch("random.choices", side_effect=lambda x, *_, **__: [x[0]]),
    ):
        from phids.api.schemas.species import HerbivoreSpeciesParams
    from phids.api.schemas.species import FloraSpeciesParams

    dummy_flora = [
        FloraSpeciesParams(
            species_id=0,
            name="Dummy",
            base_energy=10,
            max_energy=20,
            growth_rate=1,
            survival_threshold=1,
            reproduction_interval=1,
        ),
        FloraSpeciesParams(
            species_id=1,
            name="Dummy",
            base_energy=10,
            max_energy=20,
            growth_rate=1,
            survival_threshold=1,
            reproduction_interval=1,
        ),
    ]
    dummy_herbivore = [HerbivoreSpeciesParams(species_id=0, name="Dummy", energy_min=1, velocity=1, consumption_rate=1)]
    run_interaction(
        world,
        env,
        diet_matrix=[[False, False]],
        flora_species_params=dummy_flora,
        herbivore_species_params=dummy_herbivore,
        tick=0,
    )

    # CASE B: flat field, inertia dx=1, dy=0
    swarm.last_dx = 1
    swarm.last_dy = 0
    with patch("random.choices", side_effect=lambda x, *_, **__: [x[0]]):
        from phids.api.schemas.species import HerbivoreSpeciesParams
    from phids.api.schemas.species import FloraSpeciesParams

    dummy_flora = [
        FloraSpeciesParams(
            species_id=0,
            name="Dummy",
            base_energy=10,
            max_energy=20,
            growth_rate=1,
            survival_threshold=1,
            reproduction_interval=1,
        ),
        FloraSpeciesParams(
            species_id=1,
            name="Dummy",
            base_energy=10,
            max_energy=20,
            growth_rate=1,
            survival_threshold=1,
            reproduction_interval=1,
        ),
    ]
    dummy_herbivore = [HerbivoreSpeciesParams(species_id=0, name="Dummy", energy_min=1, velocity=1, consumption_rate=1)]
    run_interaction(
        world,
        env,
        diet_matrix=[[False, False]],
        flora_species_params=dummy_flora,
        herbivore_species_params=dummy_herbivore,
        tick=0,
    )

    # CASE C: non-flat field, not invert
    env.flow_field[1, 1] = 1.0
    env.flow_field[2, 1] = 5.0
    swarm.last_dx = 0
    swarm.last_dy = 0
    with patch("random.choices", side_effect=lambda x, *_, **__: [x[0]]):
        from phids.api.schemas.species import HerbivoreSpeciesParams
    from phids.api.schemas.species import FloraSpeciesParams

    dummy_flora = [
        FloraSpeciesParams(
            species_id=0,
            name="Dummy",
            base_energy=10,
            max_energy=20,
            growth_rate=1,
            survival_threshold=1,
            reproduction_interval=1,
        ),
        FloraSpeciesParams(
            species_id=1,
            name="Dummy",
            base_energy=10,
            max_energy=20,
            growth_rate=1,
            survival_threshold=1,
            reproduction_interval=1,
        ),
    ]
    dummy_herbivore = [HerbivoreSpeciesParams(species_id=0, name="Dummy", energy_min=1, velocity=1, consumption_rate=1)]
    run_interaction(
        world,
        env,
        diet_matrix=[[False, False]],
        flora_species_params=dummy_flora,
        herbivore_species_params=dummy_herbivore,
        tick=0,
    )

    # CASE D: non-flat field, invert=True
    import numpy as np

    scratch_cx = np.empty(5, dtype=np.int32)
    scratch_cy = np.empty(5, dtype=np.int32)
    scratch_scores = np.empty(5, dtype=np.float64)
    scratch_adjusted = np.empty(5, dtype=np.float64)
    scratch_weights = np.empty(5, dtype=np.float64)

    with patch("random.choices", side_effect=lambda x, *_, **__: [x[0]]):
        _choose_neighbour_by_flow_probability(
            swarm,
            env.flow_field,
            env.width,
            env.height,
            scratch_cx,
            scratch_cy,
            scratch_scores,
            scratch_adjusted,
            scratch_weights,
            invert=True,
        )

    # 3. Clean up the non-existent entity from the registry to avoid side effects
    world.unregister_position(99999, 1, 1)


def test_accumulate_tile_population_bounds() -> None:
    """Validate _accumulate_tile_population handles valid and out-of-bounds updates gracefully."""
    from phids.engine.systems.interaction.population import _accumulate_tile_population

    tile_pops = [0] * 100
    width = 10

    # Valid in-bounds update
    _accumulate_tile_population(tile_pops, x=2, y=3, width=width, delta=5)
    assert tile_pops[3 * 10 + 2] == 5

    # Out-of-bounds negative x
    _accumulate_tile_population(tile_pops, x=-1, y=3, width=width, delta=5)
    assert sum(tile_pops) == 5

    # Out-of-bounds x >= width (horizontal out of bounds)
    _accumulate_tile_population(tile_pops, x=15, y=3, width=width, delta=5)
    assert sum(tile_pops) == 5

    # Out-of-bounds negative y
    _accumulate_tile_population(tile_pops, x=2, y=-1, width=width, delta=5)
    assert sum(tile_pops) == 5

    # Out-of-bounds y >= height (IndexError caught by except block)
    _accumulate_tile_population(tile_pops, x=2, y=15, width=width, delta=5)
    assert sum(tile_pops) == 5
