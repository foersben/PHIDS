# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Targeted unit and edge-case tests for signaling system coverage.

Validates activation condition trees, toxin application short-circuits,
mycorrhizal target species gating, SIMD growth and decay kernels,
active signal channel bitmasks, and spatial distance metrics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest

from phids.engine.components.plant import PlantComponent
from phids.engine.components.substances import SubstanceComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.engine.systems.lifecycle.growth import _apply_mycorrhizal_tax_jit, _grow, _grow_simd_jit
from phids.engine.systems.signaling.conditions import _check_activation_condition
from phids.engine.systems.signaling.emission import (
    _apply_toxin_to_swarms,
    _numba_decay_signal_layer,
    _process_single_emission,
)
from phids.engine.systems.signaling.spatial import (
    _co_located_swarm_population as signaling_co_located,
)
from phids.engine.systems.signaling.spatial import (
    _collect_mycorrhizal_targets,
    toroidal_distance_jit,
    toroidal_manhattan_distance_jit,
)
from phids.engine.systems.signaling.triggers import _evaluate_initiator

if TYPE_CHECKING:
    from collections.abc import Callable


def test_signaling_co_located_swarm_population_filters_species(
    add_swarm: Callable[..., int],
) -> None:
    """Verify that signaling co-located swarm population filtering correctly maps species.

    Args:
        add_swarm: Fixture to construct and register a swarm entity into the ECS world.
    """
    world = ECSWorld()
    add_swarm(world, 4, 4, species_id=0, population=7)
    add_swarm(world, 4, 4, species_id=1, population=11)
    add_swarm(world, 4, 4, species_id=1, population=13)
    assert signaling_co_located(world, x=4, y=4, herbivore_species_id=0) == 7
    assert signaling_co_located(world, x=4, y=4, herbivore_species_id=1) == 24


def test_activation_condition_supports_none_and_environmental_signal_bounds(
    add_plant: Callable[..., int],
) -> None:
    """Assert activation check passes on empty node and honors environmental signal boundaries.

    Args:
        add_plant: Fixture to construct and register a plant entity into the ECS world.
    """
    world = ECSWorld()
    plant_id = add_plant(world, 1, 1)
    plant = world.get_entity(plant_id).get_component(PlantComponent)
    env = GridEnvironment(width=5, height=5, num_signals=1, num_toxins=1)
    env.signal_layers[0, 1, 1] = 0.3

    assert _check_activation_condition(plant, plant_id, None, env, {}, {}) is True
    assert (
        _check_activation_condition(
            plant,
            plant_id,
            {"kind": "environmental_signal", "signal_id": 0, "min_concentration": 0.2},
            env,
            {},
            {},
        )
        is True
    )
    assert (
        _check_activation_condition(
            plant,
            plant_id,
            {"kind": "environmental_signal", "signal_id": 5, "min_concentration": 0.2},
            env,
            {},
            {},
        )
        is False
    )


def test_activation_condition_with_swarm_presence_and_substance_active(
    add_plant: Callable[..., int],
    add_swarm: Callable[..., int],
) -> None:
    """Verify activation condition under simultaneous swarm presence and substance active requirements.

    Args:
        add_plant: Fixture to construct and register a plant entity into the ECS world.
        add_swarm: Fixture to construct and register a swarm entity into the ECS world.
    """
    world = ECSWorld()
    plant_id = add_plant(world, 3, 3)
    add_swarm(world, 3, 3, species_id=2, population=4)
    plant = world.get_entity(plant_id).get_component(PlantComponent)
    env = GridEnvironment(width=6, height=6, num_signals=1, num_toxins=1)
    population_index = {(3, 3, 2): 4}
    active = {plant_id: {7}}

    herbivore_presence = {
        "kind": "herbivore_presence",
        "herbivore_species_id": 2,
        "min_herbivore_population": 3,
    }
    substance_active = {"kind": "substance_active", "substance_id": 7}
    composite = {"kind": "all_of", "conditions": [herbivore_presence, substance_active]}
    assert _check_activation_condition(plant, plant_id, composite, env, population_index, active) is True


def test_collect_mycorrhizal_targets_respects_species_gate(add_plant: Callable[..., int]) -> None:
    """Verify mycorrhizal target collection respects inter-species connection settings.

    Args:
        add_plant: Fixture to construct and register a plant entity into the ECS world.
    """
    world = ECSWorld()
    source_id = add_plant(world, 1, 1, species_id=0)
    same_species_id = add_plant(world, 2, 1, species_id=0)
    other_species_id = add_plant(world, 3, 1, species_id=1)
    source = world.get_entity(source_id).get_component(PlantComponent)
    source.mycorrhizal_connections.update({same_species_id, other_species_id, 9999})

    same_only = _collect_mycorrhizal_targets(source, world, mycorrhizal_inter_species=False)
    assert len(same_only) == 1
    assert same_only[0].species_id == 0

    all_species = _collect_mycorrhizal_targets(source, world, mycorrhizal_inter_species=True)
    assert {target.species_id for target in all_species} == {0, 1}


def test_apply_toxin_to_swarms_short_circuits_on_zero_layer() -> None:
    """Verify _apply_toxin_to_swarms returns early without querying swarms if toxin layer is 0.

    When ``env.toxin_layers[sub_id]`` is entirely zero, the function must short-circuit and leave
    all swarms untouched (population unchanged, repelled flag un-flagged).
    """
    world = ECSWorld()
    env = GridEnvironment(width=10, height=10, num_signals=1, num_toxins=2)

    entity = world.create_entity()
    swarm = SwarmComponent(
        entity_id=entity.entity_id,
        species_id=0,
        x=2,
        y=3,
        population=100,
        initial_population=100,
        energy=50.0,
        energy_min=10.0,
        velocity=1,
        consumption_rate=1.0,
    )
    world.add_component(entity.entity_id, swarm)
    world.register_position(entity.entity_id, 2, 3)

    # Toxin layer 0 is entirely 0.0
    _apply_toxin_to_swarms(
        sub_id=0,
        lethal=True,
        lethality_rate=0.5,
        repellent=True,
        repellent_walk_ticks=5,
        env=env,
        world=world,
    )

    assert swarm.population == 100, "Swarm population must remain unchanged when toxin layer is 0."
    assert not swarm.repelled, "Swarm repelled status must remain False when toxin layer is 0."


def test_apply_toxin_to_swarms_applies_effects_when_toxin_present() -> None:
    """Verify _apply_toxin_to_swarms applies lethality and repellency when toxin is > 0.

    When ``env.toxin_layers[sub_id]`` has non-zero concentration at the swarm's location,
    lethal casualties and repellency flags must be applied as expected.
    """
    world = ECSWorld()
    env = GridEnvironment(width=10, height=10, num_signals=1, num_toxins=2)

    entity = world.create_entity()
    swarm = SwarmComponent(
        entity_id=entity.entity_id,
        species_id=0,
        x=2,
        y=3,
        population=100,
        initial_population=100,
        energy=50.0,
        energy_min=10.0,
        velocity=1,
        consumption_rate=1.0,
    )
    world.add_component(entity.entity_id, swarm)
    world.register_position(entity.entity_id, 2, 3)

    # Set toxin concentration at (2, 3)
    env.toxin_layers[0, 2, 3] = 0.1

    _apply_toxin_to_swarms(
        sub_id=0,
        lethal=True,
        lethality_rate=0.5,
        repellent=True,
        repellent_walk_ticks=5,
        env=env,
        world=world,
    )

    # casualties = int(0.5 * 0.1 * 100) = 5
    assert swarm.population == 95
    assert swarm.repelled
    assert swarm.repelled_ticks_remaining == 5


def test_toroidal_distance_jit_parity() -> None:
    """Verify toroidal_distance_jit produces exact Euclidean distances across toroidal seams.

    Tests both standard Euclidean distance and shortest wrap-around distance across boundaries.
    """
    # Direct distance (0,0) to (3,4) = 5.0
    d1 = toroidal_distance_jit(0, 0, 3, 4, width=10, height=10)
    assert d1 == pytest.approx(5.0)

    # Wrap-around distance across x seam: x=1 to x=9 on width 10 is delta 2
    d2 = toroidal_distance_jit(1, 2, 9, 2, width=10, height=10)
    assert d2 == pytest.approx(2.0)


def test_toroidal_manhattan_distance_jit_bounds() -> None:
    """Verify toroidal_manhattan_distance_jit produces exact Manhattan distances across seams.

    Tests wrap-around bounds in both x and y dimensions.
    """
    # Direct Manhattan distance (1,1) to (3,4) = 2 + 3 = 5
    m1 = toroidal_manhattan_distance_jit(1, 1, 3, 4, width=10, height=10)
    assert m1 == 5

    # Wrap-around Manhattan distance: x=0 to x=9 (dx=1), y=0 to y=8 (dy=2) -> 3
    m2 = toroidal_manhattan_distance_jit(0, 0, 9, 8, width=10, height=10)
    assert m2 == 3


def test_active_channel_bitmask_gating_parity() -> None:
    """Verify diffuse_signals uses active_signal_channels gating correctly and discards decayed layers.

    Tests that inactive channels skip advection/convolution, while active channels diffuse
    properly and auto-discard from active_signal_channels when decaying below SIGNAL_EPSILON.
    """
    env = GridEnvironment(width=16, height=16, num_signals=4)

    # Initially all channels inactive
    assert len(env.active_signal_channels) == 0

    # Mark channel 1 active and place signal
    env.mark_signal_active(1)
    env.signal_layers[1, 8, 8] = 5.0
    assert 1 in env.active_signal_channels

    # Perform diffusion
    env.diffuse_signals(signal_decay_factor=0.85)

    # Channel 1 should have diffused concentration at (8,8)
    assert env.signal_layers[1, 8, 8] > 0.0
    # Inactive channel 0 write layer should remain 0.0
    assert np.all(env.signal_layers[0] == 0.0)

    # Simulate strong decay until signal drops below SIGNAL_EPSILON
    for _ in range(50):
        env.diffuse_signals(signal_decay_factor=0.01)

    assert 1 not in env.active_signal_channels, "Channel 1 must be discarded from active set upon sub-threshold decay."


def test_hoisted_trigger_imports_parity() -> None:
    """Verify hoisted trigger imports evaluate environmental signals and herbivore attacks correctly.

    Tests that top-level schema imports in triggers.py maintain exact trigger evaluation behavior.
    """
    from phids.api.schemas.triggers import (
        HerbivoreAttackInitiator,
        SynthesizeSubstanceAction,
        TriggerConditionSchema,
    )

    env = GridEnvironment(width=10, height=10, num_signals=2)
    plant = PlantComponent(
        entity_id=1,
        species_id=0,
        x=3,
        y=3,
        energy=100.0,
        max_energy=200.0,
        base_energy=100.0,
        growth_rate=1.0,
        survival_threshold=1.0,
        reproduction_interval=10,
        seed_min_dist=1,
        seed_max_dist=3,
        seed_energy_cost=10.0,
    )

    class MockTrigger:
        def __init__(self) -> None:
            self.schema = TriggerConditionSchema(
                initiator=HerbivoreAttackInitiator(herbivore_species_id=0, min_herbivore_population=10),
                action=SynthesizeSubstanceAction(substance_id=0, synthesis_duration=5),
            )

    trig = MockTrigger()

    # Herbivore population 5 (< 10 threshold) -> False
    pop_index_low = {(3, 3, 0): 5}
    assert not _evaluate_initiator(trig, plant, env, pop_index_low)  # type: ignore[arg-type]

    # Herbivore population 15 (>= 10 threshold) -> True
    pop_index_high = {(3, 3, 0): 15}
    assert _evaluate_initiator(trig, plant, env, pop_index_high)  # type: ignore[arg-type]


def test_simd_lifecycle_and_decay_kernels_parity() -> None:
    """Verify 256-bit SIMD JIT kernels for photosynthetic growth, mycorrhizal tax, and signal decay."""
    # 1. Photosynthetic growth scaling (clamped to max_energy=100.0)
    g1 = _grow_simd_jit(energy=50.0, base_energy=10.0, growth_rate=1.0, max_energy=100.0)
    assert g1 == 66.8  # 50.0 + 10.0 * 0.01 * 168 = 66.8
    g2 = _grow_simd_jit(energy=90.0, base_energy=10.0, growth_rate=1.0, max_energy=100.0)
    assert g2 == 100.0  # clamped to max_energy

    # 2. Mycorrhizal carbon tax deduction
    t1 = _apply_mycorrhizal_tax_jit(energy=50.0, tax_per_link=1.5, num_links=3)
    assert t1 == 45.5  # 50.0 - (1.5 * 3)

    # 3. Airborne VOC signal layer decay kernel
    layer = np.array([[10.0, 0.005], [0.0, 1.0]], dtype=np.float64)
    _numba_decay_signal_layer(layer, decay_factor=0.5, epsilon=0.01)
    assert layer[0, 0] == 5.0
    assert layer[0, 1] == 0.0  # 0.005 * 0.5 = 0.0025 < epsilon -> 0.0
    assert layer[1, 1] == 0.5

    # 4. Dead plant substance emission branch
    world = ECSWorld()
    env = GridEnvironment(width=8, height=8)
    plant_ent = world.create_entity()
    sub = SubstanceComponent(
        entity_id=1,
        substance_id=0,
        owner_plant_id=plant_ent.entity_id,
        active=True,
        triggered_this_tick=True,
    )
    dead_subs: list[int] = []
    dead_plants: list[int] = []
    plant_comp = PlantComponent(
        entity_id=plant_ent.entity_id,
        species_id=0,
        x=1,
        y=1,
        energy=50.0,
        max_energy=100.0,
        base_energy=10.0,
        growth_rate=1.0,
        survival_threshold=5.0,
        reproduction_interval=10,
        seed_min_dist=1.0,
        seed_max_dist=3.0,
        seed_energy_cost=15.0,
    )
    world.add_component(plant_ent.entity_id, plant_comp)

    _process_single_emission(
        sub=sub,
        entity_id=1,
        world=world,
        env=env,
        substance_emit_rate=1.0,
        mycorrhizal_inter_species=False,
        signal_velocity=1,
        active_substance_ids_by_owner={plant_ent.entity_id: {0}},
        dead_plant_ids={plant_ent.entity_id},
        dead_substances=dead_subs,
        dead_plants=dead_plants,
        plant_death_causes={},
        active_toxin_props={},
    )
    assert not sub.active
    assert dead_subs == [1]

    # 4b. Emission branch when owner plant entity is None (deleted)
    sub2 = SubstanceComponent(
        entity_id=2,
        substance_id=0,
        owner_plant_id=99999,
        active=True,
        triggered_this_tick=True,
    )
    dead_subs_2: list[int] = []
    _process_single_emission(
        sub=sub2,
        entity_id=2,
        world=world,
        env=env,
        substance_emit_rate=1.0,
        mycorrhizal_inter_species=False,
        signal_velocity=1,
        active_substance_ids_by_owner={},
        dead_plant_ids=set(),
        dead_substances=dead_subs_2,
        dead_plants=[],
        plant_death_causes={},
        active_toxin_props={},
    )
    assert dead_subs_2 == [2]

    # 4c. Emission branch when substance untriggered and aftereffect expired
    sub3 = SubstanceComponent(
        entity_id=3,
        substance_id=0,
        owner_plant_id=plant_ent.entity_id,
        active=True,
        triggered_this_tick=False,
        aftereffect_remaining_ticks=0,
        irreversible=False,
    )
    active_map = {plant_ent.entity_id: {0}}
    _process_single_emission(
        sub=sub3,
        entity_id=3,
        world=world,
        env=env,
        substance_emit_rate=1.0,
        mycorrhizal_inter_species=False,
        signal_velocity=1,
        active_substance_ids_by_owner=active_map,
        dead_plant_ids=set(),
        dead_substances=[],
        dead_plants=[],
        plant_death_causes={},
        active_toxin_props={},
    )
    assert not sub3.active
    assert 0 not in active_map[plant_ent.entity_id]

    # 5. Direct _grow function call (both unclamped and clamped branches)
    plant_comp.energy = 10.0
    plant_comp.max_energy = 100.0
    plant_comp.base_energy = 10.0
    plant_comp.growth_rate = 1.0
    _grow(plant_comp, tick=0)
    assert plant_comp.energy == 26.8  # 10.0 + 10.0 * 0.01 * 168

    plant_comp.energy = 95.0
    _grow(plant_comp, tick=0)
    assert plant_comp.energy == 100.0  # clamped to max_energy


def test_spatial_hash_toxin_exposure_parity() -> None:
    """Verify Spatial-Hash Mediated Toxin Exposure and adaptive fallback parity."""
    world = ECSWorld()
    env = GridEnvironment(width=8, height=8, num_toxins=1)

    # 1. Localized toxin exposure (num_active_cells < num_swarms)
    e1 = world.create_entity()
    sw1 = SwarmComponent(
        entity_id=e1.entity_id,
        species_id=0,
        x=2,
        y=2,
        population=100,
        initial_population=100,
        energy=100.0,
        energy_min=1.0,
        velocity=1,
        consumption_rate=1.0,
    )
    world.add_component(e1.entity_id, sw1)
    world.register_position(e1.entity_id, 2, 2)

    e2 = world.create_entity()
    sw2 = SwarmComponent(
        entity_id=e2.entity_id,
        species_id=0,
        x=5,
        y=5,
        population=100,
        initial_population=100,
        energy=100.0,
        energy_min=1.0,
        velocity=1,
        consumption_rate=1.0,
    )
    world.add_component(e2.entity_id, sw2)
    world.register_position(e2.entity_id, 5, 5)

    env.toxin_layers[0, 2, 2] = 0.5

    _apply_toxin_to_swarms(
        sub_id=0,
        lethal=True,
        lethality_rate=0.5,
        repellent=True,
        repellent_walk_ticks=3,
        env=env,
        world=world,
    )

    assert sw1.population == 75  # 100 - int(0.5 * 0.5 * 100) = 75
    assert sw1.repelled is True
    assert sw1.repelled_ticks_remaining == 3
    assert sw2.population == 100  # un-exposed at (5, 5)
    assert sw2.repelled is False

    # 2. Saturated toxin exposure fallback (num_active_cells >= num_swarms)
    env.toxin_layers[0, :, :] = 0.2
    _apply_toxin_to_swarms(
        sub_id=0,
        lethal=True,
        lethality_rate=0.1,
        repellent=False,
        repellent_walk_ticks=0,
        env=env,
        world=world,
    )
    assert sw1.population < 75
    assert sw2.population < 100
