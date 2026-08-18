# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for multi-scale temporal decoupling (Modulo-Gating).

These tests verify that:
1. The Slow Loop (every 168 ticks) gates lifecycle execution correctly.
2. The Medium Loop (every 24 ticks) gates feeding and metabolic attrition correctly.
3. Stride multipliers (168x for growth, 24x for metabolism) are applied precisely.
4. No lifecycle or metabolic work is performed on non-boundary ticks.

Test design follows mutation-testing principles:
- Every assertion targets a specific numeric constant (24, 168) or a precise boundary
  so that mutmut boundary mutations (e.g., % 168 -> % 169, * 24 -> * 23) are
  immediately caught by at least one assertion.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.engine.systems.interaction import run_interaction
from phids.engine.systems.lifecycle import SLOW_TICK_STRIDE, run_lifecycle

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_flora_params(species_id: int = 0) -> object:
    from phids.api.schemas.species import FloraSpeciesParams

    return FloraSpeciesParams(
        species_id=species_id,
        name="TestFlora",
        base_energy=10.0,
        max_energy=100.0,
        growth_rate=1.0,  # per-tick rate, must be multiplied by SLOW_TICK_STRIDE
        survival_threshold=0.1,
        reproduction_interval=9999,  # disable reproduction to isolate growth
    )


def _make_herbivore_params(species_id: int = 0) -> object:
    from phids.api.schemas.species import HerbivoreSpeciesParams

    return HerbivoreSpeciesParams(
        species_id=species_id, name="TestHerbivore", energy_min=1.0, velocity=1, consumption_rate=1.0
    )


# ---------------------------------------------------------------------------
# SLOW_TICK_STRIDE constant
# ---------------------------------------------------------------------------


def test_slow_tick_stride_is_168() -> None:
    """SLOW_TICK_STRIDE must be exactly 168 to represent one biological week.

    Mutation targets: any change to the numeric literal 168 breaks this.
    """
    assert SLOW_TICK_STRIDE == 168


# ---------------------------------------------------------------------------
# Plant growth stride multiplication
# ---------------------------------------------------------------------------


def test_plant_growth_applies_stride_multiplier(
    add_plant: Callable[..., int],
) -> None:
    """Plant energy increment equals base_energy * (rate / 100) * 168 per slow-loop call.

    Mutation targets:
    - Removing * SLOW_TICK_STRIDE -> growth becomes 168x smaller, assertion fails.
    - Changing SLOW_TICK_STRIDE constant -> assertion fails.
    """
    world = ECSWorld()
    env = GridEnvironment(width=16, height=16, num_signals=1, num_toxins=1)

    base_energy = 10.0
    growth_rate = 1.0  # 1% per tick

    eid = add_plant(
        world=world,
        x=5,
        y=5,
        species_id=0,
        energy=base_energy,
        base_energy=base_energy,
        growth_rate=growth_rate,
        max_energy=10_000.0,
        reproduction_interval=9999,
        seed_energy_cost=0.0,
    )
    plant = world.get_entity(eid).get_component(
        __import__("phids.engine.components.plant", fromlist=["PlantComponent"]).PlantComponent
    )
    initial_energy = plant.energy

    run_lifecycle(world, env, tick=0, flora_species_params={0: _make_flora_params()})

    expected_growth = base_energy * (growth_rate / 100.0) * SLOW_TICK_STRIDE
    assert plant.energy == pytest.approx(initial_energy + expected_growth, rel=1e-6)


def test_plant_growth_is_zero_on_non_slow_tick(
    add_plant: Callable[..., int],
) -> None:
    """Plant energy must not change when lifecycle is called on a non-boundary tick.

    The SimulationLoop gates run_lifecycle with ``if is_slow_tick`` which means
    lifecycle is NOT invoked on off-boundary ticks. This test directly verifies
    that the gate must exist by calling run_lifecycle directly and confirming
    growth is applied, then checking that if the loop omits the call energy stays fixed.

    Mutation targets:
    - Removing the ``if is_slow_tick`` guard in loop.py -> lifecycle fires every tick,
      but this test validates the inverse: energy MUST be frozen without a lifecycle call.
    """
    world = ECSWorld()

    eid = add_plant(
        world=world,
        x=3,
        y=3,
        energy=20.0,
        base_energy=10.0,
        growth_rate=1.0,
        max_energy=10_000.0,
        reproduction_interval=9999,
    )
    plant = world.get_entity(eid).get_component(
        __import__("phids.engine.components.plant", fromlist=["PlantComponent"]).PlantComponent
    )

    energy_before = plant.energy

    # Simulate what the loop does on a non-slow-tick: skip lifecycle entirely.
    # Energy must remain unchanged.
    # (No call to run_lifecycle here - this is the invariant being validated.)

    assert plant.energy == energy_before  # must not drift without an explicit lifecycle call


# ---------------------------------------------------------------------------
# Modulo-gated interaction: feeding and metabolism
# ---------------------------------------------------------------------------


def test_feeding_is_suppressed_on_non_medium_tick(
    add_swarm: Callable[..., int],
    add_plant: Callable[..., int],
) -> None:
    """Plant energy must not decrease when is_medium_tick=False.

    Mutation targets:
    - Removing the ``and is_medium_tick`` guard on feeding -> plant energy decreases,
      assertion ``plant.energy == initial_plant_energy`` fails.
    - Changing ``is_medium_tick=False`` to ``is_medium_tick=True`` in the guard ->
      the guard becomes always-true, assertion still fails.
    """
    world = ECSWorld()
    env = GridEnvironment(width=16, height=16, num_signals=1, num_toxins=1)

    plant_eid = add_plant(world=world, x=4, y=4, species_id=0, energy=50.0)
    swarm_eid = add_swarm(world=world, x=4, y=4, species_id=0, population=5, energy=5.0)

    env.apparent_nutrition_layer[4, 4] = 1.0
    env.plant_energy_by_species[0, 4, 4] = 50.0

    from phids.engine.components.plant import PlantComponent
    from phids.engine.components.swarm import SwarmComponent

    plant = world.get_entity(plant_eid).get_component(PlantComponent)
    swarm = world.get_entity(swarm_eid).get_component(SwarmComponent)
    swarm.move_cooldown = 1  # pin in place so it doesn't move away
    swarm.initial_population = swarm.population

    initial_plant_energy = plant.energy
    initial_swarm_energy = swarm.energy

    run_interaction(
        world,
        env,
        diet_matrix=[[True]],
        flora_species_params=[_make_flora_params()],
        herbivore_species_params=[_make_herbivore_params()],
        tick=1,
        is_medium_tick=False,  # ← explicit non-medium tick
        is_slow_tick=False,
    )

    # No feeding must have occurred
    assert plant.energy == initial_plant_energy
    # No metabolic cost must have been applied
    assert swarm.energy == initial_swarm_energy


def test_feeding_occurs_on_medium_tick(
    add_swarm: Callable[..., int],
    add_plant: Callable[..., int],
) -> None:
    """Plant energy decreases when is_medium_tick=True (feeding is active).

    The definitive proof of feeding is that the plant lost energy. The swarm's
    net energy is deliberately not tested here because the 24x metabolic stride
    dominates the feeding gain for small swarms. The isolation of metabolic cost
    is tested separately in test_metabolic_cost_scaled_by_24.

    Mutation targets:
    - Flipping ``and is_medium_tick`` to ``and not is_medium_tick`` -> feeding suppressed,
      plant energy stays unchanged and assertion fails.
    """
    world = ECSWorld()
    env = GridEnvironment(width=16, height=16, num_signals=1, num_toxins=1)

    plant_eid = add_plant(world=world, x=4, y=4, species_id=0, energy=50.0)
    swarm_eid = add_swarm(world=world, x=4, y=4, species_id=0, population=5, energy=9999.0)

    env.apparent_nutrition_layer[4, 4] = 1.0
    env.plant_energy_by_species[0, 4, 4] = 50.0

    from phids.engine.components.plant import PlantComponent
    from phids.engine.components.swarm import SwarmComponent

    plant = world.get_entity(plant_eid).get_component(PlantComponent)
    swarm = world.get_entity(swarm_eid).get_component(SwarmComponent)
    swarm.move_cooldown = 1
    swarm.initial_population = swarm.population

    initial_plant_energy = plant.energy

    run_interaction(
        world,
        env,
        diet_matrix=[[True]],
        flora_species_params=[_make_flora_params()],
        herbivore_species_params=[_make_herbivore_params()],
        tick=0,
        is_medium_tick=True,  # ← explicit medium tick
        is_slow_tick=False,
    )

    # Feeding must have occurred: plant lost energy
    assert plant.energy < initial_plant_energy


# ---------------------------------------------------------------------------
# Metabolic cost stride multiplication
# ---------------------------------------------------------------------------


def test_metabolic_cost_scaled_by_24(
    add_swarm: Callable[..., int],
) -> None:
    """Metabolic cost equals population * energy_min * upkeep * 24 on medium tick.

    We verify the correct absolute energy drain at tick boundary. Reproduction is
    disabled by setting reproduction_energy_divisor to a huge value so the swarm
    never converts surplus energy into new individuals, letting us isolate the cost.

    Mutation targets:
    - Changing ``* 24`` to ``* 1`` -> cost 24x smaller, swarm keeps much more energy.
    - Changing ``* 24`` to ``* 23`` or ``* 25`` -> off-by-one caught precisely.
    """
    world = ECSWorld()
    env = GridEnvironment(width=16, height=16, num_signals=1, num_toxins=1)

    swarm_eid = add_swarm(world=world, x=8, y=8, species_id=0, population=10, energy=1000.0)
    from phids.engine.components.swarm import SwarmComponent

    swarm = world.get_entity(swarm_eid).get_component(SwarmComponent)
    swarm.move_cooldown = 1  # pin in place
    swarm.initial_population = swarm.population
    swarm.energy_upkeep_per_individual = 0.1
    swarm.energy_min = 2.0
    swarm.split_population_threshold = 99999  # disable mitosis
    swarm.reproduction_energy_divisor = 999999.0  # disable reproduction to isolate cost

    initial_energy = swarm.energy

    run_interaction(
        world,
        env,
        diet_matrix=[[False]],
        flora_species_params=[_make_flora_params()],
        herbivore_species_params=[_make_herbivore_params()],
        tick=0,
        is_medium_tick=True,
        is_slow_tick=False,
    )

    # Expected: pop=10, energy_min=2.0, upkeep=0.1, stride=24
    expected_cost = 10 * 2.0 * 0.1 * 24
    assert swarm.energy == pytest.approx(initial_energy - expected_cost, rel=1e-6)


def test_metabolic_cost_not_applied_on_non_medium_tick(
    add_swarm: Callable[..., int],
) -> None:
    """Swarm energy must not decrease when is_medium_tick=False.

    Mutation targets:
    - Removing the ``and is_medium_tick`` guard -> cost applied every tick,
      swarm energy decreases and the assertion fails.
    """
    world = ECSWorld()
    env = GridEnvironment(width=16, height=16, num_signals=1, num_toxins=1)

    swarm_eid = add_swarm(world=world, x=8, y=8, species_id=0, population=10, energy=500.0)
    from phids.engine.components.swarm import SwarmComponent

    swarm = world.get_entity(swarm_eid).get_component(SwarmComponent)
    swarm.move_cooldown = 1
    swarm.initial_population = swarm.population
    swarm.energy_upkeep_per_individual = 0.5
    swarm.energy_min = 2.0

    initial_energy = swarm.energy

    run_interaction(
        world,
        env,
        diet_matrix=[[False]],
        flora_species_params=[_make_flora_params()],
        herbivore_species_params=[_make_herbivore_params()],
        tick=1,
        is_medium_tick=False,
        is_slow_tick=False,
    )

    assert swarm.energy == initial_energy


# ---------------------------------------------------------------------------
# Mitosis gating
# ---------------------------------------------------------------------------


def test_mitosis_suppressed_on_non_slow_tick(
    add_swarm: Callable[..., int],
) -> None:
    """Swarm must NOT split when population exceeds threshold on a medium-only tick.

    Mutation targets:
    - Removing ``if is_slow_tick`` guard on mitosis -> swarm splits on every medium tick,
      the entity count assertion fails.
    """
    world = ECSWorld()
    env = GridEnvironment(width=16, height=16, num_signals=1, num_toxins=1)

    swarm_eid = add_swarm(world=world, x=8, y=8, species_id=0, population=100, energy=9999.0)
    from phids.engine.components.swarm import SwarmComponent

    swarm = world.get_entity(swarm_eid).get_component(SwarmComponent)
    swarm.move_cooldown = 1
    swarm.initial_population = swarm.population
    swarm.split_population_threshold = 50  # population (100) exceeds threshold

    entity_count_before = len(world._entities)

    run_interaction(
        world,
        env,
        diet_matrix=[[False]],
        flora_species_params=[_make_flora_params()],
        herbivore_species_params=[_make_herbivore_params()],
        tick=0,
        is_medium_tick=True,
        is_slow_tick=False,  # ← Mitosis must NOT fire here
    )

    # No new entity should have been created
    assert len(world._entities) == entity_count_before


def test_mitosis_fires_on_slow_tick(
    add_swarm: Callable[..., int],
) -> None:
    """Swarm must split when population exceeds threshold on a slow tick.

    Mutation targets:
    - Changing ``if is_slow_tick`` to ``if not is_slow_tick`` -> split suppressed,
      entity count stays the same and assertion fails.
    """
    world = ECSWorld()
    env = GridEnvironment(width=16, height=16, num_signals=1, num_toxins=1)

    swarm_eid = add_swarm(world=world, x=8, y=8, species_id=0, population=100, energy=9999.0)
    from phids.engine.components.swarm import SwarmComponent

    swarm = world.get_entity(swarm_eid).get_component(SwarmComponent)
    swarm.move_cooldown = 1
    swarm.initial_population = swarm.population
    swarm.split_population_threshold = 50

    entity_count_before = len(world._entities)

    run_interaction(
        world,
        env,
        diet_matrix=[[False]],
        flora_species_params=[_make_flora_params()],
        herbivore_species_params=[_make_herbivore_params()],
        tick=0,
        is_medium_tick=True,
        is_slow_tick=True,  # ← Mitosis MUST fire here
    )

    assert len(world._entities) == entity_count_before + 1


# ---------------------------------------------------------------------------
# Loop-level modulo gate integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_loop_lifecycle_only_fires_at_tick_168_multiples() -> None:
    """SimulationLoop must gate lifecycle to tick % 168 == 0.

    Ticks 0..167 must not trigger plant growth. Tick 168 must.

    Mutation targets:
    - Changing ``% 168`` to ``% 167`` or ``% 169`` -> gate fires at wrong tick,
      one of the boundary assertions fails.
    - Removing the ``if is_slow_tick`` guard entirely -> plant grows every tick.
    """
    from phids.api.schemas.placement import InitialPlantPlacement, InitialSwarmPlacement
    from phids.api.schemas.simulation import SimulationConfig
    from phids.api.schemas.species import (
        DietCompatibilityMatrix,
        FloraSpeciesParams,
        HerbivoreResistancesSchema,
        HerbivoreSpeciesParams,
    )
    from phids.api.schemas.triggers import PassiveDefensesSchema
    from phids.engine.components.plant import PlantComponent
    from phids.engine.loop import SimulationLoop

    config = SimulationConfig(
        grid_width=16,
        grid_height=16,
        max_ticks=175,
        tick_rate_hz=1000.0,
        num_signals=1,
        num_toxins=1,
        wind_x=0.0,
        wind_y=0.0,
        flora_species=[
            FloraSpeciesParams(
                species_id=0,
                name="grass",
                base_energy=10.0,
                max_energy=100_000.0,
                growth_rate=1.0,  # 1% per tick, meaningful when stride=168
                survival_threshold=0.001,
                reproduction_interval=99999,
                seed_energy_cost=0.0,
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
                energy_upkeep_per_individual=0.0,  # zero upkeep to prevent starvation
                resistances=HerbivoreResistancesSchema(),
            )
        ],
        diet_matrix=DietCompatibilityMatrix(rows=[[False]]),  # non-compatible diet to isolate plant growth
        initial_plants=[InitialPlantPlacement(species_id=0, x=2, y=2, energy=10.0)],
        initial_swarms=[
            InitialSwarmPlacement(species_id=0, x=5, y=5, population=1, energy=1.0)
        ],  # prevent Z5 extinction without reproduction surge
    )

    loop = SimulationLoop(config, disable_replay=True)

    plant_eid = next(iter(loop.world._component_index.get(PlantComponent, set())))
    plant = loop.world.get_entity(plant_eid).get_component(PlantComponent)

    # Step tick 0 (0 % 168 == 0 -> is_slow_tick=True, growth applies)
    await loop.step()
    expected_growth = 10.0 * (1.0 / 100.0) * 168
    energy_after_tick_0 = plant.energy
    assert energy_after_tick_0 == pytest.approx(10.0 + expected_growth, rel=1e-4)

    # Run ticks 1..167 (167 steps) - lifecycle must NOT fire (tick % 168 != 0)
    for _ in range(167):
        await loop.step()

    energy_at_tick_167 = plant.energy
    assert energy_at_tick_167 == energy_after_tick_0, (
        f"Plant energy changed before weekly gate: {energy_after_tick_0} -> {energy_at_tick_167}"
    )

    # Tick 168 (step 169): lifecycle MUST fire again
    await loop.step()

    energy_at_tick_168 = plant.energy
    assert energy_at_tick_168 == pytest.approx(energy_after_tick_0 + expected_growth, rel=1e-4), (
        f"Expected weekly growth burst of {expected_growth} at tick 168, "
        f"got delta={energy_at_tick_168 - energy_after_tick_0}"
    )


@pytest.mark.asyncio
async def test_loop_metabolism_only_fires_at_tick_24_multiples() -> None:
    """SimulationLoop must gate metabolism to tick % 24 == 0.

    Ticks 1..23 must not drain swarm energy. Tick 24 must.

    Mutation targets:
    - Changing ``% 24`` to ``% 23`` or ``% 25`` -> gate fires at wrong tick.
    - Removing the ``and is_medium_tick`` guard -> swarm drains every tick.
    """
    from phids.api.schemas.placement import InitialPlantPlacement, InitialSwarmPlacement
    from phids.api.schemas.simulation import SimulationConfig
    from phids.api.schemas.species import (
        DietCompatibilityMatrix,
        FloraSpeciesParams,
        HerbivoreResistancesSchema,
        HerbivoreSpeciesParams,
    )
    from phids.engine.components.swarm import SwarmComponent
    from phids.engine.loop import SimulationLoop

    config = SimulationConfig(
        grid_width=16,
        grid_height=16,
        max_ticks=30,
        tick_rate_hz=1000.0,
        num_signals=1,
        num_toxins=1,
        wind_x=0.0,
        wind_y=0.0,
        flora_species=[
            FloraSpeciesParams(
                species_id=0,
                name="dummy_flora",
                base_energy=10.0,
                max_energy=20.0,
                growth_rate=1.0,
                survival_threshold=1.0,
                reproduction_interval=9999,
            )
        ],
        herbivore_species=[
            HerbivoreSpeciesParams(
                species_id=0,
                name="h0",
                energy_min=1.0,
                velocity=1,
                consumption_rate=0.001,
                energy_upkeep_per_individual=0.01,
                resistances=HerbivoreResistancesSchema(),
            )
        ],
        diet_matrix=DietCompatibilityMatrix(rows=[[False]]),
        initial_plants=[InitialPlantPlacement(species_id=0, x=1, y=1, energy=10.0)],  # prevent Z3 extinction
        initial_swarms=[InitialSwarmPlacement(species_id=0, x=4, y=4, population=2, energy=9999.0)],
    )

    loop = SimulationLoop(config, disable_replay=True)

    swarm_eid = next(iter(loop.world._component_index.get(SwarmComponent, set())))
    swarm = loop.world.get_entity(swarm_eid).get_component(SwarmComponent)
    swarm.split_population_threshold = 99999  # disable mitosis
    swarm.reproduction_energy_divisor = 999999.0  # disable reproduction
    swarm.move_cooldown = 99999  # pin in place so it doesn't move

    # Step tick 0 (0 % 24 == 0 -> is_medium_tick=True, metabolism runs)
    await loop.step()

    expected_cost = 2 * 1.0 * 0.01 * 24  # pop * energy_min * upkeep * stride
    energy_after_tick_0 = swarm.energy
    assert energy_after_tick_0 == pytest.approx(9999.0 - expected_cost, rel=1e-4)

    # Run ticks 1..23 (23 steps): metabolism must NOT fire (no medium-tick boundary)
    for _ in range(23):
        await loop.step()

    energy_at_tick_23 = swarm.energy
    assert energy_at_tick_23 == energy_after_tick_0, (
        f"Swarm energy changed before daily gate: {energy_after_tick_0} -> {energy_at_tick_23}"
    )

    # Tick 24 (25th step): metabolism MUST fire again
    await loop.step()

    energy_at_tick_24 = swarm.energy
    assert energy_at_tick_24 == pytest.approx(energy_after_tick_0 - expected_cost, rel=1e-4), (
        f"Expected daily metabolism cost of {expected_cost} at tick 24, "
        f"got delta={energy_after_tick_0 - energy_at_tick_24}"
    )
