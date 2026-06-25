"""Focused mutation-pilot regressions for termination-condition branch semantics."""

from __future__ import annotations

import pytest

from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.ecs import ECSWorld
from phids.telemetry.conditions import check_termination
from phids.telemetry.tick_metrics import collect_tick_metrics


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
            max_energy=20.0,
            base_energy=10.0,
            growth_rate=2.0,
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


def test_z1_precedes_ecological_rules_when_tick_budget_is_exhausted() -> None:
    """Z1 terminates first even when other ecological rules could also be true."""
    world = ECSWorld()
    _add_plant(world, species_id=0, energy=50.0)
    _add_swarm(world, species_id=0, population=20)

    result = check_termination(
        world,
        tick=100,
        max_ticks=100,
        z2_flora_species=1,
        z6_max_flora_energy=1.0,
        z7_max_total_herbivore_population=1,
    )

    assert result.terminated is True
    assert result.reason.startswith("Z1")


@pytest.mark.parametrize(
    ("kwargs_equal", "kwargs_above", "expected_rule"),
    [
        (
            {"z6_max_flora_energy": 10.0, "z5_check_all_herbivores": False},
            {"z6_max_flora_energy": 9.0, "z5_check_all_herbivores": False},
            "Z6",
        ),
        (
            {"z7_max_total_herbivore_population": 10},
            {"z7_max_total_herbivore_population": 9},
            "Z7",
        ),
    ],
)
def test_threshold_rules_require_strict_greater_than(
    kwargs_equal: dict[str, float | int | bool],
    kwargs_above: dict[str, float | int | bool],
    expected_rule: str,
) -> None:
    """Equality does not trigger thresholds, while strictly greater values do."""
    world = ECSWorld()
    _add_plant(world, species_id=0, energy=10.0)
    _add_swarm(world, species_id=0, population=10)

    equal = check_termination(world, tick=0, max_ticks=100, **kwargs_equal)
    above = check_termination(world, tick=0, max_ticks=100, **kwargs_above)

    assert equal.terminated is False
    assert above.terminated is True
    assert above.reason.startswith(expected_rule)


def test_negative_threshold_sentinels_disable_z6_and_z7() -> None:
    """Negative thresholds keep Z6 and Z7 disabled while live entities remain present."""
    world = ECSWorld()
    _add_plant(world, species_id=0, energy=200.0)
    _add_swarm(world, species_id=0, population=200)

    result = check_termination(
        world,
        tick=0,
        max_ticks=100,
        z6_max_flora_energy=-1.0,
        z7_max_total_herbivore_population=-1,
    )

    assert result.terminated is False
    assert result.reason == ""


def test_z2_precedes_z6_when_both_are_true() -> None:
    """Species-extinction checks run before aggregate-energy checks by design."""
    world = ECSWorld()
    _add_plant(world, species_id=0, energy=50.0)
    _add_swarm(world, species_id=0, population=4)

    result = check_termination(
        world,
        tick=0,
        max_ticks=100,
        z2_flora_species=1,
        z6_max_flora_energy=1.0,
    )

    assert result.terminated is True
    assert result.reason.startswith("Z2")


def test_tick_metrics_path_matches_world_scan_for_precedence_case() -> None:
    """TickMetrics and world-scan paths resolve the same precedence outcome."""
    world = ECSWorld()
    _add_plant(world, species_id=0, energy=50.0)
    _add_swarm(world, species_id=0, population=4)

    metrics = collect_tick_metrics(world)
    via_world_scan = check_termination(
        world,
        tick=0,
        max_ticks=100,
        z2_flora_species=1,
        z6_max_flora_energy=1.0,
    )
    via_metrics = check_termination(
        world,
        tick=0,
        max_ticks=100,
        z2_flora_species=1,
        z6_max_flora_energy=1.0,
        tick_metrics=metrics,
    )

    assert via_metrics.terminated == via_world_scan.terminated
    assert via_metrics.reason == via_world_scan.reason
