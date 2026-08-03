# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Integration tests for PHIDS plant lifecycle and mycorrhizal network dynamics."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import pytest

from phids.api.schemas.species import FloraSpeciesParams
from phids.api.schemas.triggers import PassiveDefensesSchema
from phids.engine.components.plant import PlantComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.engine.systems.lifecycle import run_lifecycle

if TYPE_CHECKING:
    from collections.abc import Callable


def _flora_params(species_id: int = 0) -> FloraSpeciesParams:
    return FloraSpeciesParams(
        species_id=species_id,
        name=f"flora-{species_id}",
        base_energy=10.0,
        max_energy=30.0,
        growth_rate=5.0,
        survival_threshold=1.0,
        reproduction_interval=1,
        seed_min_dist=1.0,
        seed_max_dist=1.0,
        seed_energy_cost=2.0,
        triggers=[],
        passive_defenses=PassiveDefensesSchema(digestibility_modifier=1.0, mechanical_damage_per_bite=0.0),
    )


def test_lifecycle_establishes_mycorrhizal_connections_with_cost(add_plant: Callable[..., int]) -> None:
    """Verify lifecycle creates reciprocal mycorrhizal links and deducts connection cost."""
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=1, num_toxins=1)
    p1 = add_plant(world, 1, 1, species_id=0, energy=10.0, growth_rate=0.0)
    p2 = add_plant(world, 1, 2, species_id=0, energy=10.0, growth_rate=0.0)
    params = {0: _flora_params(0)}
    run_lifecycle(
        world,
        env,
        tick=1,
        flora_species_params=params,
        mycorrhizal_connection_cost=1.5,
        mycorrhizal_growth_interval_ticks=1,
        mycorrhizal_inter_species=False,
    )
    plant1 = world.get_entity(p1).get_component(PlantComponent)
    plant2 = world.get_entity(p2).get_component(PlantComponent)
    assert p2 in plant1.mycorrhizal_connections
    assert p1 in plant2.mycorrhizal_connections
    assert plant1.energy < 10.0
    assert plant2.energy < 10.0


def test_lifecycle_respects_interspecies_connection_switch(add_plant: Callable[..., int]) -> None:
    """Verify inter-species mycorrhizal links are blocked when the feature flag is disabled."""
    world = ECSWorld()
    env = GridEnvironment(width=4, height=4, num_signals=1, num_toxins=1)
    p1 = add_plant(world, 1, 1, species_id=0, energy=8.0)
    p2 = add_plant(world, 2, 1, species_id=1, energy=8.0)
    params = {0: _flora_params(0), 1: _flora_params(1)}
    run_lifecycle(
        world,
        env,
        tick=1,
        flora_species_params=params,
        mycorrhizal_connection_cost=1.0,
        mycorrhizal_growth_interval_ticks=1,
        mycorrhizal_inter_species=False,
    )
    plant1 = world.get_entity(p1).get_component(PlantComponent)
    assert p2 not in plant1.mycorrhizal_connections


def test_lifecycle_mycorrhiza_does_not_spend_last_surplus_energy(add_plant: Callable[..., int]) -> None:
    """Verify mycorrhiza formation does not consume the final survival surplus."""
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=1, num_toxins=1)
    p1 = add_plant(world, 1, 1, species_id=0, energy=1.5)
    p2 = add_plant(world, 2, 1, species_id=0, energy=1.5)
    for entity_id in (p1, p2):
        plant = world.get_entity(entity_id).get_component(PlantComponent)
        plant.growth_rate = 0.0
        plant.reproduction_interval = 999
        plant.seed_energy_cost = 999.0
    run_lifecycle(
        world,
        env,
        tick=0,
        flora_species_params={0: _flora_params(0)},
        mycorrhizal_connection_cost=1.0,
        mycorrhizal_growth_interval_ticks=1,
        mycorrhizal_inter_species=False,
    )
    plant1 = world.get_entity(p1).get_component(PlantComponent)
    plant2 = world.get_entity(p2).get_component(PlantComponent)
    assert plant1.mycorrhizal_connections == set()
    assert plant2.mycorrhizal_connections == set()
    assert plant1.energy == pytest.approx(1.5)
    assert plant2.energy == pytest.approx(1.5)


def test_lifecycle_mycorrhiza_respects_interval_and_forms_parallel_pairs(
    add_plant: Callable[..., int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify growth interval gating and deterministic pair formation for parallel links."""
    world = ECSWorld()
    env = GridEnvironment(width=8, height=4, num_signals=1, num_toxins=1)
    p1 = add_plant(world, 1, 1, species_id=0, energy=12.0)
    p2 = add_plant(world, 2, 1, species_id=0, energy=12.0)
    p3 = add_plant(world, 5, 1, species_id=0, energy=12.0)
    p4 = add_plant(world, 6, 1, species_id=0, energy=12.0)
    for entity_id in (p1, p2, p3, p4):
        plant = world.get_entity(entity_id).get_component(PlantComponent)
        plant.reproduction_interval = 999
        plant.seed_energy_cost = 999.0
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    params = {0: _flora_params(0)}
    growth_interval = 4
    for tick in range(growth_interval - 1):
        run_lifecycle(
            world,
            env,
            tick=tick,
            flora_species_params=params,
            mycorrhizal_connection_cost=1.0,
            mycorrhizal_growth_interval_ticks=growth_interval,
            mycorrhizal_inter_species=False,
        )
    for entity_id in (p1, p2, p3, p4):
        plant = world.get_entity(entity_id).get_component(PlantComponent)
        assert plant.mycorrhizal_connections == set()
    run_lifecycle(
        world,
        env,
        tick=growth_interval - 1,
        flora_species_params=params,
        mycorrhizal_connection_cost=1.0,
        mycorrhizal_growth_interval_ticks=growth_interval,
        mycorrhizal_inter_species=False,
    )
    plant1 = world.get_entity(p1).get_component(PlantComponent)
    plant2 = world.get_entity(p2).get_component(PlantComponent)
    plant3 = world.get_entity(p3).get_component(PlantComponent)
    plant4 = world.get_entity(p4).get_component(PlantComponent)
    first_links = {
        tuple(sorted((left, right)))
        for left, plant in ((p1, plant1), (p2, plant2), (p3, plant3), (p4, plant4))
        for right in plant.mycorrhizal_connections
        if left < right
    }
    assert first_links == {(p1, p2), (p3, p4)}


def test_lifecycle_mycorrhiza_limits_one_new_link_per_plant_per_tick(
    add_plant: Callable[..., int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify each plant forms at most one new mycorrhizal link per tick."""
    world = ECSWorld()
    env = GridEnvironment(width=5, height=5, num_signals=1, num_toxins=1)
    p1 = add_plant(world, 2, 1, species_id=0, energy=12.0)
    p2 = add_plant(world, 1, 1, species_id=0, energy=12.0)
    p3 = add_plant(world, 3, 1, species_id=0, energy=12.0)
    for entity_id in (p1, p2, p3):
        plant = world.get_entity(entity_id).get_component(PlantComponent)
        plant.reproduction_interval = 999
        plant.seed_energy_cost = 999.0
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    run_lifecycle(
        world,
        env,
        tick=0,
        flora_species_params={0: _flora_params(0)},
        mycorrhizal_connection_cost=1.0,
        mycorrhizal_growth_interval_ticks=1,
        mycorrhizal_inter_species=False,
    )
    plant1 = world.get_entity(p1).get_component(PlantComponent)
    plant2 = world.get_entity(p2).get_component(PlantComponent)
    plant3 = world.get_entity(p3).get_component(PlantComponent)
    assert len(plant1.mycorrhizal_connections) == 1
    assert plant2.mycorrhizal_connections != plant3.mycorrhizal_connections
