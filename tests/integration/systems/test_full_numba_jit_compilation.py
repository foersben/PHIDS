# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Full Numba JIT Compilation & Execution Integration Test Suite.

Guarantees that all @njit decorated functions across core engine modules
(flow_field, movement, feeding, metabolism, signaling, lifecycle) compile
cleanly without Numba typing errors, illegal Python collection usage, or memory
layout mismatches when executed on contiguous NumPy arrays.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

from phids.api.schemas import (
    FloraSpeciesParams,
    HerbivoreResistancesSchema,
    HerbivoreSpeciesParams,
    PassiveDefensesSchema,
)
from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.engine.core.flow_field import _compute_flow_field_impl, compute_flow_field
from phids.engine.systems.interaction import run_interaction
from phids.engine.systems.interaction.movement import (
    _choose_neighbour_by_flow_probability_jit,
    _gather_neighbours_jit,
    _weighted_field_choice_jit,
)
from phids.engine.systems.lifecycle import run_lifecycle
from phids.engine.systems.signaling import run_signaling

pytestmark = pytest.mark.skipif(os.environ.get("NUMBA_DISABLE_JIT") == "1", reason="Requires Numba JIT enabled")


def test_flow_field_numba_jit_compilation() -> None:
    """Verify flow field JIT functions compile and execute on float64 contiguous arrays."""
    width, height = 20, 20
    plant_energy = np.zeros((width, height), dtype=np.float64, order="C")
    plant_energy[5, 5] = 100.0
    apparent_nutrition = np.ones((width, height), dtype=np.float64, order="C")

    toxin_layers = np.zeros((1, width, height), dtype=np.float64, order="C")
    toxin_layers[0, 5, 5] = 10.0

    base = np.zeros((width, height), dtype=np.float64, order="C")
    current = np.zeros((width, height), dtype=np.float64, order="C")
    nxt = np.zeros((width, height), dtype=np.float64, order="C")

    # Directly invoke low-level Numba JIT kernel
    res = _compute_flow_field_impl(
        plant_energy=plant_energy,
        apparent_nutrition_layer=apparent_nutrition,
        toxin_layers=toxin_layers,
        width=width,
        height=height,
        base=base,
        current=current,
        nxt=nxt,
        alpha=1.0,
        beta=1.0,
        decay=0.5,
        truncate_threshold=1e-6,
    )
    assert res is not None
    assert res.shape == (width, height)

    # Invoke python wrapper
    field = compute_flow_field(
        plant_energy=plant_energy,
        apparent_nutrition_layer=apparent_nutrition,
        toxin_layers=toxin_layers,
        width=width,
        height=height,
        alpha=1.0,
        beta=1.0,
        decay=0.5,
    )
    assert field.shape == (width, height)


def test_movement_helpers_numba_jit_compilation() -> None:
    """Verify movement kernel helpers compile and execute with Numba buffers."""
    field = np.ones((10, 10), dtype=np.float64, order="C") * 5.0
    field[5, 6] = 20.0  # high attraction East

    scratch_cx = np.zeros(5, dtype=np.int32)
    scratch_cy = np.zeros(5, dtype=np.int32)
    scratch_scores = np.array([5.0, 5.0, 20.0, 5.0, 5.0], dtype=np.float64)
    scratch_adjusted = np.zeros(5, dtype=np.float64)
    scratch_weights = np.zeros(5, dtype=np.float64)

    # 1. Test neighbour gathering
    n_valid = _gather_neighbours_jit(
        x=5,
        y=5,
        width=10,
        height=10,
        c_x=scratch_cx,
        c_y=scratch_cy,
    )
    assert n_valid == 5

    # 2. Test weighted choice
    nx, ny = _choose_neighbour_by_flow_probability_jit(
        x=5,
        y=5,
        last_dx=0,
        last_dy=0,
        flow_field=field,
        width=10,
        height=10,
        invert=False,
        c_x=scratch_cx,
        c_y=scratch_cy,
        scores=scratch_scores,
        adjusted_scores=scratch_adjusted,
        weights=scratch_weights,
        rand_val=0.5,
    )
    assert 0 <= nx < 10
    assert 0 <= ny < 10

    # 3. Direct testing of weighted field choice jit
    wx, wy = _weighted_field_choice_jit(
        count=n_valid,
        invert=False,
        scores=scratch_scores,
        c_x=scratch_cx,
        c_y=scratch_cy,
        adjusted_scores=scratch_adjusted,
        weights=scratch_weights,
        rand_val=0.5,
    )
    assert 0 <= wx < 10
    assert 0 <= wy < 10


def test_full_interaction_phase_jit_execution() -> None:
    """Verify full interaction system loop under Numba JIT mode."""
    world = ECSWorld()
    env = GridEnvironment(width=15, height=15)

    p_eid = world.create_entity()
    world.add_component(
        p_eid.entity_id,
        PlantComponent(
            entity_id=p_eid.entity_id,
            species_id=0,
            x=5,
            y=5,
            energy=80.0,
            max_energy=100.0,
            base_energy=10.0,
            growth_rate=0.1,
            survival_threshold=0.0,
            reproduction_interval=10,
            seed_min_dist=1,
            seed_max_dist=2,
            seed_energy_cost=5,
        ),
    )
    world.register_position(p_eid.entity_id, 5, 5)

    s_eid = world.create_entity()
    world.add_component(
        s_eid.entity_id,
        SwarmComponent(
            entity_id=s_eid.entity_id,
            species_id=0,
            x=5,
            y=5,
            population=10,
            initial_population=10,
            energy=50.0,
            energy_min=1.0,
            velocity=1,
            consumption_rate=2.0,
            split_population_threshold=1000,
        ),
    )
    world.register_position(s_eid.entity_id, 5, 5)

    flora_params = [
        FloraSpeciesParams(
            species_id=0,
            name="F0",
            base_energy=10,
            max_energy=100,
            growth_rate=0.1,
            survival_threshold=0,
            reproduction_interval=10,
            passive_defenses=PassiveDefensesSchema(digestibility_modifier=1.0, mechanical_damage_per_bite=0.0),
        )
    ]
    herb_params = [
        HerbivoreSpeciesParams(
            species_id=0,
            name="H0",
            energy_min=1,
            velocity=1,
            consumption_rate=2.0,
            energy_upkeep_per_individual=0.01,
            resistances=HerbivoreResistancesSchema(digestive_efficiency=1.0, morphological_adaptation=0.0),
        )
    ]
    diet = [[True]]

    # Execute full interaction phase in JIT mode
    run_interaction(world, env, diet, flora_params, herb_params, tick=0)


def test_full_lifecycle_and_signaling_jit_execution() -> None:
    """Verify lifecycle and signaling systems under Numba JIT mode."""
    world = ECSWorld()
    env = GridEnvironment(width=15, height=15)

    p_eid = world.create_entity()
    world.add_component(
        p_eid.entity_id,
        PlantComponent(
            entity_id=p_eid.entity_id,
            species_id=0,
            x=5,
            y=5,
            energy=95.0,
            max_energy=100.0,
            base_energy=10.0,
            growth_rate=0.2,
            survival_threshold=1.0,
            reproduction_interval=1,
            seed_min_dist=1,
            seed_max_dist=2,
            seed_energy_cost=10,
        ),
    )
    world.register_position(p_eid.entity_id, 5, 5)

    flora_params = [
        FloraSpeciesParams(
            species_id=0,
            name="F0",
            base_energy=10,
            max_energy=100,
            growth_rate=0.2,
            survival_threshold=1,
            reproduction_interval=1,
            passive_defenses=PassiveDefensesSchema(digestibility_modifier=1.0, mechanical_damage_per_bite=0.0),
        )
    ]

    # Run lifecycle phase
    run_lifecycle(world, env, tick=1, flora_species_params={0: flora_params[0]})

    # Run signaling phase
    run_signaling(world, env, trigger_conditions={}, mycorrhizal_inter_species=False, signal_velocity=1, tick=1)
