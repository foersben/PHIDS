"""Targeted branch-coverage tests for low-coverage runtime modules.

The assertions in this module focus on deterministic edge conditions in private helpers
used by signaling, interaction, and replay backends. Each test is intentionally small and
state-local so that per-file coverage gaps can be closed without introducing behavioural
regressions in the simulation loop.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.engine.systems.interaction import _co_located_swarm_population as interaction_co_located
from phids.engine.systems.signaling import (
    _check_activation_condition,
    _collect_mycorrhizal_targets,
    _co_located_swarm_population as signaling_co_located,
)
from phids.io.replay import ReplayBuffer
from phids.shared.constants import SIGNAL_EPSILON

try:
    from phids.io.zarr_replay import ZarrReplayBuffer

    ZARR_AVAILABLE = True
except ImportError:
    ZARR_AVAILABLE = False


def _add_plant(world: ECSWorld, x: int, y: int, species_id: int = 0) -> int:
    entity = world.create_entity()
    world.add_component(
        entity.entity_id,
        PlantComponent(
            entity_id=entity.entity_id,
            species_id=species_id,
            x=x,
            y=y,
            energy=10.0,
            max_energy=20.0,
            base_energy=10.0,
            growth_rate=5.0,
            survival_threshold=1.0,
            reproduction_interval=2,
            seed_min_dist=1.0,
            seed_max_dist=2.0,
            seed_energy_cost=1.0,
        ),
    )
    world.register_position(entity.entity_id, x, y)
    return entity.entity_id


def _add_swarm(world: ECSWorld, x: int, y: int, species_id: int = 0, population: int = 5) -> int:
    entity = world.create_entity()
    world.add_component(
        entity.entity_id,
        SwarmComponent(
            entity_id=entity.entity_id,
            species_id=species_id,
            x=x,
            y=y,
            population=population,
            initial_population=max(1, population),
            energy=25.0,
            energy_min=1.0,
            velocity=1,
            consumption_rate=1.0,
        ),
    )
    world.register_position(entity.entity_id, x, y)
    return entity.entity_id


def test_signaling_co_located_swarm_population_filters_species() -> None:
    world = ECSWorld()
    _add_swarm(world, 4, 4, species_id=0, population=7)
    _add_swarm(world, 4, 4, species_id=1, population=11)
    _add_swarm(world, 4, 4, species_id=1, population=13)
    assert signaling_co_located(world, x=4, y=4, herbivore_species_id=0) == 7
    assert signaling_co_located(world, x=4, y=4, herbivore_species_id=1) == 24


def test_interaction_co_located_swarm_population_skips_non_swarm_and_stale_ids() -> None:
    world = ECSWorld()
    plant_id = _add_plant(world, 2, 2, species_id=0)
    world.entities_at(2, 2).add(9999)
    _add_swarm(world, 2, 2, species_id=0, population=9)
    _add_swarm(world, 2, 2, species_id=0, population=6)
    assert world.has_entity(plant_id)
    assert interaction_co_located(world, x=2, y=2) == 15


def test_activation_condition_supports_none_and_environmental_signal_bounds() -> None:
    world = ECSWorld()
    plant_id = _add_plant(world, 1, 1)
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


def test_activation_condition_with_swarm_presence_and_substance_active() -> None:
    world = ECSWorld()
    plant_id = _add_plant(world, 3, 3)
    _add_swarm(world, 3, 3, species_id=2, population=4)
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
    assert (
        _check_activation_condition(plant, plant_id, composite, env, population_index, active)
        is True
    )


def test_replay_cleanup_spill_file_for_owned_and_non_owned_paths(tmp_path: Path) -> None:
    owned = ReplayBuffer(spill_to_disk=True)
    owned_path = owned._ensure_spill_path()
    owned_path.write_bytes(b"frame")
    assert owned_path.exists()
    owned._cleanup_spill_file()
    assert not owned_path.exists()

    explicit_path = tmp_path / "explicit.bin"
    explicit_path.write_bytes(b"frame")
    non_owned = ReplayBuffer(spill_to_disk=True, spill_path=explicit_path)
    non_owned._cleanup_spill_file()
    assert explicit_path.exists()


def test_replay_get_frame_out_of_range_raises() -> None:
    buffer = ReplayBuffer()
    buffer.append({"tick": 0})
    with pytest.raises(IndexError):
        buffer.get_frame(1)


def test_replay_read_spilled_frame_incomplete_payload_raises(tmp_path: Path) -> None:
    spill_path = tmp_path / "spill.bin"
    spill_path.write_bytes(b"123")
    buffer = ReplayBuffer(spill_to_disk=True, spill_path=spill_path)
    buffer._spilled_index = [(0, 10)]
    with pytest.raises(IndexError):
        buffer.get_frame(0)


@pytest.mark.skipif(not ZARR_AVAILABLE, reason="zarr not installed")
def test_zarr_cleanup_store_for_owned_paths() -> None:
    buffer = ZarrReplayBuffer()
    buffer._ensure_store()
    assert buffer._store_path is not None
    assert buffer._store_path.exists()
    store_path = buffer._store_path
    buffer._cleanup_store()
    assert not store_path.exists()


@pytest.mark.skipif(not ZARR_AVAILABLE, reason="zarr not installed")
def test_zarr_load_metadata_falls_back_on_corrupt_blob(tmp_path: Path) -> None:
    import zarr

    store_path = tmp_path / "corrupt.zarr"
    root = zarr.open_group(str(store_path), mode="w")
    root.create_group("frames/00000000")
    root.create_array("_metadata", data=np.frombuffer(b"not-json", dtype=np.uint8), chunks=(8,))

    buffer = ZarrReplayBuffer(spill_path=store_path)
    buffer._load_metadata()
    assert len(buffer) == 0
    assert buffer._frame_count == 1


@pytest.mark.skipif(not ZARR_AVAILABLE, reason="zarr not installed")
def test_zarr_signal_tail_clipping_on_append_and_read(tmp_path: Path) -> None:
    store_path = tmp_path / "signal.zarr"
    buffer = ZarrReplayBuffer(spill_path=store_path)
    signal = np.array([[[SIGNAL_EPSILON * 0.5, SIGNAL_EPSILON * 2.0]]], dtype=np.float32)
    buffer.append({"tick": 0, "signal_layers": signal})
    frame = buffer.get_frame(0)
    restored = np.asarray(frame["signal_layers"], dtype=np.float32)
    assert restored[0, 0, 0] == 0.0
    assert restored[0, 0, 1] > 0.0


def test_collect_mycorrhizal_targets_respects_species_gate() -> None:
    world = ECSWorld()
    source_id = _add_plant(world, 1, 1, species_id=0)
    same_species_id = _add_plant(world, 2, 1, species_id=0)
    other_species_id = _add_plant(world, 3, 1, species_id=1)
    source = world.get_entity(source_id).get_component(PlantComponent)
    source.mycorrhizal_connections.update({same_species_id, other_species_id, 9999})

    same_only = _collect_mycorrhizal_targets(source, world, mycorrhizal_inter_species=False)
    assert len(same_only) == 1
    assert same_only[0].species_id == 0

    all_species = _collect_mycorrhizal_targets(source, world, mycorrhizal_inter_species=True)
    assert {target.species_id for target in all_species} == {0, 1}


@pytest.mark.skipif(not ZARR_AVAILABLE, reason="zarr not installed")
def test_zarr_get_frame_out_of_bounds_raises(tmp_path: Path) -> None:
    buffer = ZarrReplayBuffer(spill_path=tmp_path / "frames.zarr")
    buffer.append({"tick": 0, "value": 1})
    with pytest.raises(IndexError):
        buffer.get_frame(4)
