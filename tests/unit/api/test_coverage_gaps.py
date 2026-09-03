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
import polars as pl
import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

from phids.api.routers.telemetry.chartjs import _extract_chart_series, _extract_chart_series_df
from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.engine.core.flow_field import _init_base_and_current_jit
from phids.engine.systems.interaction import _co_located_swarm_population as interaction_co_located
from phids.engine.systems.interaction.population import _accumulate_tile_population
from phids.engine.systems.signaling.conditions import (
    _check_activation_condition,
)
from phids.engine.systems.signaling.emission import _apply_toxin_to_swarms
from phids.engine.systems.signaling.spatial import (
    _co_located_swarm_population as signaling_co_located,
)
from phids.engine.systems.signaling.spatial import (
    _collect_mycorrhizal_targets,
    toroidal_distance_jit,
    toroidal_manhattan_distance_jit,
)
from phids.engine.systems.signaling.trigger_evaluation import _evaluate_initiator
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


def _build_chart_rows(n: int) -> list[dict[str, object]]:
    """Build ``n`` minimal telemetry row dicts for use in extraction tests."""
    return [
        {
            "tick": i,
            "flora_population": 100 + i,
            "herbivore_population": 50 + i,
            "total_flora_energy": 200.0 + i,
            "plant_pop_by_species": {},
            "plant_energy_by_species": {},
            "defense_cost_by_species": {},
            "swarm_pop_by_species": {},
        }
        for i in range(n)
    ]


def _rows_to_df(rows: list[dict[str, object]]) -> pl.DataFrame:
    """Convert minimal row dicts to the Polars schema expected by _extract_chart_series_df."""
    return pl.DataFrame(
        {
            "tick": [int(r["tick"]) for r in rows],  # type: ignore[arg-type]
            "flora_population": [int(r["flora_population"]) for r in rows],  # type: ignore[arg-type]
            "herbivore_population": [int(r["herbivore_population"]) for r in rows],  # type: ignore[arg-type]
            "total_flora_energy": [float(r["total_flora_energy"]) for r in rows],  # type: ignore[arg-type]
        }
    )


def test_extract_chart_series_df_matches_row_path() -> None:
    """Verify that the Polars fast path produces numerically identical scalar series to the row path.

    Both ``_extract_chart_series`` (row-based) and ``_extract_chart_series_df`` (Polars-based) are
    called on equivalent data. The resulting ``labels`` and the three scalar series must be
    element-wise identical, confirming that vectorized extraction does not introduce rounding or
    ordering discrepancies compared to the reference implementation.
    """
    rows = _build_chart_rows(20)
    df = _rows_to_df(rows)

    labels_row, series_row = _extract_chart_series(rows, flora_ids=[], herbivore_ids=[])
    labels_df, series_df = _extract_chart_series_df(df, flora_ids=[], herbivore_ids=[])

    assert labels_row == labels_df, "Tick labels must match between row and DataFrame paths."
    assert series_row["flora_population"] == series_df["flora_population"]
    assert series_row["herbivore_population"] == series_df["herbivore_population"]
    assert series_row["total_flora_energy"] == pytest.approx(series_df["total_flora_energy"], rel=1e-9)


def test_extract_chart_series_df_empty_dataframe() -> None:
    """Verify that an empty Polars DataFrame returns empty labels and zero-length series.

    This guards the edge case where the simulation has just started and no telemetry rows have
    been recorded yet. The function must return an empty label list and pre-initialized empty
    series dicts without raising, matching the behavior of the row-based path on an empty list.
    """
    empty_df = pl.DataFrame(
        {
            "tick": pl.Series([], dtype=pl.Int64),
            "flora_population": pl.Series([], dtype=pl.Int64),
            "herbivore_population": pl.Series([], dtype=pl.Int64),
            "total_flora_energy": pl.Series([], dtype=pl.Float64),
        }
    )

    labels, series = _extract_chart_series_df(empty_df, flora_ids=[1, 2], herbivore_ids=[3])

    assert labels == []
    assert series["flora_population"] == []
    assert series["herbivore_population"] == []
    assert series["total_flora_energy"] == []
    assert series["plant_1_pop"] == []
    assert series["swarm_3_pop"] == []


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


def test_init_base_and_current_jit_vectorized_parity() -> None:
    """Verify SIMD-vectorized _init_base_and_current_jit matches explicit scalar loop calculation.

    Tests numerical parity across multi-layer toxin arrays and plant energy attraction fields.
    """
    w, h = 8, 8
    plant_energy = np.array([[float(x + y) for y in range(h)] for x in range(w)], dtype=np.float64)
    apparent_nutrition = np.ones((w, h), dtype=np.float64)
    toxin_layers = np.zeros((3, w, h), dtype=np.float64)
    toxin_layers[0, 2, 3] = 0.5
    toxin_layers[1, 2, 3] = 0.25
    toxin_layers[2, 4, 4] = 1.0

    base = np.zeros((w, h), dtype=np.float64)
    current = np.zeros((w, h), dtype=np.float64)

    _init_base_and_current_jit(
        width=w,
        height=h,
        plant_energy=plant_energy,
        apparent_nutrition_layer=apparent_nutrition,
        toxin_layers=toxin_layers,
        base=base,
        current=current,
        alpha=2.0,
        beta=1.5,
    )

    # Expected at (2,3): alpha*(2+3)*1.0 - beta*(0.5+0.25+0) = 10.0 - 1.125 = 8.875
    assert base[2, 3] == pytest.approx(8.875)
    assert current[2, 3] == pytest.approx(8.875)
    assert np.array_equal(base, current)


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

    # Mock compiled trigger with HerbivoreAttackInitiator
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


def test_swarm_population_index_dense_array_parity() -> None:
    """Verify SwarmPopulationIndex dense 3D NumPy array parity with dictionary fallback index.

    Tests that pre-allocated 3D array population indexing yields identical lookup results to heap dictionaries.
    """
    from phids.engine.systems.signaling.spatial import SwarmPopulationIndex, _build_swarm_population_index

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
    from phids.engine.systems.interaction.movement import _is_swarm_anchored, _is_swarm_anchored_jit

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


def test_simd_lifecycle_and_decay_kernels_parity() -> None:
    """Verify 256-bit SIMD JIT kernels for photosynthetic growth, mycorrhizal tax, and signal decay."""
    from phids.engine.components.substances import SubstanceComponent
    from phids.engine.systems.lifecycle.growth import _apply_mycorrhizal_tax_jit, _grow_simd_jit
    from phids.engine.systems.signaling.emission import _numba_decay_signal_layer, _process_single_emission

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
    from phids.engine.systems.lifecycle.growth import _grow

    plant_comp.energy = 10.0
    plant_comp.max_energy = 100.0
    plant_comp.base_energy = 10.0
    plant_comp.growth_rate = 1.0
    _grow(plant_comp, tick=0)
    assert plant_comp.energy == 26.8  # 10.0 + 10.0 * 0.01 * 168

    plant_comp.energy = 95.0
    _grow(plant_comp, tick=0)
    assert plant_comp.energy == 100.0  # clamped to max_energy


def test_spatial_hash_empty_set_singleton_parity() -> None:
    """Verify that ECSWorld.entities_at returns EMPTY_SET singleton for unoccupied cells."""
    from phids.engine.core.ecs import EMPTY_SET, ECSWorld

    world = ECSWorld()
    res1 = world.entities_at(10, 20)
    res2 = world.entities_at(99, 99)
    assert res1 is EMPTY_SET
    assert res2 is EMPTY_SET
    assert len(res1) == 0


def test_foraging_parameter_caching_parity() -> None:
    """Verify CachedFloraForagingParams and CachedHerbivoreForagingParams extraction parity."""
    from phids.api.schemas.species import (
        FloraSpeciesParams,
        HerbivoreResistancesSchema,
        HerbivoreSpeciesParams,
        PassiveDefensesSchema,
    )
    from phids.engine.systems.interaction.feeding import (
        CachedFloraForagingParams,
        cache_flora_foraging_params,
        cache_herbivore_foraging_params,
    )

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


def test_spatial_hash_toxin_exposure_parity() -> None:
    """Verify Spatial-Hash Mediated Toxin Exposure and adaptive fallback parity."""
    from phids.engine.components.swarm import SwarmComponent
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld
    from phids.engine.systems.signaling.emission import _apply_toxin_to_swarms

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


def test_tile_population_jit_accumulation_parity() -> None:
    """Verify _accumulate_tile_population_jit in-place NumPy array accumulation parity."""
    import numpy as np

    from phids.engine.systems.interaction.population import (
        _accumulate_tile_population,
        _accumulate_tile_population_jit,
    )

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


def test_flow_field_pow2_propagation_parity() -> None:
    """Verify bitwise power-of-2 Jacobi relaxation kernel convergence parity."""
    import numpy as np

    from phids.engine.core.flow_field import compute_flow_field

    width, height = 16, 16
    plant_energy = np.zeros((width, height), dtype=np.float64)
    plant_energy[8, 8] = 50.0

    apparent_nutrition = np.ones((width, height), dtype=np.float64)
    toxin_layers = np.zeros((1, width, height), dtype=np.float64)

    field = compute_flow_field(
        plant_energy=plant_energy,
        apparent_nutrition_layer=apparent_nutrition,
        toxin_layers=toxin_layers,
        width=width,
        height=height,
    )

    assert field[8, 8] > 0.0
    assert field[7, 8] > 0.0
    assert field[0, 0] >= 0.0


def test_subnormal_float_flushing_and_fastmath_parity() -> None:
    """Verify subnormal float zeroing and fastmath=True kernel precision parity."""
    import numpy as np

    from phids.engine.core.biotope import _numba_convolve_signal_layer
    from phids.engine.core.flow_field import _truncate_subnormals_jit

    width, height = 8, 8
    kernel = np.array([[0.1, 0.2, 0.1], [0.2, 0.4, 0.2], [0.1, 0.2, 0.1]], dtype=np.float64)

    advected = np.full((width, height), 1e-15, dtype=np.float64)
    write_buf = np.zeros((width, height), dtype=np.float64)

    # Subnormal tail (< 1e-4) should be zeroed out
    _numba_convolve_signal_layer(
        width,
        height,
        decay=0.9,
        epsilon=1e-4,
        kernel=kernel,
        write_buffer=write_buf,
        advected_scratch=advected,
    )
    assert np.all(write_buf == 0.0)

    # Test explicit subnormal truncation kernel
    flow_arr = np.array([[1e-10, 5.0], [0.0, 1e-3]], dtype=np.float64)
    _truncate_subnormals_jit(2, 2, flow_arr, threshold=1e-4)
    assert flow_arr[0, 0] == 0.0
    assert flow_arr[0, 1] == 5.0
    assert flow_arr[1, 1] == 1e-3


def test_parallel_jit_flow_field_parity() -> None:
    """Verify multi-threaded parallel JIT Jacobi relaxation parity across grid sizes."""
    import numpy as np

    from phids.engine.core.flow_field import (
        _propagate_iteration_jit_parallel,
        _propagate_iteration_jit_pow2,
        _propagate_iteration_jit_pow2_parallel,
        compute_flow_field,
    )

    width, height = 128, 128
    plant_energy = np.zeros((width, height), dtype=np.float64)
    plant_energy[64, 64] = 100.0
    apparent_nutrition = np.ones((width, height), dtype=np.float64)
    toxin_layers = np.zeros((1, width, height), dtype=np.float64)

    field_parallel = compute_flow_field(
        plant_energy=plant_energy,
        apparent_nutrition_layer=apparent_nutrition,
        toxin_layers=toxin_layers,
        width=width,
        height=height,
    )

    # Parity check between pow2 sequential and pow2 parallel
    base = np.zeros((width, height), dtype=np.float64)
    base[64, 64] = 100.0
    current_seq = base.copy()
    nxt_seq = np.zeros_like(base)
    current_par = base.copy()
    nxt_par = np.zeros_like(base)

    mask_x, mask_y = width - 1, height - 1
    diff_seq = _propagate_iteration_jit_pow2(width, height, mask_x, mask_y, 0.6, base, current_seq, nxt_seq)
    diff_par = _propagate_iteration_jit_pow2_parallel(width, height, mask_x, mask_y, 0.6, base, current_par, nxt_par)

    assert np.allclose(diff_seq, diff_par)
    assert np.allclose(nxt_seq, nxt_par)

    # Check non-pow2 parallel kernel parity
    current_std_par = base.copy()
    nxt_std_par = np.zeros_like(base)
    diff_std = _propagate_iteration_jit_parallel(width, height, 0.6, base, current_std_par, nxt_std_par)
    assert np.allclose(diff_seq, diff_std)
    assert np.allclose(nxt_seq, nxt_std_par)
    assert field_parallel[64, 64] > 0.0


def test_batch_processing_thread_governance() -> None:
    """Verify batch worker thread pinning env configuration."""
    import subprocess
    import sys

    cmd = [
        sys.executable,
        "-c",
        "import os; from phids.engine.batch.orchestrator import _init_batch_worker; "
        "_init_batch_worker(); assert os.environ.get('NUMBA_NUM_THREADS') == '1'",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0


def test_missing_trigger_evaluation_coverage() -> None:
    from phids.engine.systems.signaling.trigger_evaluation import (
        _evaluate_environmental_initiator_njit,
        _evaluate_herbivore_initiator_njit,
        _process_njit_triggers_for_species,
        _process_standard_triggers_for_species,
        _process_single_trigger,
        _process_single_trigger_action
    )
    import numpy as np

    # 1. test _evaluate_environmental_initiator_njit
    xs = np.array([0, 1, 2, 3], dtype=np.int32)
    ys = np.array([0, 0, 0, 0], dtype=np.int32)
    signal_layer = np.zeros((10, 10), dtype=np.float64)
    signal_layer[0, 0] = 5.0
    signal_layer[1, 0] = 0.5
    signal_layer[2, 0] = 10.0
    signal_layer[3, 0] = 0.0

    out_mask = np.zeros(4, dtype=np.bool_)

    # Step curve (0)
    getattr(_evaluate_environmental_initiator_njit, 'py_func', _evaluate_environmental_initiator_njit)(xs, ys, signal_layer, 0, 2.0, 1.0, 1.0, out_mask)
    assert out_mask[0] == True
    assert out_mask[1] == False

    # Hill curve (1)
    getattr(_evaluate_environmental_initiator_njit, 'py_func', _evaluate_environmental_initiator_njit)(xs, ys, signal_layer, 1, 2.0, 1.0, 2.0, out_mask)
    assert out_mask[0] == True
    assert out_mask[3] == False

    # Logarithmic curve (2)
    getattr(_evaluate_environmental_initiator_njit, 'py_func', _evaluate_environmental_initiator_njit)(xs, ys, signal_layer, 2, 2.0, 1.0, 1.0, out_mask)
    assert out_mask[0] == True
    assert out_mask[1] == False

    # Other curve (3)
    getattr(_evaluate_environmental_initiator_njit, 'py_func', _evaluate_environmental_initiator_njit)(xs, ys, signal_layer, 3, 2.0, 1.0, 1.0, out_mask)
    assert out_mask[0] == False

    # 2. test _evaluate_herbivore_initiator_njit
    swarm_grid = np.zeros((2, 10, 10), dtype=np.int32)
    swarm_grid[0, 0, 0] = 15
    swarm_grid[0, 1, 0] = 5
    out_mask = np.zeros(4, dtype=np.bool_)
    getattr(_evaluate_herbivore_initiator_njit, 'py_func', _evaluate_herbivore_initiator_njit)(xs, ys, 0, 10, swarm_grid, out_mask)
    assert out_mask[0] == True
    assert out_mask[1] == False





def test_missing_trigger_evaluation_coverage_standard() -> None:
    from phids.engine.systems.signaling.trigger_evaluation import (
        _process_single_trigger_action,
        _apply_synthesize_action,
        _process_njit_triggers_for_species,
        _process_standard_triggers_for_species,
        _evaluate_environmental_initiator_njit,
        _evaluate_herbivore_initiator_njit
    )
    from phids.engine.core.ecs import ECSWorld
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.components.plant import PlantComponent
    from phids.api.schemas.triggers import TriggerConditionSchema, ResourceWithdrawalAction, SynthesizeSubstanceAction, EnvironmentalSignalInitiator

    class MockTrigger:
        def __init__(self, action) -> None:
            self.schema = TriggerConditionSchema(
                initiator=EnvironmentalSignalInitiator(signal_id=0, min_concentration=1.0),
                action=action,
            )
            self.activation_condition_dump = None

    world = ECSWorld()
    env = GridEnvironment(width=10, height=10, num_signals=2)
    entity = world.create_entity()
    plant = PlantComponent(entity_id=entity.entity_id, species_id=0, x=3, y=3, energy=100.0, max_energy=200.0, base_energy=100.0, growth_rate=1.0, survival_threshold=1.0, reproduction_interval=10, seed_min_dist=1, seed_max_dist=3, seed_energy_cost=10.0)
    world.add_component(entity.entity_id, plant)

    owner_substance_by_key = {}
    substance_entities = []

    # 1. ResourceWithdrawalAction
    trig1 = MockTrigger(ResourceWithdrawalAction(apparent_nutrition_factor=0.5, withdrawal_duration=10))
    _process_single_trigger_action(trig1, plant, world, env, owner_substance_by_key, {}, {}, substance_entities)
    assert plant.target_nutrition_factor == 0.5
    assert plant.withdrawal_ticks_remaining == 10

    # 2. SynthesizeSubstanceAction
    trig2 = MockTrigger(SynthesizeSubstanceAction(substance_id=1, synthesis_duration=5))
    _process_single_trigger_action(trig2, plant, world, env, owner_substance_by_key, {}, {}, substance_entities)
    assert (plant.entity_id, 1) in owner_substance_by_key
    assert owner_substance_by_key[(plant.entity_id, 1)].synthesis_duration == 5

    # Existing synthesis re-arm
    _process_single_trigger_action(trig2, plant, world, env, owner_substance_by_key, {}, {}, substance_entities)
    assert owner_substance_by_key[(plant.entity_id, 1)].triggered_this_tick == True

    # 3. Test _process_njit_triggers_for_species
    import numpy as np
    mask = np.array([True], dtype=np.bool_)
    _process_njit_triggers_for_species(trig2, [plant], 1, mask, world, env, owner_substance_by_key, {}, {}, substance_entities)

    # 4. Test _process_standard_triggers_for_species
    env.signal_layers[0, 3, 3] = 5.0 # Set high enough to trigger
    _process_standard_triggers_for_species(trig2, [plant], world, env, owner_substance_by_key, {}, {}, substance_entities)

    # 5. _evaluate_environmental_initiator_njit
    xs = np.array([0, 1, 2, 3], dtype=np.int32)
    ys = np.array([0, 0, 0, 0], dtype=np.int32)
    signal_layer = np.zeros((10, 10), dtype=np.float64)
    signal_layer[0, 0] = 5.0
    signal_layer[1, 0] = 0.5
    signal_layer[2, 0] = 10.0
    signal_layer[3, 0] = 0.0

    out_mask = np.zeros(4, dtype=np.bool_)

    getattr(_evaluate_environmental_initiator_njit, 'py_func', _evaluate_environmental_initiator_njit)(xs, ys, signal_layer, 0, 2.0, 1.0, 1.0, out_mask)
    getattr(_evaluate_environmental_initiator_njit, 'py_func', _evaluate_environmental_initiator_njit)(xs, ys, signal_layer, 1, 2.0, 1.0, 2.0, out_mask)
    getattr(_evaluate_environmental_initiator_njit, 'py_func', _evaluate_environmental_initiator_njit)(xs, ys, signal_layer, 2, 2.0, 1.0, 1.0, out_mask)
    getattr(_evaluate_environmental_initiator_njit, 'py_func', _evaluate_environmental_initiator_njit)(xs, ys, signal_layer, 3, 2.0, 1.0, 1.0, out_mask)

    # 6. _evaluate_herbivore_initiator_njit
    swarm_grid = np.zeros((2, 10, 10), dtype=np.int32)
    swarm_grid[0, 0, 0] = 15
    swarm_grid[0, 1, 0] = 5
    out_mask = np.zeros(4, dtype=np.bool_)
    getattr(_evaluate_herbivore_initiator_njit, 'py_func', _evaluate_herbivore_initiator_njit)(xs, ys, 0, 10, swarm_grid, out_mask)


def test_missing_trigger_evaluation_coverage_standard2() -> None:
    from phids.engine.systems.signaling.trigger_evaluation import (
        _evaluate_environmental_signal,
        _evaluate_initiator,
        _evaluate_species_triggers
    )
    from phids.engine.core.ecs import ECSWorld
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.components.plant import PlantComponent
    from phids.api.schemas.triggers import TriggerConditionSchema, ResourceWithdrawalAction, SynthesizeSubstanceAction, EnvironmentalSignalInitiator, HerbivoreAttackInitiator
    from phids.engine.systems.signaling.types import CompiledTrigger
    import numpy as np

    class MockTrigger(CompiledTrigger):
        def __init__(self, initiator) -> None:
            self.schema = TriggerConditionSchema(
                initiator=initiator,
                action=ResourceWithdrawalAction(apparent_nutrition_factor=0.5, withdrawal_duration=10),
            )
            self.activation_condition_dump = None

    env = GridEnvironment(width=10, height=10, num_signals=2)
    env.signal_layers[0, 3, 3] = 5.0
    plant = PlantComponent(entity_id=1, species_id=0, x=3, y=3, energy=100.0, max_energy=200.0, base_energy=100.0, growth_rate=1.0, survival_threshold=1.0, reproduction_interval=10, seed_min_dist=1, seed_max_dist=3, seed_energy_cost=10.0)

    # 1. _evaluate_environmental_signal
    init_step = EnvironmentalSignalInitiator(signal_id=0, min_concentration=1.0, response_curve="step")
    init_hill = EnvironmentalSignalInitiator(signal_id=0, min_concentration=1.0, response_curve="hill", half_saturation=2.0, hill_cooperativity=1.0)
    init_log = EnvironmentalSignalInitiator(signal_id=0, min_concentration=1.0, response_curve="logarithmic")
    init_other = EnvironmentalSignalInitiator(signal_id=0, min_concentration=100.0, response_curve="step")
    init_bad_id = EnvironmentalSignalInitiator(signal_id=5, min_concentration=1.0, response_curve="step")

    assert _evaluate_environmental_signal(init_step, plant, env) == True
    assert _evaluate_environmental_signal(init_hill, plant, env) == True
    assert _evaluate_environmental_signal(init_log, plant, env) == True
    assert _evaluate_environmental_signal(init_other, plant, env) == False
    assert _evaluate_environmental_signal(init_bad_id, plant, env) == False

    # 2. _evaluate_initiator
    trig_env = MockTrigger(init_step)
    trig_herb = MockTrigger(HerbivoreAttackInitiator(herbivore_species_id=0, min_herbivore_population=10))

    assert _evaluate_initiator(trig_env, plant, env, {}) == True
    assert _evaluate_initiator(trig_herb, plant, env, {(3, 3, 0): 15}) == True
    assert _evaluate_initiator(trig_herb, plant, env, {(3, 3, 0): 5}) == False

    # 3. _evaluate_species_triggers
    curve_map = {"step": 0, "hill": 1, "logarithmic": 2}
    swarm_grid = np.zeros((1, 10, 10), dtype=np.int32)
    swarm_grid[0, 3, 3] = 15

    world = ECSWorld()
    entity = world.create_entity()
    plant.entity_id = entity.entity_id
    world.add_component(entity.entity_id, plant)

    _evaluate_species_triggers(
        triggers=[trig_env, trig_herb],
        plants=[plant],
        world=world,
        env=env,
        owner_substance_by_key={},
        swarm_population_by_cell_species={(3, 3, 0): 15},
        active_substance_ids_by_owner={},
        substance_entities=[],
        curve_map=curve_map,
        swarm_grid=swarm_grid
    )
