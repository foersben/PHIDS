# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Metabolism, reproduction, and mitosis logic for swarms in the interaction system."""

from __future__ import annotations

from typing import TYPE_CHECKING

from phids.engine.components.swarm import SwarmComponent
from phids.engine.systems.interaction.movement import _random_walk_step
from phids.engine.systems.interaction.population import _accumulate_tile_population

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt

    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld, Entity


def _perform_mitosis(
    swarm: SwarmComponent,
    world: ECSWorld,
    env: GridEnvironment,
    scratch_cx: npt.NDArray[np.int32],
    scratch_cy: npt.NDArray[np.int32],
) -> SwarmComponent:
    """Split an oversized swarm into two equal daughter colonies via binary fission.

    Colony fission - the division of a supercolony that has exceeded its reproductive threshold
    into two independent daughter swarms - is a fundamental demographic event in social insect
    biology and clonal arthropod populations. This function implements the discrete analogue of
    that process within the ECS framework: the parent swarm retains ⌊n/2⌋ individuals and half
    the accumulated energy, while a new entity carrying a ``SwarmComponent`` with the complementary
    moiety is allocated, registered in the ECS world, and inserted into the spatial hash at a
    stochastically sampled adjacent cell. All heritable phenotypic parameters - ``energy_min``,
    ``velocity``, ``consumption_rate``, ``reproduction_energy_divisor``,
    ``energy_upkeep_per_individual``, and ``split_population_threshold`` - are copied verbatim to
    the offspring, reflecting the clonal genetic identity of the daughter colony. The energy
    partition is strictly symmetric (each colony receives exactly half of the parent pool) to
    conserve total simulated biomass across the fission event. Offspring placement via
    ``_random_walk_step`` ensures daughters are not deposited on top of the parent, reducing
    immediate re-coalescence and modelling the active dispersal phase observed following natural
    colony fission events.

    Args:
        swarm: Parent swarm component to be bisected; its ``population``, ``initial_population``,
            and ``energy`` fields are mutated in-place to reflect the retained half.
        world: ECSWorld registry used to allocate the new entity identifier and attach the
            offspring ``SwarmComponent``.
        env: Grid environment supplying the spatial dimensions required by ``_random_walk_step``
            to sample a valid dispersal cell adjacent to the parent's current position.
        scratch_cx: Pre-allocated buffer for random walk X offsets.
        scratch_cy: Pre-allocated buffer for random walk Y offsets.

    Returns:
        The ``SwarmComponent`` instance attached to the newly spawned offspring entity,
        containing its assigned population count, energy allocation, and grid coordinates.

    See Also:
        _random_walk_step
    """
    offspring_population = swarm.population // 2
    retained_population = swarm.population - offspring_population
    swarm.population = retained_population
    swarm.initial_population = retained_population
    offspring_x, offspring_y = _random_walk_step(swarm.x, swarm.y, env.width, env.height, scratch_cx, scratch_cy)

    new_entity = world.create_entity()
    offspring = SwarmComponent(
        entity_id=new_entity.entity_id,
        species_id=swarm.species_id,
        x=offspring_x,
        y=offspring_y,
        population=offspring_population,
        initial_population=offspring_population,
        energy=swarm.energy / 2.0,
        energy_min=swarm.energy_min,
        velocity=swarm.velocity,
        consumption_rate=swarm.consumption_rate,
        reproduction_energy_divisor=swarm.reproduction_energy_divisor,
        energy_upkeep_per_individual=swarm.energy_upkeep_per_individual,
        split_population_threshold=swarm.split_population_threshold,
    )
    swarm.energy /= 2.0
    world.add_component(new_entity.entity_id, offspring)
    world.register_position(new_entity.entity_id, offspring_x, offspring_y)
    return offspring


def _resolve_swarm_metabolism_and_reproduction(
    swarm: SwarmComponent,
    entity: Entity,
    world: ECSWorld,
    env: GridEnvironment,
    tile_populations: list[int],
    dead_swarms: list[int],
    scratch_cx: npt.NDArray[np.int32],
    scratch_cy: npt.NDArray[np.int32],
) -> bool:
    """Apply metabolic upkeep, casualty liquidation, reproduction, and mitosis. Returns False if dead.

    This function consolidates the post-feeding life-cycle mechanics for a swarm:

    1. **Metabolic Cost**: Deducts energy based on population size and baseline needs.
    2. **Casualty Liquidation**: Triggers "death by starvation" if energy reserves are insufficient to support the
    current population.
    3. **Reproduction & Mitosis**: Calculates and executes population doubling (mitosis) if the swarm has accumulated
    enough excess energy.

    The function returns `False` if the swarm's population drops to zero, signaling to the main loop that the entity
    should be cleaned up.

    Args:
        swarm: The swarm component.
        entity: The entity component.
        world: The ECS world.
        env: The grid environment.
        tile_populations: The tile populations.
        dead_swarms: The list to append dead swarm IDs to.
        scratch_cx: Pre-allocated buffer for random walk X offsets.
        scratch_cy: Pre-allocated buffer for random walk Y offsets.

    Returns:
        False if the swarm died, True otherwise.
    """
    metabolic_cost = swarm.population * swarm.energy_min * swarm.energy_upkeep_per_individual
    swarm.energy -= metabolic_cost

    if swarm.energy < 0.0 and swarm.population > 0:
        previous_population = swarm.population
        deficit = -swarm.energy
        casualties = int(deficit // swarm.energy_min)
        if casualties * swarm.energy_min < deficit:
            casualties += 1
        swarm.population = max(0, swarm.population - casualties)
        _accumulate_tile_population(
            tile_populations,
            swarm.x,
            swarm.y,
            env.width,
            swarm.population - previous_population,
        )
        total_casualty_energy = casualties * swarm.energy_min
        leftover_energy = total_casualty_energy - deficit
        swarm.energy = max(0.0, leftover_energy)

    if swarm.population <= 0:
        world.unregister_position(entity.entity_id, swarm.x, swarm.y)
        dead_swarms.append(entity.entity_id)
        return False

    # Reproduction
    baseline_energy = swarm.population * swarm.energy_min
    if swarm.energy > baseline_energy:
        surplus = swarm.energy - baseline_energy
        cost_per_offspring = max(
            swarm.energy_min,
            swarm.energy_min * swarm.reproduction_energy_divisor,
        )

        new_individuals = int(surplus // cost_per_offspring)
        if new_individuals > 0:
            previous_population = swarm.population
            swarm.population += new_individuals
            _accumulate_tile_population(
                tile_populations,
                swarm.x,
                swarm.y,
                env.width,
                swarm.population - previous_population,
            )
            swarm.energy -= new_individuals * cost_per_offspring

    # Mitosis
    threshold = swarm.split_population_threshold
    if swarm.population >= threshold:
        pre_split_population = swarm.population
        offspring = _perform_mitosis(swarm, world, env, scratch_cx, scratch_cy)
        _accumulate_tile_population(
            tile_populations,
            swarm.x,
            swarm.y,
            env.width,
            swarm.population - pre_split_population,
        )
        _accumulate_tile_population(
            tile_populations,
            offspring.x,
            offspring.y,
            env.width,
            offspring.population,
        )
    return True
