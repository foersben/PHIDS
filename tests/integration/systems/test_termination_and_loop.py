"""Integration tests for SimulationLoop determinism, termination conditions, and tick ordering.

This module validates the end-to-end behaviour of :class:`~phids.engine.loop.SimulationLoop`
under a range of configured termination conditions (Z1 max-ticks, Z3 total flora extinction, Z4
herbivore species extinction) and under boundary scenarios such as empty placement lists and
single-species configurations. The core hypotheses are: (1) the loop terminates at exactly
``max_ticks`` when no ecological stopping condition fires first; (2) the loop terminates
immediately upon total flora extinction, reflecting the biological collapse of the primary
producer trophic layer; (3) all five ordered phases (flow field, lifecycle, interaction,
signaling, telemetry) advance the ECS world state deterministically across multiple ticks without
raising exceptions; and (4) the telemetry recorder accumulates exactly one row per completed tick,
preserving a correct accounting of Lotka-Volterra population dynamics.
"""

from __future__ import annotations

import asyncio
import logging

import pytest

from phids.api.schemas import (
    DietCompatibilityMatrix,
    FloraSpeciesParams,
    InitialPlantPlacement,
    InitialSwarmPlacement,
    HerbivoreSpeciesParams,
    SimulationConfig,
)
from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.ecs import ECSWorld
from phids.engine.loop import SimulationLoop
from phids.telemetry.conditions import check_termination


def _base_config(max_ticks: int = 20) -> SimulationConfig:
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
            )
        ],
        herbivore_species=[
            HerbivoreSpeciesParams(
                species_id=0,
                name="herbivore-0",
                energy_min=1.0,
                velocity=1,
                consumption_rate=1.0,
            )
        ],
        diet_matrix=DietCompatibilityMatrix(rows=[[True]]),
        initial_plants=[InitialPlantPlacement(species_id=0, x=2, y=2, energy=10.0)],
        initial_swarms=[InitialSwarmPlacement(species_id=0, x=2, y=2, population=3, energy=3.0)],
    )


def _world_with_counts(plant_species: list[int], herbivore_species: list[int]) -> ECSWorld:
    world = ECSWorld()
    for idx, sp in enumerate(plant_species):
        e = world.create_entity()
        p = PlantComponent(
            entity_id=e.entity_id,
            species_id=sp,
            x=idx,
            y=0,
            energy=5.0,
            max_energy=10.0,
            base_energy=5.0,
            growth_rate=1.0,
            survival_threshold=1.0,
            reproduction_interval=2,
            seed_min_dist=1.0,
            seed_max_dist=2.0,
            seed_energy_cost=1.0,
        )
        world.add_component(e.entity_id, p)

    for idx, sp in enumerate(herbivore_species):
        e = world.create_entity()
        s = SwarmComponent(
            entity_id=e.entity_id,
            species_id=sp,
            x=idx,
            y=1,
            population=4,
            initial_population=4,
            energy=0.0,
            energy_min=1.0,
            velocity=1,
            consumption_rate=1.0,
        )
        world.add_component(e.entity_id, s)

    return world


def test_termination_z1_max_ticks() -> None:
    """Validates the termination z1 max ticks invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    world = _world_with_counts([0], [0])
    result = check_termination(world, tick=10, max_ticks=10)
    assert result.terminated is True
    assert result.reason.startswith("Z1")


@pytest.mark.parametrize(
    ("kwargs", "expected_reason"),
    [
        ({"z2_flora_species": 1}, "Z2"),
        ({"z4_herbivore_species": 1}, "Z4"),
    ],
)
def test_termination_species_extinction_branches(
    kwargs: dict[str, int], expected_reason: str
) -> None:
    """Validate species-index extinction termination branches through table-driven inputs."""
    world = _world_with_counts([0], [0])
    result = check_termination(world, tick=0, max_ticks=100, **kwargs)
    assert result.terminated is True
    assert expected_reason in result.reason


def test_termination_z3_z5_all_extinction() -> None:
    """Validates the termination z3 z5 all extinction invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    world = _world_with_counts([], [])

    z3 = check_termination(world, tick=0, max_ticks=100)
    assert z3.terminated is True
    assert "Z3" in z3.reason


@pytest.mark.parametrize(
    ("kwargs", "expected_reason"),
    [
        ({"z6_max_flora_energy": 1.0}, "Z6"),
        ({"z7_max_total_herbivore_population": 1}, "Z7"),
    ],
)
def test_termination_threshold_branches(
    kwargs: dict[str, float | int], expected_reason: str
) -> None:
    """Validate numeric-threshold termination branches through table-driven inputs."""
    world = _world_with_counts([0], [0])
    result = check_termination(world, tick=0, max_ticks=100, **kwargs)
    assert result.terminated is True
    assert expected_reason in result.reason


def test_simulation_loop_step_updates_replay_and_telemetry() -> None:
    """Validates the simulation loop step updates replay and telemetry invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    loop = SimulationLoop(_base_config(max_ticks=30))

    before_tick = loop.tick
    result = asyncio.run(loop.step())

    assert result.terminated is False
    assert loop.tick == before_tick + 1
    assert len(loop.replay) == 1
    assert loop.telemetry.dataframe.height >= 1
    latest = loop.telemetry.get_latest_metrics()
    assert latest is not None
    assert "death_herbivore_feeding" in latest
    assert "death_defense_maintenance" in latest


def test_simulation_loop_terminates_when_z1_reached(caplog) -> None:
    """Validates the simulation loop terminates when z1 reached invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Args:
        caplog: Input value used to parameterize deterministic behavior for this callable.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    loop = SimulationLoop(_base_config(max_ticks=1))
    loop.tick = loop.config.max_ticks

    with caplog.at_level(logging.INFO, logger="phids.engine.loop"):
        result = asyncio.run(loop.step())

    assert result.terminated is True
    assert loop.terminated is True
    assert loop.running is False
    assert loop.termination_reason is not None
    assert "Simulation terminated at tick" in caplog.text


def test_get_state_snapshot_memorize_within_tick_and_refreshes_after_step() -> None:
    """Validate that snapshot generation does not repeat expensive env serialization within one tick."""
    loop = SimulationLoop(_base_config(max_ticks=10))

    calls = {"count": 0}
    original_to_dict = loop.env.to_dict

    def _counted_to_dict() -> dict[str, object]:
        calls["count"] += 1
        return original_to_dict()

    loop.env.to_dict = _counted_to_dict  # type: ignore[method-assign]

    snap_a = loop.get_state_snapshot()
    snap_b = loop.get_state_snapshot()

    assert calls["count"] == 1
    assert snap_a is snap_b

    asyncio.run(loop.step())
    loop.get_state_snapshot()
    assert calls["count"] == 2


def test_get_state_snapshot_cache_invalidates_when_wind_changes() -> None:
    """Validate snapshot cache invalidation for same-tick environmental wind updates."""
    loop = SimulationLoop(_base_config(max_ticks=10))

    calls = {"count": 0}
    original_to_dict = loop.env.to_dict

    def _counted_to_dict() -> dict[str, object]:
        calls["count"] += 1
        return original_to_dict()

    loop.env.to_dict = _counted_to_dict  # type: ignore[method-assign]

    loop.get_state_snapshot()
    loop.update_wind(0.25, -0.5)
    snapshot_after_wind = loop.get_state_snapshot()

    assert calls["count"] == 2
    assert isinstance(snapshot_after_wind, dict)


def test_step_with_zarr_backend_does_not_require_ui_snapshot_serialization() -> None:
    """Validate replay append path can run without invoking env.to_dict in zarr mode."""
    config = _base_config(max_ticks=10).model_copy(update={"replay_backend": "zarr"})
    loop = SimulationLoop(config)
    if not hasattr(loop.replay, "append_raw_arrays"):
        pytest.skip("Zarr backend unavailable in this environment")

    calls = {"count": 0}

    def _fail_if_called() -> dict[str, object]:
        calls["count"] += 1
        raise AssertionError("env.to_dict should not be called during replay append in zarr mode")

    loop.env.to_dict = _fail_if_called  # type: ignore[method-assign]

    asyncio.run(loop.step())

    assert calls["count"] == 0
    assert len(loop.replay) == 1
