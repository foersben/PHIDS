# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Targeted unit and edge-case tests for interaction system coverage.

Validates co-located swarm population filtering, buffer reuse in GridEnvironment,
tile population array accumulations, dense swarm population indexing,
anchoring evaluation kernels, and SIMD energy layer reconstruction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from phids.api.schemas.species import (
    FloraSpeciesParams,
    HerbivoreResistancesSchema,
    HerbivoreSpeciesParams,
    PassiveDefensesSchema,
)
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import EMPTY_SET, ECSWorld
from phids.engine.systems.interaction import _co_located_swarm_population as interaction_co_located
from phids.engine.systems.interaction.feeding import (
    CachedFloraForagingParams,
    cache_flora_foraging_params,
    cache_herbivore_foraging_params,
)
from phids.engine.systems.interaction.movement import _is_swarm_anchored, _is_swarm_anchored_jit
from phids.engine.systems.interaction.population import (
    _accumulate_tile_population,
    _accumulate_tile_population_jit,
)
from phids.engine.systems.signaling.spatial import SwarmPopulationIndex, _build_swarm_population_index

if TYPE_CHECKING:
    from collections.abc import Callable


def test_interaction_co_located_swarm_population_skips_non_swarm_and_stale_ids(
    add_plant: Callable[..., int],
    add_swarm: Callable[..., int],
) -> None:
    """Verify that co-located swarm population utility ignores stale entity IDs.

    Args:
        add_plant: Fixture to construct and register a plant entity into the ECS world.
        add_swarm: Fixture to construct and register a swarm entity into the ECS world.
    """
    world = ECSWorld()
    plant_id = add_plant(world, 2, 2, species_id=0)
    world.entities_at(2, 2).add(9999)
    add_swarm(world, 2, 2, species_id=0, population=9)
    add_swarm(world, 2, 2, species_id=0, population=6)
    assert world.has_entity(plant_id)
    assert interaction_co_located(world, x=2, y=2) == 15


def test_grid_environment_tile_populations_buffer_reuse() -> None:
    """Verify reset_tile_populations zeroes the pre-allocated NumPy array in-place.

    Multiple calls must return the exact same ``npt.NDArray[np.int32]`` instance with
    its elements cleared to zero without allocating a new array or Python list.
    """
    env = GridEnvironment(width=10, height=10)
    buf1 = env.tile_populations
    assert isinstance(buf1, np.ndarray)
    assert buf1.dtype == np.int32
    assert buf1.shape == (100,)

    # Mutate buffer
    buf1[15] = 42
    buf1[45] = 99

    buf2 = env.reset_tile_populations()
    assert buf2 is buf1, "reset_tile_populations must return the identical array instance."
    assert np.all(buf2 == 0), "reset_tile_populations must zero out all elements in-place."


def test_accumulate_tile_population_numpy_array_parity() -> None:
    """Verify _accumulate_tile_population operates correctly on NumPy NDArrays and lists.

    Both a NumPy 1D array and a Python list must accumulate population deltas at the expected flat
    indices without raising or corrupting adjacent elements.
    """
    np_buf = np.zeros(100, dtype=np.int32)
    py_list = [0] * 100

    _accumulate_tile_population(np_buf, x=3, y=2, width=10, delta=15)
    _accumulate_tile_population(py_list, x=3, y=2, width=10, delta=15)

    idx = 2 * 10 + 3
    assert np_buf[idx] == 15
    assert py_list[idx] == 15

    _accumulate_tile_population(np_buf, x=3, y=2, width=10, delta=-5)
    _accumulate_tile_population(py_list, x=3, y=2, width=10, delta=-5)
    assert np_buf[idx] == 10
    assert py_list[idx] == 10


def test_swarm_population_index_dense_array_parity() -> None:
    """Verify SwarmPopulationIndex dense 3D NumPy array parity with dictionary fallback index.

    Tests that pre-allocated 3D array population indexing yields identical lookup results to heap dictionaries.
    """
    env = GridEnvironment(width=16, height=16, num_signals=4)
    world = ECSWorld()

    # Create two swarms of species 1 co-located at (5, 5)
    e1 = world.create_entity()
    world.add_component(
        e1.entity_id,
        SwarmComponent(
            entity_id=e1.entity_id,
            species_id=1,
            x=5,
            y=5,
            population=12,
            initial_population=12,
            energy=100.0,
            energy_min=10.0,
            velocity=1.0,
            consumption_rate=1.0,
        ),
    )
    e2 = world.create_entity()
    world.add_component(
        e2.entity_id,
        SwarmComponent(
            entity_id=e2.entity_id,
            species_id=1,
            x=5,
            y=5,
            population=8,
            initial_population=8,
            energy=100.0,
            energy_min=10.0,
            velocity=1.0,
            consumption_rate=1.0,
        ),
    )

    # Build index using pre-allocated 3D buffer on env
    idx = _build_swarm_population_index(world, env)
    assert isinstance(idx, SwarmPopulationIndex)

    # Co-located population sum at (5,5,1) must equal 20
    assert idx.get((5, 5, 1), 0) == 20
    # Absent cell must return 0
    assert idx.get((2, 2, 1), 0) == 0
    # Out of bounds species must return default 0
    assert idx.get((5, 5, 999), 0) == 0


def test_is_swarm_anchored_jit_parity() -> None:
    """Verify _is_swarm_anchored_jit parity with reference anchoring logic.

    Tests that JIT-compiled anchoring evaluates 3D plant energy arrays and 2D diet matrices correctly.
    """
    env = GridEnvironment(width=10, height=10, num_signals=2)
    swarm = SwarmComponent(
        entity_id=1,
        species_id=0,
        x=4,
        y=4,
        population=10,
        initial_population=10,
        energy=50.0,
        energy_min=10.0,
        velocity=1.0,
        consumption_rate=1.0,
    )

    # 2D diet matrix: species 0 eats flora 0, does not eat flora 1
    diet_matrix = np.array([[True, False]], dtype=np.bool_)

    # Case 1: Apparent nutrition < 0.999 -> False
    env.apparent_nutrition_layer[4, 4] = 0.5
    assert not _is_swarm_anchored(swarm, env, diet_matrix)

    # Case 2: Apparent nutrition >= 0.999, flora 0 energy > 0 -> True
    env.apparent_nutrition_layer[4, 4] = 1.0
    env.set_plant_energy(4, 4, 0, 50.0)
    env.rebuild_energy_layer()
    assert _is_swarm_anchored(swarm, env, diet_matrix)

    # Directly test Numba JIT kernel
    assert _is_swarm_anchored_jit(4, 4, 0, 1.0, env.plant_energy_by_species, diet_matrix)

    # Case 3: Flora 0 energy depleted -> False
    env.set_plant_energy(4, 4, 0, 0.0)
    env.rebuild_energy_layer()
    assert not _is_swarm_anchored(swarm, env, diet_matrix)

    # Case 4: Test with list of lists diet_matrix (triggering fallback conversion branch)
    list_diet = [[True, False]]
    assert not _is_swarm_anchored(swarm, env, list_diet)

    # Case 5: Out of bounds species_id in JIT kernel -> False
    assert not _is_swarm_anchored_jit(4, 4, 999, 1.0, env.plant_energy_by_species, diet_matrix)


def test_rebuild_energy_layer_simd_parity() -> None:
    """Verify rebuild_energy_layer 256-bit SIMD matrix reduction parity across species energy layers.

    Tests that vector reduction np.sum(..., axis=0, out=...) accurately aggregates multi-species plant energy.
    """
    env = GridEnvironment(width=8, height=8, num_signals=2)

    # Set per-species energy contributions in write buffer
    env.set_plant_energy(2, 3, 0, 45.0)
    env.set_plant_energy(2, 3, 1, 30.0)

    # Execute SIMD vector reduction and buffer swap
    env.rebuild_energy_layer()

    # Aggregate plant energy at (2, 3) must equal 75.0 (45 + 30)
    assert env.plant_energy_layer[2, 3] == 75.0
    assert env.plant_energy_by_species[0, 2, 3] == 45.0
    assert env.plant_energy_by_species[1, 2, 3] == 30.0

    # Unmodified coordinates must remain 0.0
    assert env.plant_energy_layer[0, 0] == 0.0


def test_spatial_hash_empty_set_singleton_parity() -> None:
    """Verify that ECSWorld.entities_at returns EMPTY_SET singleton for unoccupied cells."""
    world = ECSWorld()
    res1 = world.entities_at(10, 20)
    res2 = world.entities_at(99, 99)
    assert res1 is EMPTY_SET
    assert res2 is EMPTY_SET
    assert len(res1) == 0


def test_foraging_parameter_caching_parity() -> None:
    """Verify CachedFloraForagingParams and CachedHerbivoreForagingParams extraction parity."""
    flora = [
        FloraSpeciesParams(
            species_id=0,
            name="TestFlora",
            base_energy=10.0,
            max_energy=20.0,
            growth_rate=2.0,
            survival_threshold=1.0,
            reproduction_interval=2,
            seed_min_dist=1.0,
            seed_max_dist=2.0,
            seed_energy_cost=1.0,
            passive_defenses=PassiveDefensesSchema(mechanical_damage_per_bite=0.5, digestibility_modifier=0.8),
        )
    ]
    herb = [
        HerbivoreSpeciesParams(
            species_id=0,
            name="TestHerb",
            energy_min=1.0,
            velocity=1,
            consumption_rate=1.0,
            reproduction_energy_divisor=2.0,
            resistances=HerbivoreResistancesSchema(digestive_efficiency=0.9, morphological_adaptation=0.1),
        )
    ]

    cached_f = cache_flora_foraging_params(flora)
    cached_h = cache_herbivore_foraging_params(herb)

    assert isinstance(cached_f[0], CachedFloraForagingParams)
    assert cached_h[0].digestive_efficiency == 0.9
    assert cached_h[0].morphological_adaptation == 0.1


def test_tile_population_jit_accumulation_parity() -> None:
    """Verify _accumulate_tile_population_jit in-place NumPy array accumulation parity."""
    arr1 = np.zeros(16, dtype=np.int32)
    _accumulate_tile_population(arr1, x=2, y=1, width=4, delta=50, height=4)
    assert arr1[1 * 4 + 2] == 50

    _accumulate_tile_population(arr1, x=2, y=1, width=4, delta=-20, height=4)
    assert arr1[1 * 4 + 2] == 30

    # Test JIT direct call
    arr2 = np.zeros(16, dtype=np.int32)
    _accumulate_tile_population_jit(arr2, 2, 1, 4, 4, 100)
    assert arr2[6] == 100

    # Test boundary clamping (out-of-bounds does not raise)
    _accumulate_tile_population_jit(arr2, -1, 1, 4, 4, 10)
    _accumulate_tile_population_jit(arr2, 4, 1, 4, 4, 10)
    assert arr2[6] == 100
