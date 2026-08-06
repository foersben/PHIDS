# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Canon alignment invariant tests.

Verifies the correct semantics of ``mycorrhizal_signal_velocity`` as a hops-per-tick
*rate* (higher = more signal delivered per tick), and that ``translocation_rate`` is
properly wired through from ``FloraSpeciesParams`` to ``PlantComponent`` at entity
construction and seed-offspring spawn time.
"""

from __future__ import annotations

import math

import pytest

from phids.engine.components.plant import PlantComponent
from phids.engine.components.substances import SubstanceComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.engine.systems.signaling.emission import _process_signal_emission
from phids.engine.systems.signaling.lifecycle import _phase_manage_nutrition_recovery

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_env(num_signals: int = 1, width: int = 5, height: int = 5) -> GridEnvironment:
    return GridEnvironment(width=width, height=height, num_signals=num_signals, num_toxins=1)


def _make_plant(entity_id: int, x: int, y: int, translocation_rate: float = 0.2) -> PlantComponent:
    return PlantComponent(
        entity_id=entity_id,
        species_id=0,
        x=x,
        y=y,
        energy=100.0,
        max_energy=200.0,
        base_energy=50.0,
        growth_rate=5.0,
        survival_threshold=1.0,
        reproduction_interval=10,
        seed_min_dist=1.0,
        seed_max_dist=3.0,
        seed_energy_cost=5.0,
        translocation_rate=translocation_rate,
    )


def _make_substance(entity_id: int, owner_id: int, substance_id: int = 0) -> SubstanceComponent:
    sub = SubstanceComponent(entity_id=entity_id, owner_plant_id=owner_id, substance_id=substance_id)
    sub.active = True
    sub.triggered_this_tick = True
    sub.is_toxin = False
    return sub


# ---------------------------------------------------------------------------
# Test 1: mycorrhizal_signal_velocity is a rate (higher = more signal per tick)
# ---------------------------------------------------------------------------


@pytest.mark.scientific_invariant
def test_mycorrhizal_signal_velocity_scales_relay_proportionally() -> None:
    """Higher signal_velocity delivers proportionally more relay concentration per tick.

    With signal_velocity=1 the relay target receives per_target_amount * 1.
    With signal_velocity=2 the relay target receives per_target_amount * 2.
    The ratio must equal the velocity ratio exactly.
    """
    world = ECSWorld()

    source_entity = world.create_entity()
    source_plant = _make_plant(source_entity.entity_id, x=2, y=2)
    world.add_component(source_entity.entity_id, source_plant)
    world.register_position(source_entity.entity_id, 2, 2)

    relay_entity = world.create_entity()
    relay_plant = _make_plant(relay_entity.entity_id, x=3, y=2)
    world.add_component(relay_entity.entity_id, relay_plant)
    world.register_position(relay_entity.entity_id, 3, 2)

    # Establish bidirectional mycorrhizal connection
    source_plant.mycorrhizal_connections.add(relay_entity.entity_id)
    relay_plant.mycorrhizal_connections.add(source_entity.entity_id)

    sub = _make_substance(99, source_entity.entity_id, substance_id=0)
    emit_rate = 0.4

    def _measure_relay(velocity: int) -> float:
        env = _make_env(num_signals=1)
        _process_signal_emission(
            sub=sub,
            plant=source_plant,
            env=env,
            world=world,
            substance_emit_rate=emit_rate,
            mycorrhizal_inter_species=True,
            signal_velocity=velocity,
        )
        return float(env.signal_layers[0, relay_plant.x, relay_plant.y])

    relay_at_1 = _measure_relay(1)
    relay_at_2 = _measure_relay(2)

    assert relay_at_1 > 0.0, "Relay concentration must be positive for velocity=1"
    assert relay_at_2 > relay_at_1, "velocity=2 must deliver more signal than velocity=1"
    assert math.isclose(relay_at_2, relay_at_1 * 2.0, rel_tol=1e-9), (
        f"velocity=2 should deliver exactly 2x the concentration of velocity=1, got {relay_at_1} vs {relay_at_2}"
    )


# ---------------------------------------------------------------------------
# Test 2: translocation_rate wire-through - seeded offspring inherit species param
# ---------------------------------------------------------------------------


@pytest.mark.scientific_invariant
def test_translocation_rate_inherited_by_seed_offspring() -> None:
    """Seeded plant offspring must inherit translocation_rate from FloraSpeciesParams.

    Previously translocation_rate was silently dropped at spawn time, defaulting to 0.2.
    This test guards against that regression.
    """
    from phids.api.schemas.species import FloraSpeciesParams
    from phids.engine.systems.lifecycle import _attempt_reproduction

    species_translocation_rate = 0.65

    flora_params = FloraSpeciesParams(
        species_id=0,
        name="TestFlora",
        base_energy=10.0,
        max_energy=100.0,
        growth_rate=5.0,
        survival_threshold=1.0,
        reproduction_interval=5,
        seed_min_dist=1.0,
        seed_max_dist=3.0,
        seed_energy_cost=5.0,
        translocation_rate=species_translocation_rate,
    )
    flora_species_params: dict[int, FloraSpeciesParams] = {0: flora_params}

    world = ECSWorld()
    env = _make_env(width=10, height=10)

    parent_entity = world.create_entity()
    parent_plant = PlantComponent(
        entity_id=parent_entity.entity_id,
        species_id=0,
        x=5,
        y=5,
        energy=50.0,
        max_energy=100.0,
        base_energy=10.0,
        growth_rate=5.0,
        survival_threshold=1.0,
        reproduction_interval=5,
        seed_min_dist=1.0,
        seed_max_dist=3.0,
        seed_energy_cost=5.0,
        last_reproduction_tick=0,
        translocation_rate=species_translocation_rate,
    )
    world.add_component(parent_entity.entity_id, parent_plant)
    world.register_position(parent_entity.entity_id, 5, 5)

    # Run reproduction at a tick far past the reproduction_interval (tick=100 >> interval=5)
    offspring = _attempt_reproduction(
        parent_plant, tick=100, world=world, env=env, flora_species_params=flora_species_params
    )

    assert len(offspring) == 1, "Reproduction should produce exactly one offspring"
    child: PlantComponent = offspring[0]

    assert math.isclose(child.translocation_rate, species_translocation_rate, rel_tol=1e-9), (
        f"Offspring translocation_rate {child.translocation_rate!r} must equal "
        f"species param {species_translocation_rate!r}, not the dataclass default 0.2"
    )


# ---------------------------------------------------------------------------
# Test 3: higher translocation_rate converges apparent_nutrition_factor faster
# ---------------------------------------------------------------------------


@pytest.mark.scientific_invariant
def test_translocation_rate_controls_recovery_convergence_speed() -> None:
    """A plant with translocation_rate=0.4 must recover apparent_nutrition_factor twice as fast.

    Gap reduction per tick = (1.0 - x(t)) * rate, so doubling rate doubles the reduction.
    Recovery formula: x(t+1) = x(t) + (1.0 - x(t)) * rate.
    """
    rate_slow = 0.2
    rate_fast = 0.4
    start_value = 0.5

    plant_slow = _make_plant(entity_id=1, x=0, y=0, translocation_rate=rate_slow)
    plant_slow.apparent_nutrition_factor = start_value
    plant_slow.withdrawal_ticks_remaining = 0

    plant_fast = _make_plant(entity_id=2, x=0, y=0, translocation_rate=rate_fast)
    plant_fast.apparent_nutrition_factor = start_value
    plant_fast.withdrawal_ticks_remaining = 0

    world_slow = ECSWorld()
    e_slow = world_slow.create_entity()
    world_slow.add_component(e_slow.entity_id, plant_slow)

    world_fast = ECSWorld()
    e_fast = world_fast.create_entity()
    world_fast.add_component(e_fast.entity_id, plant_fast)

    _phase_manage_nutrition_recovery(world_slow)
    _phase_manage_nutrition_recovery(world_fast)

    gap_reduction_slow = plant_slow.apparent_nutrition_factor - start_value
    gap_reduction_fast = plant_fast.apparent_nutrition_factor - start_value

    assert gap_reduction_fast > gap_reduction_slow, (
        "Higher translocation_rate must produce larger gap reduction per tick"
    )
    assert math.isclose(gap_reduction_fast, gap_reduction_slow * 2.0, rel_tol=1e-9), (
        f"rate_fast=0.4 should close exactly 2x the gap of rate_slow=0.2 per tick, "
        f"got slow={gap_reduction_slow:.6f}, fast={gap_reduction_fast:.6f}"
    )
