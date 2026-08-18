# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Core swarm movement resolution logic.

Provides the primary orchestrator `_resolve_swarm_movement` which combines anchoring, repulsion,
and flow field movement for herbivore swarms.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from phids.engine.systems.interaction.movement.anchoring import _is_swarm_anchored
from phids.engine.systems.interaction.movement.choices import _choose_neighbour_by_flow_probability
from phids.engine.systems.interaction.movement.incidental import _resolve_incidental_mortality
from phids.engine.systems.interaction.movement.neighbors import _calculate_toroidal_delta
from phids.engine.systems.interaction.movement.random_walk import _random_walk_step
from phids.engine.systems.interaction.population import TILE_CARRYING_CAPACITY, _accumulate_tile_population

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt

    from phids.api.schemas.species import HerbivoreSpeciesParams
    from phids.engine.components.swarm import SwarmComponent
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld, Entity


def _resolve_swarm_movement(
    swarm: SwarmComponent,
    entity: Entity,
    env: GridEnvironment,
    world: ECSWorld,
    diet_matrix: list[list[bool]] | npt.NDArray[np.bool_],
    tile_populations: npt.NDArray[np.int32] | list[int],
    herbivore_params_dict: dict[int, HerbivoreSpeciesParams],
    scratch_cx: npt.NDArray[np.int32],
    scratch_cy: npt.NDArray[np.int32],
    scratch_scores: npt.NDArray[np.float64],
    scratch_adjusted: npt.NDArray[np.float64],
    scratch_weights: npt.NDArray[np.float64],
) -> bool:
    """Evaluate and execute movement phase for a single swarm, return has_moved.

    This function implements the core movement logic for a herbivore swarm, handling
    three distinct priority regimes: **anchoring** (staying put on food), **repulsion** (moving
    off crowded tiles), and **attraction** (moving along the global flow field).

    Args:
        swarm: The swarm component.
        entity: The entity.
        env: The grid environment.
        world: The ECS world.
        diet_matrix: The boolean diet compatibility matrix.
        tile_populations: Array of current population counts per tile.
        herbivore_params_dict: Dictionary mapping species config IDs to their parameters.
        scratch_cx: Pre-allocated buffer for candidate X coordinates.
        scratch_cy: Pre-allocated buffer for candidate Y coordinates.
        scratch_scores: Pre-allocated buffer for unadjusted field scores.
        scratch_adjusted: Pre-allocated buffer for exponentiated scores.
        scratch_weights: Pre-allocated buffer for final normalized probabilities.

    Returns:
        True if the swarm physically changed (x,y) coordinates, False if anchored.
    """
    if swarm.move_cooldown > 0:
        swarm.move_cooldown -= 1
        return False

    # Decay aversion memory per movement tick
    if getattr(swarm, "aversion_memory", 0.0) > 0.0:
        swarm.aversion_memory *= 0.95
        if swarm.aversion_memory < 0.01:
            swarm.aversion_memory = 0.0

    old_x, old_y = swarm.x, swarm.y

    # 1. Crowding takes strict precedence (Physical Jostling)
    if (
        not swarm.repelled
        and 0 <= swarm.x < env.width
        and 0 <= swarm.y < env.height
        and tile_populations[swarm.y * env.width + swarm.x] > TILE_CARRYING_CAPACITY
    ):
        from phids.engine.core.herbivore_params import get_herbivore_evasion_duration

        k_ticks = get_herbivore_evasion_duration(herbivore_params_dict, swarm.species_id)
        swarm.repelled = True
        swarm.repelled_ticks_remaining = k_ticks

    if swarm.repelled and swarm.repelled_ticks_remaining > 0:
        nx, ny = _random_walk_step(swarm.x, swarm.y, env.width, env.height, scratch_cx, scratch_cy)
        swarm.repelled_ticks_remaining -= 1
        if swarm.repelled_ticks_remaining <= 0:
            swarm.repelled = False
    else:
        # 2. Fast O(1) check: are we already standing on valid, uneaten food?
        if _is_swarm_anchored(swarm, env, diet_matrix):
            nx, ny = swarm.x, swarm.y
        else:
            from phids.engine.core.herbivore_params import get_herbivore_softmax_temperature

            tau = get_herbivore_softmax_temperature(herbivore_params_dict, swarm.species_id)
            # 3. Resume normal gradient tracking if no food is present.
            nx, ny = _choose_neighbour_by_flow_probability(
                swarm,
                env.flow_field,
                env.width,
                env.height,
                scratch_cx,
                scratch_cy,
                scratch_scores,
                scratch_adjusted,
                scratch_weights,
                tile_populations=tile_populations,
                tau=tau,
            )

    has_moved = False
    if (nx, ny) != (old_x, old_y):
        world.move_entity(entity.entity_id, old_x, old_y, nx, ny)
        _accumulate_tile_population(tile_populations, old_x, old_y, env.width, -swarm.population)
        _accumulate_tile_population(tile_populations, nx, ny, env.width, swarm.population)
        swarm.x, swarm.y = nx, ny

        swarm.last_dx = _calculate_toroidal_delta(nx, old_x, env.width)
        swarm.last_dy = _calculate_toroidal_delta(ny, old_y, env.height)
        has_moved = True

        # Plan 3: Evaluate probabilistic incidental mortality (trampling or clipping) on co-located flora
        _resolve_incidental_mortality(swarm, nx, ny, world, env, herbivore_params_dict)

    swarm.move_cooldown = swarm.velocity - 1
    return has_moved
