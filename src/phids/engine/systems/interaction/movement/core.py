# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Core logic."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt

from phids.engine.systems.interaction.movement.flow_field import _choose_neighbour_by_flow_probability
from phids.engine.systems.interaction.movement.mortality import _resolve_incidental_mortality
from phids.engine.systems.interaction.movement.random_walk import _random_walk_step
from phids.engine.systems.interaction.population import TILE_CARRYING_CAPACITY, _accumulate_tile_population

if TYPE_CHECKING:
    from phids.api.schemas.species import HerbivoreSpeciesParams
    from phids.engine.components.swarm import SwarmComponent
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld, Entity


def _is_swarm_anchored_jit(
    x: int,
    y: int,
    species_id: int,
    apparent_nutrition_val: float,
    plant_energy_by_species: npt.NDArray[np.float64],
    diet_matrix: npt.NDArray[np.bool_],
    caloric_intake: float = 0.0,
    metabolic_upkeep: float = 0.0,
) -> bool:
    """Numba-compiled fast collision check for swarm anchoring on compatible uneaten flora.

    Evaluates co-located plant energy layers using a pre-compiled boolean diet matrix,
    eliminating Python list iteration and NumPy `.item()` scalar conversion overhead.
    Includes Marginal Value Theorem (MVT) "Full Belly Override": if current caloric intake
    equals or exceeds metabolic upkeep, the swarm anchors regardless of apparent nutrition.

    Args:
        x: X-coordinate of the swarm.
        y: Y-coordinate of the swarm.
        species_id: Species identifier of the swarm.
        apparent_nutrition_val: Current apparent nutrition level at (x, y).
        plant_energy_by_species: 3D array of plant energy levels [num_flora_species, W, H].
        diet_matrix: 2D boolean array of diet compatibility [num_herbivore_species, num_flora_species].
        caloric_intake: Current caloric intake rate of the swarm (for MVT Full Belly Override).
        metabolic_upkeep: Baseline metabolic upkeep of the swarm (for MVT Full Belly Override).

    Returns:
        True if the swarm is co-located with compatible uneaten food or full belly; False otherwise.
    """
    # MVT Full Belly Override: if intake >= upkeep > 0, lock movement (swarm is anchored)
    if metabolic_upkeep > 0.0 and caloric_intake >= metabolic_upkeep:
        return True

    if apparent_nutrition_val < 0.999:
        return False
    num_herbivores, num_flora = diet_matrix.shape
    if species_id >= num_herbivores:
        return False
    for flora_species_id in range(num_flora):
        if diet_matrix[species_id, flora_species_id]:
            if plant_energy_by_species[flora_species_id, x, y] > 0.0:
                return True
    return False


def _is_swarm_anchored(
    swarm: SwarmComponent,
    env: GridEnvironment,
    diet_matrix: list[list[bool]] | npt.NDArray[np.bool_],
) -> bool:
    """Return True if swarm is currently co-located with compatible uneaten food or full belly.

    Numba JIT Anchoring Resolution & Array Scalar Extraction Avoidance:
    ------------------------------------------------------------------
    Evaluating herbivore anchoring via Python list iteration and dynamic NumPy `.item()` scalar calls
    on every movement tick induces interpreter overhead. Dispatching to `_is_swarm_anchored_jit`
    evaluates 3D species energy arrays and 2D boolean diet matrices in compiled C, eliminating
    object creation and scalar extraction overhead in the movement hot path.

    Args:
        swarm: The swarm component.
        env: The grid environment.
        diet_matrix: The boolean diet matrix (2D NumPy array or list of lists).

    Returns:
        True if the swarm is anchored, False otherwise.
    """
    intake = float(getattr(swarm, "last_caloric_intake", 0.0))
    upkeep = float(getattr(swarm, "metabolism_upkeep", 0.0))

    if isinstance(diet_matrix, np.ndarray):
        return _is_swarm_anchored_jit(
            swarm.x,
            swarm.y,
            swarm.species_id,
            float(env.apparent_nutrition_layer[swarm.x, swarm.y]),
            env.plant_energy_by_species,
            diet_matrix,
            caloric_intake=intake,
            metabolic_upkeep=upkeep,
        )

    diet_arr = np.array(diet_matrix, dtype=np.bool_)
    return _is_swarm_anchored_jit(
        swarm.x,
        swarm.y,
        swarm.species_id,
        float(env.apparent_nutrition_layer[swarm.x, swarm.y]),
        env.plant_energy_by_species,
        diet_arr,
        caloric_intake=intake,
        metabolic_upkeep=upkeep,
    )


def _calculate_toroidal_delta(n_coord: int, old_coord: int, size: int) -> int:
    """Calculate the shortest path delta across a toroidal boundary.

    Args:
        n_coord: The coordinate of the neighbour.
        old_coord: The coordinate of the current cell.
        size: The size of the grid environment.

    Returns:
        The shortest path delta across the toroidal boundary.
    """
    delta = n_coord - old_coord
    if delta > size // 2:
        delta -= size
    elif delta < -size // 2:
        delta += size
    return delta


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
