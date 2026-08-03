# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Shared step-runner helpers for interaction-phase integration tests.

This module provides the single authoritative implementation of the three
interaction-phase step-runners. It is imported by:

- ``test_interaction_invariants/test_attrition_invariants.py``
- ``test_interaction_invariants/test_reproduction_invariants.py``
- ``test_interaction_invariants/test_mitosis_invariants.py``
- ``test_interaction_hypothesis_pilot.py``

Centralizing these helpers here eliminates the duplication that previously
existed between the ``test_interaction_invariants`` sub-package and
``test_interaction_hypothesis_pilot.py``.
"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np

from phids.api.schemas.species import (
    FloraSpeciesParams,
    HerbivoreSpeciesParams,
)
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.engine.systems.interaction import run_interaction

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

NO_DIET_MATRIX = np.zeros((1, 1), dtype=np.bool_)
"""A (1, 1) all-False diet matrix used to suppress feeding in isolated tests."""

_DUMMY_FLORA = [
    FloraSpeciesParams(
        species_id=0,
        name="Dummy",
        base_energy=10.0,
        max_energy=20.0,
        growth_rate=1.0,
        survival_threshold=1.0,
        reproduction_interval=1,
    )
]
"""Minimal single-species flora parameter list satisfying interaction-phase contracts."""

_DUMMY_HERBIVORE = [
    HerbivoreSpeciesParams(species_id=0, name="Dummy", energy_min=1.0, velocity=1, consumption_rate=1.0)
]
"""Minimal single-species herbivore parameter list satisfying interaction-phase contracts."""


# ---------------------------------------------------------------------------
# Entity factory
# ---------------------------------------------------------------------------


def spawn_swarm(
    world: ECSWorld,
    *,
    x: int,
    y: int,
    species_id: int,
    population: int,
    energy: float,
    energy_min: float,
    velocity: int,
    consumption_rate: float,
) -> int:
    """Spawn and register a single swarm entity for isolated interaction tests.

    Args:
        world: The ECSWorld registry into which the entity is added.
        x: Grid column coordinate for position registration.
        y: Grid row coordinate for position registration.
        species_id: Index of the herbivore species definition.
        population: Initial individual count.
        energy: Initial aggregate energy reserve.
        energy_min: Per-individual survival energy floor.
        velocity: Movement cooldown ticks (higher = slower).
        consumption_rate: Per-individual feeding speed multiplier.

    Returns:
        The unique integer entity ID of the newly created swarm.
    """
    entity = world.create_entity()
    world.add_component(
        entity.entity_id,
        SwarmComponent(
            entity_id=entity.entity_id,
            species_id=species_id,
            x=x,
            y=y,
            population=population,
            initial_population=max(1, population // 2),
            energy=energy,
            energy_min=energy_min,
            velocity=velocity,
            consumption_rate=consumption_rate,
        ),
    )
    world.register_position(entity.entity_id, x, y)
    return entity.entity_id


# ---------------------------------------------------------------------------
# Step-runners (single authoritative implementations, previously duplicated)
# ---------------------------------------------------------------------------


def run_attrition_step(
    *,
    population: int,
    initial_energy: float,
    upkeep: float,
    energy_min: float = 2.0,
) -> tuple[ECSWorld, int]:
    """Run one interaction tick with only metabolic attrition active.

    Feeding, movement, reproduction, and mitosis are all suppressed so that
    only the attrition arithmetic branch mutates world state.

    Args:
        population: Initial swarm individual count.
        initial_energy: Aggregate energy at tick start.
        upkeep: Per-individual energy drain coefficient.
        energy_min: Survival energy floor per individual.

    Returns:
        A ``(world, swarm_id)`` tuple after the tick completes.
    """
    world = ECSWorld()
    env = GridEnvironment(width=3, height=3, num_signals=1, num_toxins=1)
    swarm_id = spawn_swarm(
        world,
        x=1,
        y=1,
        species_id=0,
        population=population,
        energy=initial_energy,
        energy_min=energy_min,
        velocity=1,
        consumption_rate=1.0,
    )
    swarm = world.get_entity(swarm_id).get_component(SwarmComponent)
    swarm.move_cooldown = 1
    swarm.energy_upkeep_per_individual = upkeep
    swarm.reproduction_energy_divisor = 1_000_000.0
    swarm.split_population_threshold = 1000

    run_interaction(
        world,
        env,
        diet_matrix=NO_DIET_MATRIX,
        flora_species_params=_DUMMY_FLORA,
        herbivore_species_params=_DUMMY_HERBIVORE,
        tick=0,
    )
    return world, swarm_id


def run_reproduction_step(
    *,
    population: int,
    initial_energy: float,
    energy_min: float,
    reproduction_divisor: float,
) -> tuple[ECSWorld, int]:
    """Run one interaction tick with only the reproduction arithmetic branch active.

    Attrition upkeep is zeroed and mitosis is disabled so only surplus-energy
    conversion into offspring modifies world state.

    Args:
        population: Initial swarm individual count.
        initial_energy: Aggregate energy at tick start.
        energy_min: Per-individual survival energy floor.
        reproduction_divisor: Divisor applied to energy_min to compute offspring cost.

    Returns:
        A ``(world, swarm_id)`` tuple after the tick completes.
    """
    world = ECSWorld()
    env = GridEnvironment(width=3, height=3, num_signals=1, num_toxins=1)
    swarm_id = spawn_swarm(
        world,
        x=1,
        y=1,
        species_id=0,
        population=population,
        energy=initial_energy,
        energy_min=energy_min,
        velocity=1,
        consumption_rate=1.0,
    )
    swarm = world.get_entity(swarm_id).get_component(SwarmComponent)
    swarm.move_cooldown = 1
    swarm.energy_upkeep_per_individual = 0.0
    swarm.reproduction_energy_divisor = reproduction_divisor
    swarm.split_population_threshold = 1000

    run_interaction(
        world,
        env,
        diet_matrix=NO_DIET_MATRIX,
        flora_species_params=_DUMMY_FLORA,
        herbivore_species_params=_DUMMY_HERBIVORE,
        tick=0,
    )
    return world, swarm_id


def run_mitosis_step(
    *,
    population: int,
    initial_population: int,
    split_population_threshold: int,
    initial_energy: float,
    energy_min: float,
    offspring_pos: tuple[int, int] = (2, 1),
) -> tuple[ECSWorld, int, tuple[int, int], float]:
    """Run one interaction tick with only the mitosis branch active.

    Attrition, reproduction, movement, and feeding are all suppressed.
    The random-walk step for offspring placement is patched deterministically
    to ``offspring_pos``.

    Args:
        population: Current swarm individual count (triggers split if >= threshold).
        initial_population: Historical baseline population for threshold calculation.
        split_population_threshold: Population count at or above which fission occurs.
        initial_energy: Aggregate energy before the tick.
        energy_min: Per-individual survival energy floor.
        offspring_pos: Deterministic ``(x, y)`` position for the spawned child swarm.

    Returns:
        A ``(world, swarm_id, offspring_pos, pre_split_energy)`` tuple.
    """
    world = ECSWorld()
    env = GridEnvironment(width=4, height=4, num_signals=1, num_toxins=1)

    swarm_id = spawn_swarm(
        world,
        x=1,
        y=1,
        species_id=0,
        population=population,
        energy=initial_energy,
        energy_min=energy_min,
        velocity=1,
        consumption_rate=1.0,
    )
    swarm = world.get_entity(swarm_id).get_component(SwarmComponent)
    swarm.initial_population = initial_population
    swarm.move_cooldown = 1
    swarm.energy_upkeep_per_individual = 0.0
    swarm.reproduction_energy_divisor = 1_000_000.0
    swarm.split_population_threshold = split_population_threshold

    with patch(
        "phids.engine.systems.interaction.metabolism._random_walk_step",
        return_value=offspring_pos,
    ):
        run_interaction(
            world,
            env,
            diet_matrix=NO_DIET_MATRIX,
            flora_species_params=_DUMMY_FLORA,
            herbivore_species_params=_DUMMY_HERBIVORE,
            tick=0,
        )
    return world, swarm_id, offspring_pos, initial_energy
