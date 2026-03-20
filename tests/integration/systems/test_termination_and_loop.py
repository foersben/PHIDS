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
from collections.abc import Callable

import pytest

from phids.api.schemas import SimulationConfig
from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.ecs import ECSWorld
from phids.engine.loop import SimulationLoop
from phids.telemetry.conditions import check_termination
from phids.telemetry.tick_metrics import TickMetrics, collect_tick_metrics


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
    """Verify Z1 termination fires when `tick` reaches `max_ticks`."""
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
    """Verify Z3 fires when no flora entities remain in the world."""
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


def test_termination_with_precomputed_tick_metrics_matches_world_scan() -> None:
    """Termination decisions remain identical when metrics are provided by a shared tick snapshot."""
    world = _world_with_counts([0], [0])
    metrics = collect_tick_metrics(world)

    via_metrics = check_termination(
        world,
        tick=0,
        max_ticks=100,
        z6_max_flora_energy=1.0,
        tick_metrics=metrics,
    )
    via_world_scan = check_termination(
        world,
        tick=0,
        max_ticks=100,
        z6_max_flora_energy=1.0,
    )

    assert via_metrics.terminated is True
    assert via_metrics.reason == via_world_scan.reason


@pytest.mark.parametrize(
    ("setup", "kwargs"),
    [
        ("z2", {"z2_flora_species": 1}),
        ("z4", {"z4_herbivore_species": 1}),
        ("z6", {"z6_max_flora_energy": 1.0}),
        ("z7", {"z7_max_total_herbivore_population": 1}),
    ],
)
def test_termination_parity_between_metrics_and_world_scan_across_branches(
    setup: str,
    kwargs: dict[str, int | float],
) -> None:
    """Branch outcomes remain identical when termination is evaluated via shared TickMetrics."""
    world = _world_with_counts([0], [0])
    if setup == "z6":
        plant = next(iter(world.query(PlantComponent))).get_component(PlantComponent)
        plant.energy = 8.0
    if setup == "z7":
        swarm = next(iter(world.query(SwarmComponent))).get_component(SwarmComponent)
        swarm.population = 9

    metrics = collect_tick_metrics(world)
    via_metrics = check_termination(world, tick=0, max_ticks=100, tick_metrics=metrics, **kwargs)
    via_world_scan = check_termination(world, tick=0, max_ticks=100, **kwargs)

    assert via_metrics.terminated == via_world_scan.terminated
    assert via_metrics.reason == via_world_scan.reason


def test_simulation_loop_step_updates_replay_and_telemetry(
    loop_config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify one loop step advances tick state and records replay plus telemetry outputs."""
    loop = SimulationLoop(loop_config_builder(max_ticks=30))

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


def test_simulation_loop_terminates_when_z1_reached(
    caplog,
    loop_config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify loop state flips to terminated and logs when Z1 is already satisfied."""
    loop = SimulationLoop(loop_config_builder(max_ticks=1))
    loop.tick = loop.config.max_ticks

    with caplog.at_level(logging.INFO, logger="phids.engine.loop"):
        result = asyncio.run(loop.step())

    assert result.terminated is True
    assert loop.terminated is True
    assert loop.running is False
    assert loop.termination_reason is not None
    assert "Simulation terminated at tick" in caplog.text


def test_get_state_snapshot_memorize_within_tick_and_refreshes_after_step(
    loop_config_builder: Callable[..., SimulationConfig],
) -> None:
    """Validate that snapshot generation does not repeat expensive env serialization within one tick."""
    loop = SimulationLoop(loop_config_builder(max_ticks=10))

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


def test_get_state_snapshot_cache_invalidates_when_wind_changes(
    loop_config_builder: Callable[..., SimulationConfig],
) -> None:
    """Validate snapshot cache invalidation for same-tick environmental wind updates."""
    loop = SimulationLoop(loop_config_builder(max_ticks=10))

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


def test_step_with_zarr_backend_does_not_require_ui_snapshot_serialization(
    loop_config_builder: Callable[..., SimulationConfig],
) -> None:
    """Validate replay append path can run without invoking env.to_dict in zarr mode."""
    config = loop_config_builder(max_ticks=10).model_copy(update={"replay_backend": "zarr"})
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


def test_step_with_msgpack_backend_uses_snapshot_serialization_path(
    loop_config_builder: Callable[..., SimulationConfig],
) -> None:
    """Validate fallback replay backend still appends via cached state snapshots."""
    config = loop_config_builder(max_ticks=10).model_copy(update={"replay_backend": "msgpack"})
    loop = SimulationLoop(config)

    calls = {"count": 0}
    original_to_dict = loop.env.to_dict

    def _counted_to_dict() -> dict[str, object]:
        calls["count"] += 1
        return original_to_dict()

    loop.env.to_dict = _counted_to_dict  # type: ignore[method-assign]

    asyncio.run(loop.step())

    assert calls["count"] == 1
    assert len(loop.replay) == 1


def test_debug_tick_summary_uses_precomputed_metrics_without_swarm_rescan(
    loop_config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify debug summary logging reads herbivore totals from shared metrics instead of querying swarms."""
    loop = SimulationLoop(loop_config_builder(max_ticks=10))

    original_query = loop.world.query

    def _guard_query(component_type: type[object]) -> object:
        if component_type is SwarmComponent:
            raise AssertionError("debug summary must not query SwarmComponent")
        return original_query(component_type)

    loop.world.query = _guard_query  # type: ignore[method-assign]

    loop._log_debug_tick_summary(
        latest_metrics={
            "total_flora_energy": 42.0,
            "flora_population": 3,
            "herbivore_clusters": 2,
            "herbivore_population": 9,
        },
        tick_metrics=TickMetrics(
            total_flora_energy=42.0,
            flora_population=3,
            herbivore_clusters=2,
            herbivore_population=9,
        ),
        phase_timings_ms={"flow_field": 0.1},
    )
