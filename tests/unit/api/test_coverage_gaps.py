# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Targeted branch-coverage tests for low-coverage runtime modules.

The assertions in this module focus on deterministic edge conditions in private helpers
used by signaling, interaction, and replay backends. Each test is intentionally small and
state-local so that per-file coverage gaps can be closed without introducing behavioural
regressions in the simulation loop.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

from phids.engine.components.plant import PlantComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.engine.systems.interaction import _co_located_swarm_population as interaction_co_located
from phids.engine.systems.signaling.conditions import (
    _check_activation_condition,
)
from phids.engine.systems.signaling.spatial import (
    _co_located_swarm_population as signaling_co_located,
)
from phids.engine.systems.signaling.spatial import (
    _collect_mycorrhizal_targets,
)
from phids.io.zarr_replay import ReplayBuffer
from phids.shared.constants import SIGNAL_EPSILON

try:
    import zarr  # noqa: F401

    ZARR_AVAILABLE = True
except ImportError:
    ZARR_AVAILABLE = False


def test_signaling_co_located_swarm_population_filters_species(
    add_swarm: Callable[..., int],
) -> None:
    """Verify that signaling co-located swarm population filtering correctly maps species."""
    world = ECSWorld()
    add_swarm(world, 4, 4, species_id=0, population=7)
    add_swarm(world, 4, 4, species_id=1, population=11)
    add_swarm(world, 4, 4, species_id=1, population=13)
    assert signaling_co_located(world, x=4, y=4, herbivore_species_id=0) == 7
    assert signaling_co_located(world, x=4, y=4, herbivore_species_id=1) == 24


def test_interaction_co_located_swarm_population_skips_non_swarm_and_stale_ids(
    add_plant: Callable[..., int],
    add_swarm: Callable[..., int],
) -> None:
    """Verify that co-located swarm population utility ignores stale entity IDs."""
    world = ECSWorld()
    plant_id = add_plant(world, 2, 2, species_id=0)
    world.entities_at(2, 2).add(9999)
    add_swarm(world, 2, 2, species_id=0, population=9)
    add_swarm(world, 2, 2, species_id=0, population=6)
    assert world.has_entity(plant_id)
    assert interaction_co_located(world, x=2, y=2) == 15


def test_activation_condition_supports_none_and_environmental_signal_bounds(
    add_plant: Callable[..., int],
) -> None:
    """Assert activation check passes on empty node and honors environmental signal boundaries."""
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
    """Verify activation condition under simultaneous swarm presence and substance active requirements."""
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


@pytest.mark.skipif(not ZARR_AVAILABLE, reason="zarr not installed")
def test_zarr_cleanup_store_for_owned_paths() -> None:
    """Verify automatic cleanup of spilled telemetry store directory for owned paths."""
    buffer = ReplayBuffer()
    buffer._ensure_store()
    assert buffer._store_path is not None
    assert buffer._store_path.exists()
    store_path = buffer._store_path
    buffer._cleanup_store()
    assert not store_path.exists()


@pytest.mark.skipif(not ZARR_AVAILABLE, reason="zarr not installed")
def test_zarr_load_metadata_falls_back_on_corrupt_blob(tmp_path: Path) -> None:
    """Verify metadata loader recovers gracefully when Zarr metadata array is corrupted."""
    import zarr

    store_path = tmp_path / "corrupt.zarr"
    root = zarr.open_group(str(store_path), mode="w")
    root.create_group("frames/00000000")
    root.create_array("_metadata", data=np.frombuffer(b"not-json", dtype=np.uint8), chunks=(8,))

    buffer = ReplayBuffer(spill_path=store_path)
    buffer._load_metadata()
    assert len(buffer) == 0
    assert buffer._frame_count == 1


@pytest.mark.skipif(not ZARR_AVAILABLE, reason="zarr not installed")
def test_zarr_signal_tail_clipping_on_append_and_read(tmp_path: Path) -> None:
    """Verify signaling concentration values below SIGNAL_EPSILON are clipped to zero on append."""
    store_path = tmp_path / "signal.zarr"
    buffer = ReplayBuffer(spill_path=store_path)
    signal = np.array([[[SIGNAL_EPSILON * 0.5, SIGNAL_EPSILON * 2.0]]], dtype=np.float32)
    buffer.append({"tick": 0, "signal_layers": signal})
    frame = buffer.get_frame(0)
    restored = np.asarray(frame["signal_layers"], dtype=np.float32)
    assert restored[0, 0, 0] == 0.0
    assert restored[0, 0, 1] > 0.0


def test_collect_mycorrhizal_targets_respects_species_gate(add_plant: Callable[..., int]) -> None:
    """Verify mycorrhizal target collection respects inter-species connection settings."""
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


@pytest.mark.skipif(not ZARR_AVAILABLE, reason="zarr not installed")
def test_zarr_get_frame_out_of_bounds_raises(tmp_path: Path) -> None:
    """Assert IndexError is raised on out-of-bounds frame lookup in ReplayBuffer."""
    buffer = ReplayBuffer(spill_path=tmp_path / "frames.zarr")
    buffer.append({"tick": 0, "value": 1})
    with pytest.raises(IndexError):
        buffer.get_frame(4)
