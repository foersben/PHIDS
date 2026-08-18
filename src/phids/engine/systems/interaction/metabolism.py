# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Metabolism, reproduction, and mitosis logic for swarms in the interaction system."""

from __future__ import annotations

from typing import TYPE_CHECKING

from phids.engine.components.swarm import SwarmComponent
from phids.engine.systems.interaction.movement.random_walk import _random_walk_step
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
    tile_populations: npt.NDArray[np.int32] | list[int],
    dead_swarms: list[int],
    scratch_cx: npt.NDArray[np.int32],
    scratch_cy: npt.NDArray[np.int32],
    herbivore_death_causes: dict[str, int] | None = None,
    is_slow_tick: bool = True,
) -> bool:
    """Apply metabolic upkeep, casualty liquidation, reproduction, and mitosis.

    Called on the Daily Loop (is_medium_tick). Per-tick parameter values
    (``energy_upkeep_per_individual``) are multiplied by 24 to represent the
    accumulated metabolic cost over the 24-hour stride.

    Mitosis (colony fission) is additionally gated to ``is_slow_tick`` (weekly,
    168-tick stride) since demographic splits are macroscopic population events
    that should not fire multiple times per day.

    Returns False if the swarm's population drops to zero.

    Args:
        swarm: The swarm component.
        entity: The entity component.
        world: The ECS world.
        env: The grid environment.
        tile_populations: The tile populations.
        dead_swarms: The list to append dead swarm IDs to.
        scratch_cx: Pre-allocated buffer for random walk X offsets.
        scratch_cy: Pre-allocated buffer for random walk Y offsets.
        herbivore_death_causes: Dictionary to track herbivore death causes.
        is_slow_tick: True on weekly (168-tick) boundaries - gates mitosis.

    Returns:
        False if the swarm died, True otherwise.
    """
    # Metabolic cost: scaled by MEDIUM_TICK_STRIDE (24 hours) since this function
    # is only called on the daily medium-loop gate.
    metabolic_cost = swarm.population * swarm.energy_min * swarm.energy_upkeep_per_individual * 24
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
        # The engine completely removes the need to track, store, or serialize sub-individual
        # fractional states by dropping any leftover energy from the ceiling casualty calculation.
        # This prevents swarms from surviving on "ghost energy" and enforces a sharp starvation curve.
        swarm.energy = 0.0

    if swarm.population <= 0:
        world.unregister_position(entity.entity_id, swarm.x, swarm.y)
        dead_swarms.append(entity.entity_id)
        if herbivore_death_causes is not None:
            herbivore_death_causes["death_starvation"] += 1
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

    # Mitosis (Slow Loop - weekly, 168-tick stride).
    # Colony fission is a macroscopic demographic event; gating it to the weekly
    # slow loop prevents multiple splits per day while preserving biological realism.
    if is_slow_tick:
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
