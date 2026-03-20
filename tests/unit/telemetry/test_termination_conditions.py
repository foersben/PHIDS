"""Unit regression tests for termination-logic branch semantics.

These checks target mutation-prone boundaries and branch ordering in
:func:`phids.telemetry.conditions.check_termination`.
"""

from __future__ import annotations

import pytest

from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.ecs import ECSWorld
from phids.telemetry.conditions import check_termination
from phids.telemetry.tick_metrics import TickMetrics, collect_tick_metrics


def _add_plant(world: ECSWorld, *, species_id: int, energy: float = 5.0) -> None:
    entity = world.create_entity()
    world.add_component(
        entity.entity_id,
        PlantComponent(
            entity_id=entity.entity_id,
            species_id=species_id,
            x=0,
            y=0,
            energy=energy,
            max_energy=10.0,
            base_energy=5.0,
            growth_rate=1.0,
            survival_threshold=1.0,
            reproduction_interval=2,
            seed_min_dist=1.0,
            seed_max_dist=2.0,
            seed_energy_cost=1.0,
        ),
    )


def _add_swarm(world: ECSWorld, *, species_id: int, population: int = 4) -> None:
    entity = world.create_entity()
    world.add_component(
        entity.entity_id,
        SwarmComponent(
            entity_id=entity.entity_id,
            species_id=species_id,
            x=0,
            y=1,
            population=population,
            initial_population=population,
            energy=5.0,
            energy_min=1.0,
            velocity=1,
            consumption_rate=1.0,
        ),
    )


def test_z6_uses_strict_greater_than_threshold() -> None:
    """Z6 does not fire at equality and fires once flora energy strictly exceeds the threshold."""
    world = ECSWorld()
    _add_plant(world, species_id=0, energy=10.0)

    equal = check_termination(
        world,
        tick=0,
        max_ticks=100,
        z6_max_flora_energy=10.0,
        z5_check_all_herbivores=False,
    )
    above = check_termination(
        world,
        tick=0,
        max_ticks=100,
        z6_max_flora_energy=9.9,
        z5_check_all_herbivores=False,
    )

    assert equal.terminated is False
    assert above.terminated is True
    assert above.reason.startswith("Z6")


def test_z7_uses_strict_greater_than_threshold() -> None:
    """Z7 does not fire at equality and fires once herbivore population strictly exceeds the threshold."""
    world = ECSWorld()
    _add_plant(world, species_id=0)
    _add_swarm(world, species_id=0, population=10)

    equal = check_termination(world, tick=0, max_ticks=100, z7_max_total_herbivore_population=10)
    above = check_termination(world, tick=0, max_ticks=100, z7_max_total_herbivore_population=9)

    assert equal.terminated is False
    assert above.terminated is True
    assert above.reason.startswith("Z7")


def test_z5_reachable_when_z3_disabled() -> None:
    """With Z3 disabled, empty flora plus empty herbivores reaches Z5 instead of early flora extinction."""
    world = ECSWorld()

    result = check_termination(
        world,
        tick=0,
        max_ticks=100,
        z3_check_all_flora=False,
        z5_check_all_herbivores=True,
    )

    assert result.terminated is True
    assert result.reason.startswith("Z5")


def test_tick_metrics_path_does_not_query_world() -> None:
    """Supplying TickMetrics bypasses ECS scans and still evaluates rules correctly."""
    world = ECSWorld()

    def _fail_query(_component_type: type[object]) -> object:
        raise AssertionError("world.query should not run when tick_metrics is provided")

    world.query = _fail_query  # type: ignore[method-assign]
    metrics = TickMetrics(
        flora_alive=True,
        herbivores_alive=True,
        flora_species_alive={0},
        herbivore_species_alive={0},
        total_flora_energy=12.0,
        total_herbivore_population=5,
    )

    result = check_termination(
        world,
        tick=0,
        max_ticks=100,
        z6_max_flora_energy=10.0,
        tick_metrics=metrics,
    )

    assert result.terminated is True
    assert result.reason.startswith("Z6")


def test_condition_precedence_z2_before_z6() -> None:
    """When both conditions are true, Z2 takes precedence over Z6 by evaluation order."""
    world = ECSWorld()
    _add_plant(world, species_id=0, energy=50.0)

    result = check_termination(
        world,
        tick=0,
        max_ticks=100,
        z2_flora_species=1,
        z6_max_flora_energy=1.0,
    )

    assert result.terminated is True
    assert result.reason.startswith("Z2")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"z2_flora_species": 0},
        {"z4_herbivore_species": 0},
    ],
)
def test_species_extinction_does_not_fire_when_species_present(
    kwargs: dict[str, int],
) -> None:
    """Species-specific extinction checks do not fire when the requested species is still present."""
    world = ECSWorld()
    _add_plant(world, species_id=0)
    _add_swarm(world, species_id=0)

    result = check_termination(world, tick=0, max_ticks=100, **kwargs)

    assert result.terminated is False
    assert result.reason == ""


@pytest.mark.parametrize(
    ("setup", "kwargs"),
    [
        ("z2", {"z2_flora_species": 1}),
        ("z4", {"z4_herbivore_species": 1}),
        ("z6", {"z6_max_flora_energy": 10.0}),
        ("z7", {"z7_max_total_herbivore_population": 8}),
        ("z5", {"z3_check_all_flora": False, "z5_check_all_herbivores": True}),
        ("z3", {"z3_check_all_flora": True, "z5_check_all_herbivores": False}),
        ("precedence_z2_over_z6", {"z2_flora_species": 1, "z6_max_flora_energy": 1.0}),
    ],
)
def test_termination_result_matches_between_world_scan_and_tick_metrics(
    setup: str,
    kwargs: dict[str, int | float | bool],
) -> None:
    """World-scan and precomputed-metrics paths yield identical termination decisions."""
    world = ECSWorld()
    # Build case-specific entities into the same world instance.
    if setup == "precedence_z2_over_z6":
        _add_plant(world, species_id=0, energy=50.0)
        _add_swarm(world, species_id=0)
    elif setup == "z2":
        _add_plant(world, species_id=0)
        _add_swarm(world, species_id=0)
    elif setup == "z4":
        _add_plant(world, species_id=0)
        _add_swarm(world, species_id=0)
    elif setup == "z6":
        _add_plant(world, species_id=0, energy=25.0)
        _add_swarm(world, species_id=0)
    elif setup == "z7":
        _add_plant(world, species_id=0)
        _add_swarm(world, species_id=0, population=12)
    elif setup == "z5":
        _add_plant(world, species_id=0)
    elif setup == "z3":
        _add_swarm(world, species_id=0)

    metrics = collect_tick_metrics(world)
    via_world_scan = check_termination(world, tick=0, max_ticks=100, **kwargs)
    via_metrics = check_termination(world, tick=0, max_ticks=100, tick_metrics=metrics, **kwargs)

    assert via_metrics.terminated == via_world_scan.terminated
    assert via_metrics.reason == via_world_scan.reason
