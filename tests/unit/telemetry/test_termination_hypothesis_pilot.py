"""Bounded Hypothesis pilot for termination parity between world scans and TickMetrics."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from phids.engine.core.ecs import ECSWorld
from phids.telemetry.conditions import check_termination
from phids.telemetry.tick_metrics import collect_tick_metrics

try:
    from hypothesis import HealthCheck, given, settings, strategies as st
except ModuleNotFoundError:
    pytest.skip("Install hypothesis to run optional property pilots.", allow_module_level=True)


@pytest.mark.hypothesis_pilot
@settings(
    max_examples=96,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    flora_count=st.integers(min_value=0, max_value=16),
    herbivore_count=st.integers(min_value=0, max_value=16),
    flora_energy_unit=st.sampled_from((1.0, 2.0, 4.0, 8.0)),
    herbivore_population_unit=st.integers(min_value=1, max_value=8),
    z2_species=st.sampled_from((-1, 0, 1)),
    z4_species=st.sampled_from((-1, 0, 1)),
)
def test_check_termination_world_scan_matches_tick_metrics_for_bounded_worlds(
    flora_count: int,
    herbivore_count: int,
    flora_energy_unit: float,
    herbivore_population_unit: int,
    z2_species: int,
    z4_species: int,
    add_plant: Callable[..., int],
    add_swarm: Callable[..., int],
) -> None:
    """Termination decision and reason remain identical across both evaluation pathways."""
    world = ECSWorld()

    for idx in range(flora_count):
        add_plant(
            world,
            idx % 4,
            (idx // 4) % 4,
            species_id=idx % 2,
            energy=flora_energy_unit,
        )

    for idx in range(herbivore_count):
        add_swarm(
            world,
            (idx + 1) % 4,
            ((idx + 1) // 4) % 4,
            species_id=idx % 2,
            population=herbivore_population_unit,
            energy=float(herbivore_population_unit),
        )

    total_flora_energy = float(flora_count) * flora_energy_unit
    total_herbivore_population = herbivore_count * herbivore_population_unit

    kwargs: dict[str, int | float | bool] = {
        "z2_flora_species": z2_species,
        "z3_check_all_flora": True,
        "z4_herbivore_species": z4_species,
        "z5_check_all_herbivores": True,
        "z6_max_flora_energy": max(-1.0, total_flora_energy - 0.5),
        "z7_max_total_herbivore_population": max(-1, total_herbivore_population - 1),
    }

    via_world_scan = check_termination(world, tick=0, max_ticks=128, **kwargs)
    metrics = collect_tick_metrics(world)
    via_metrics = check_termination(world, tick=0, max_ticks=128, tick_metrics=metrics, **kwargs)

    assert via_metrics.terminated == via_world_scan.terminated
    assert via_metrics.reason == via_world_scan.reason
