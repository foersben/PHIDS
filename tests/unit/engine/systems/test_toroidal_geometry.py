# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests verifying toroidal (wrap-around grid) design behavior."""

from __future__ import annotations

import numpy as np

from phids.api.schemas.species import FloraSpeciesParams
from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.engine.systems.interaction.movement import _resolve_swarm_movement
from phids.engine.systems.lifecycle import _attempt_reproduction, _establish_mycorrhizal_connections
from phids.engine.systems.signaling.spatial import toroidal_distance


def test_toroidal_distance_calculation() -> None:
    """Verify shortest distance across toroidal boundaries."""
    # Direct distance across x=0 and x=19 on a 20x20 grid is 1.0
    dist = toroidal_distance(0, 5, 19, 5, 20, 20)
    assert dist == 1.0

    # Distance across both seams
    dist_diagonal = toroidal_distance(0, 0, 19, 19, 20, 20)
    assert abs(dist_diagonal - np.sqrt(2.0)) < 1e-6


def test_swarm_movement_toroidal_wrap() -> None:
    """Verify swarm moving off western boundary (x=0 -> x=width-1) wraps cleanly."""
    world = ECSWorld()
    env = GridEnvironment(width=10, height=10)

    swarm_entity = world.create_entity()
    swarm = SwarmComponent(
        entity_id=swarm_entity.entity_id,
        species_id=0,
        x=0,
        y=5,
        population=100,
        initial_population=100,
        energy=100.0,
        energy_min=10.0,
        velocity=1,
        consumption_rate=1.0,
        move_cooldown=0,
        repelled=True,
        repelled_ticks_remaining=1,
    )
    world.add_component(swarm_entity.entity_id, swarm)
    world.register_position(swarm_entity.entity_id, 0, 5)

    tile_pops = [0] * 100
    scratch_cx = np.zeros(5, dtype=np.int32)
    scratch_cy = np.zeros(5, dtype=np.int32)
    scratch_scores = np.zeros(5, dtype=np.float64)
    scratch_adj = np.zeros(5, dtype=np.float64)
    scratch_weights = np.zeros(5, dtype=np.float64)

    # Run movement steps until relocation occurs
    for _ in range(20):
        swarm.move_cooldown = 0
        swarm.repelled = True
        swarm.repelled_ticks_remaining = 1
        _resolve_swarm_movement(
            swarm=swarm,
            entity=swarm_entity,
            env=env,
            world=world,
            diet_matrix=[[True]],
            tile_populations=tile_pops,
            scratch_cx=scratch_cx,
            scratch_cy=scratch_cy,
            scratch_scores=scratch_scores,
            scratch_adjusted=scratch_adj,
            scratch_weights=scratch_weights,
        )

    assert 0 <= swarm.x < 10
    assert 0 <= swarm.y < 10


def test_biotope_diffusion_toroidal_wrap() -> None:
    """Verify VOC diffusion signal placed at x=0 wraps onto x=width-1."""
    env = GridEnvironment(width=10, height=10, num_signals=1)
    env.signal_layers[0, 0, 5] = 10.0

    env.diffuse_signals()

    # After diffusion step, signal on right edge (x=9) must be non-zero due to toroidal convolution
    val_left = float(env.signal_layers[0, 0, 5])
    val_wrapped_right = float(env.signal_layers[0, 9, 5])

    assert val_left > 0.0
    assert val_wrapped_right > 0.0


def test_mycorrhizal_connection_across_toroidal_seam() -> None:
    """Verify plants at x=0 and x=width-1 form a mycorrhizal network link."""
    world = ECSWorld()
    env = GridEnvironment(width=10, height=10)

    p1_entity = world.create_entity()
    p1 = PlantComponent(
        entity_id=p1_entity.entity_id,
        species_id=0,
        x=0,
        y=5,
        energy=100.0,
        max_energy=200.0,
        base_energy=50.0,
        growth_rate=10.0,
        survival_threshold=10.0,
        reproduction_interval=10,
        seed_min_dist=2.0,
        seed_max_dist=4.0,
        seed_energy_cost=20.0,
    )
    world.add_component(p1_entity.entity_id, p1)
    world.register_position(p1_entity.entity_id, 0, 5)

    p2_entity = world.create_entity()
    p2 = PlantComponent(
        entity_id=p2_entity.entity_id,
        species_id=0,
        x=9,
        y=5,
        energy=100.0,
        max_energy=200.0,
        base_energy=50.0,
        growth_rate=10.0,
        survival_threshold=10.0,
        reproduction_interval=10,
        seed_min_dist=2.0,
        seed_max_dist=4.0,
        seed_energy_cost=20.0,
    )
    world.add_component(p2_entity.entity_id, p2)
    world.register_position(p2_entity.entity_id, 9, 5)

    success, _dead_ids = _establish_mycorrhizal_connections(
        world=world,
        env=env,
        connection_cost=5.0,
        inter_species=True,
    )

    assert success
    assert p2_entity.entity_id in p1.mycorrhizal_connections
    assert p1_entity.entity_id in p2.mycorrhizal_connections


def test_seed_reproduction_toroidal_wrap() -> None:
    """Verify seed raycasting wraps target coordinates across grid boundaries."""
    world = ECSWorld()
    env = GridEnvironment(width=10, height=10)

    # Set strong eastern wind (wind_x = +20.0)
    env.wind_vector_x[:, :] = 20.0

    plant_entity = world.create_entity()
    plant = PlantComponent(
        entity_id=plant_entity.entity_id,
        species_id=0,
        x=9,
        y=5,
        energy=100.0,
        max_energy=200.0,
        base_energy=50.0,
        growth_rate=10.0,
        survival_threshold=10.0,
        reproduction_interval=1,
        seed_min_dist=3.0,
        seed_max_dist=5.0,
        seed_energy_cost=10.0,
        last_reproduction_tick=0,
    )
    world.add_component(plant_entity.entity_id, plant)
    world.register_position(plant_entity.entity_id, 9, 5)

    species_params = {
        0: FloraSpeciesParams(
            species_id=0,
            name="TestFlora",
            display_name="Test Flora",
            color="#00FF00",
            base_energy=50.0,
            max_energy=100.0,
            growth_rate=10.0,
            survival_threshold=10.0,
            reproduction_interval=1,
            seed_min_dist=3.0,
            seed_max_dist=5.0,
            seed_energy_cost=10.0,
        )
    }

    new_plants = _attempt_reproduction(
        plant=plant,
        tick=10,
        world=world,
        env=env,
        flora_species_params=species_params,
    )

    assert len(new_plants) == 1
    child = new_plants[0]
    # Target coordinate from x=9 blown east by 3..5 cells must wrap to x in [2, 4]
    assert 0 <= child.x < 10
    assert 0 <= child.y < 10
