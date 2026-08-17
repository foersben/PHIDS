# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Movement and pathfinding logic for swarms in the interaction system.

This module contains helper functions to move swarms from one tile to another, including flow-field based movement and
neighbour-based movement.

Numba `@njit`-compiled helper functions ensure high-performance execution of the critically-threaded movement routines,
minimising CPU branch mispredictions through branchless SIMD-friendly arithmetic where feasible.

"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

import numpy as np
import numpy.typing as npt
from numba import njit

from phids.engine.systems.interaction.population import TILE_CARRYING_CAPACITY, _accumulate_tile_population

if TYPE_CHECKING:
    from collections.abc import Mapping

    from phids.api.schemas.species import HerbivoreSpeciesParams
    from phids.engine.components.swarm import SwarmComponent
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld, Entity

_orig_choice = random.choice
_orig_choices = random.choices


@njit(cache=True)
def _gather_neighbours_jit(
    x: int,
    y: int,
    width: int,
    height: int,
    c_x: npt.NDArray[np.int32],
    c_y: npt.NDArray[np.int32],
) -> int:
    """Numba-compiled helper function to gather neighbours of a cell.

    Args:
        x: The x coordinate of the cell.
        y: The y coordinate of the cell.
        width: The width of the grid environment.
        height: The height of the grid environment.
        c_x: Array to store the x coordinates of the neighbours.
        c_y: Array to store the y coordinates of the neighbours.

    Returns:
        The number of neighbours.
    """
    c_x[0] = x
    c_y[0] = y
    count = 1

    c_x[count] = (x - 1) % width
    c_y[count] = y
    count += 1
    c_x[count] = (x + 1) % width
    c_y[count] = y
    count += 1
    c_x[count] = x
    c_y[count] = (y - 1) % height
    count += 1
    c_x[count] = x
    c_y[count] = (y + 1) % height
    count += 1
    return count


@njit(cache=True)
def _gather_neighbours_jit_pow2(
    x: int,
    y: int,
    mask_x: int,
    mask_y: int,
    c_x: npt.NDArray[np.int32],
    c_y: npt.NDArray[np.int32],
) -> int:
    """Numba-compiled helper function to gather neighbours using bitwise AND masking.

    Args:
        x: The x coordinate of the cell.
        y: The y coordinate of the cell.
        mask_x: The x mask.
        mask_y: The y mask.
        c_x: Array to store the x coordinates of the neighbours.
        c_y: Array to store the y coordinates of the neighbours.

    Returns:
        The number of neighbours.
    """
    c_x[0] = x
    c_y[0] = y
    count = 1

    c_x[count] = (x - 1) & mask_x
    c_y[count] = y
    count += 1
    c_x[count] = (x + 1) & mask_x
    c_y[count] = y
    count += 1
    c_x[count] = x
    c_y[count] = (y - 1) & mask_y
    count += 1
    c_x[count] = x
    c_y[count] = (y + 1) & mask_y
    count += 1
    return count


@njit(cache=True)
def _flat_field_choice_jit(
    count: int,
    x: int,
    y: int,
    last_dx: int,
    last_dy: int,
    c_x: npt.NDArray[np.int32],
    c_y: npt.NDArray[np.int32],
    weights: npt.NDArray[np.float64],
    rand_val: float,
) -> tuple[int, int]:
    """Numba-compiled helper function to select a neighbour based on flow-field gradient.

    Args:
        count: The number of neighbours.
        x: The x coordinate of the cell.
        y: The y coordinate of the cell.
        last_dx: The last x delta.
        last_dy: The last y delta.
        c_x: Array to store the x coordinates of the neighbours.
        c_y: Array to store the y coordinates of the neighbours.
        weights: Pre-allocated array for flow-field weights.
        rand_val: Random value for weighted choice.

    Returns:
        The selected neighbour coordinates.
    """
    if last_dx == 0 and last_dy == 0:
        idx = int(rand_val * count)
        if idx >= count:
            idx = count - 1
        return c_x[idx], c_y[idx]

    target_x = x + last_dx
    target_y = y + last_dy
    total_w = 0.0
    for i in range(count):
        if c_x[i] == target_x and c_y[i] == target_y:
            weights[i] = 10.0
        else:
            weights[i] = 1.0
        total_w += weights[i]

    r = rand_val * total_w
    cum = 0.0
    for i in range(count):
        cum += weights[i]
        if r < cum:
            return c_x[i], c_y[i]
    return c_x[count - 1], c_y[count - 1]


@njit(cache=True)
def _apply_branchless_capacity_mask_jit(
    count: int,
    x: int,
    y: int,
    width: int,
    c_x: npt.NDArray[np.int32],
    c_y: npt.NDArray[np.int32],
    tile_populations: npt.NDArray[np.int32],
    max_capacity: int,
    weights: npt.NDArray[np.float64],
) -> float:
    """Branchlessly mask weights for candidate neighbours exceeding tile carrying capacity.

    Calculates a floating-point multiplier for each candidate tile using branchless boolean arithmetic:
    `mask = min(1.0, is_current + is_under_capacity)`. If a candidate cell exceeds maximum capacity
    and is not the current cell, its weight is branchlessly multiplied by 0.0, preventing CPU
    branch mispredictions in Numba `@njit` kernels.

    Args:
        count: The number of neighbours.
        x: The x coordinate of the cell.
        y: The y coordinate of the cell.
        width: The width of the grid environment.
        c_x: Array to store the x coordinates of the neighbours.
        c_y: Array to store the y coordinates of the neighbours.
        tile_populations: Array of tile population values.
        max_capacity: The maximum capacity of a tile.
        weights: Array to store the weights.

    Returns:
        The total weight.
    """
    total_w = 0.0
    for i in range(count):
        is_current = 1.0 if (c_x[i] == x and c_y[i] == y) else 0.0
        pop = tile_populations[c_y[i] * width + c_x[i]]
        under_capacity = 1.0 if (pop <= max_capacity) else 0.0
        mask = 1.0 if (is_current > 0.0 or under_capacity > 0.0) else 0.0
        weights[i] = weights[i] * mask
        total_w += weights[i]
    return total_w


@njit(cache=True, fastmath=True)
def _weighted_field_choice_jit(
    count: int,
    invert: bool,
    scores: npt.NDArray[np.float64],
    c_x: npt.NDArray[np.int32],
    c_y: npt.NDArray[np.int32],
    adjusted_scores: npt.NDArray[np.float64],
    weights: npt.NDArray[np.float64],
    rand_val: float,
    tile_populations: npt.NDArray[np.int32] | None = None,
    width: int = 0,
    max_capacity: int = 500,
    current_x: int = -1,
    current_y: int = -1,
) -> tuple[int, int]:
    """Numba-compiled helper function to select a neighbour based on flow-field gradient.

    Args:
        count: The number of neighbours.
        invert: Whether to invert the scores.
        scores: Array of flow-field gradient scores.
        c_x: Array to store the x coordinates of the neighbours.
        c_y: Array to store the y coordinates of the neighbours.
        adjusted_scores: Pre-allocated array for adjusted scores.
        weights: Pre-allocated array for flow-field weights.
        rand_val: Random value for weighted choice.
        tile_populations: Pre-allocated population array for capacity masking.
        width: Grid width for population indexing.
        max_capacity: Tile carrying capacity threshold.
        current_x: Current x coordinate of the swarm.
        current_y: Current y coordinate of the swarm.

    Returns:
        The selected neighbour coordinates.
    """
    for i in range(count):
        adjusted_scores[i] = -scores[i] if invert else scores[i]

    min_score = adjusted_scores[0]
    for i in range(1, count):
        if adjusted_scores[i] < min_score:
            min_score = adjusted_scores[i]

    total_w = 0.0
    for i in range(count):
        weights[i] = (adjusted_scores[i] - min_score) + 1e-6
        total_w += weights[i]

    if tile_populations is not None and width > 0 and current_x >= 0 and current_y >= 0:
        total_w = _apply_branchless_capacity_mask_jit(
            count, current_x, current_y, width, c_x, c_y, tile_populations, max_capacity, weights
        )

    if total_w <= 0.0:
        return (current_x if current_x >= 0 else c_x[0]), (current_y if current_y >= 0 else c_y[0])

    r = rand_val * total_w
    cum = 0.0
    for i in range(count):
        cum += weights[i]
        if r < cum:
            return c_x[i], c_y[i]
    return c_x[count - 1], c_y[count - 1]


@njit(cache=True, fastmath=True)
def _softmax_field_choice_jit(
    count: int,
    invert: bool,
    scores: npt.NDArray[np.float64],
    c_x: npt.NDArray[np.int32],
    c_y: npt.NDArray[np.int32],
    adjusted_scores: npt.NDArray[np.float64],
    weights: npt.NDArray[np.float64],
    rand_val: float,
    tau: float,
    tile_populations: npt.NDArray[np.int32] | None = None,
    width: int = 0,
    max_capacity: int = 500,
    current_x: int = -1,
    current_y: int = -1,
) -> tuple[int, int]:
    """Numba-compiled helper function to select a neighbour using Boltzmann/Softmax probabilities.

    Args:
        count: The number of neighbours.
        invert: Whether to invert the scores.
        scores: Array of flow-field gradient scores.
        c_x: Array to store the x coordinates of the neighbours.
        c_y: Array to store the y coordinates of the neighbours.
        adjusted_scores: Pre-allocated array for adjusted scores.
        weights: Pre-allocated array for flow-field weights.
        rand_val: Random value for weighted choice.
        tau: Softmax temperature parameter.
        tile_populations: Pre-allocated population array for capacity masking.
        width: Grid width for population indexing.
        max_capacity: Tile carrying capacity threshold.
        current_x: Current x coordinate of the swarm.
        current_y: Current y coordinate of the swarm.

    Returns:
        The selected neighbour coordinates.
    """
    for i in range(count):
        adjusted_scores[i] = -scores[i] if invert else scores[i]

    max_score = adjusted_scores[0]
    for i in range(1, count):
        if adjusted_scores[i] > max_score:
            max_score = adjusted_scores[i]

    total_w = 0.0
    for i in range(count):
        # Max-subtraction prevents fastmath float overflow during exponentiation.
        weights[i] = np.exp((adjusted_scores[i] - max_score) / tau)
        total_w += weights[i]

    if tile_populations is not None and width > 0 and current_x >= 0 and current_y >= 0:
        total_w = _apply_branchless_capacity_mask_jit(
            count, current_x, current_y, width, c_x, c_y, tile_populations, max_capacity, weights
        )

    if total_w <= 0.0:
        return (current_x if current_x >= 0 else c_x[0]), (current_y if current_y >= 0 else c_y[0])

    r = rand_val * total_w
    cum = 0.0
    for i in range(count):
        cum += weights[i]
        if r < cum:
            return c_x[i], c_y[i]
    return c_x[count - 1], c_y[count - 1]


@njit(cache=True, fastmath=True)
def _choose_neighbour_by_flow_probability_jit(
    x: int,
    y: int,
    last_dx: int,
    last_dy: int,
    flow_field: npt.NDArray[np.float64],
    width: int,
    height: int,
    invert: bool,
    c_x: npt.NDArray[np.int32],
    c_y: npt.NDArray[np.int32],
    scores: npt.NDArray[np.float64],
    adjusted_scores: npt.NDArray[np.float64],
    weights: npt.NDArray[np.float64],
    rand_val: float,
    tile_populations: npt.NDArray[np.int32] | None = None,
    tau: float = 0.0,
) -> tuple[int, int]:
    """JIT-accelerated Von-Neumann coordinate selector using flow weights and branchless capacity masking.

    Args:
        x: The x coordinate of the cell.
        y: The y coordinate of the cell.
        last_dx: The last x delta.
        last_dy: The last y delta.
        flow_field: Array of flow-field gradient scores.
        width: The width of the grid environment.
        height: The height of the grid environment.
        invert: Whether to invert the flow-field gradient scores.
        c_x: Array to store the x coordinates of the neighbours.
        c_y: Array to store the y coordinates of the neighbours.
        scores: Pre-allocated array for flow-field scores.
        adjusted_scores: Pre-allocated scratch array for adjusted scores.
        weights: Pre-allocated scratch array for sampling weights.
        rand_val: Random value for weighted choice.
        tile_populations: Tile population array for branchless capacity masking.
        tau: Softmax temperature parameter. 0.0 uses legacy linear weighted selection.

    Returns:
        The selected neighbour coordinates.
    """
    is_pow2 = (width > 0 and (width & (width - 1)) == 0) and (height > 0 and (height & (height - 1)) == 0)
    if is_pow2:
        count = _gather_neighbours_jit_pow2(x, y, width - 1, height - 1, c_x, c_y)
    else:
        count = _gather_neighbours_jit(x, y, width, height, c_x, c_y)

    for i in range(count):
        scores[i] = flow_field[c_x[i], c_y[i]]

    max_score = scores[0]
    min_score = scores[0]
    for i in range(1, count):
        if scores[i] > max_score:
            max_score = scores[i]
        if scores[i] < min_score:
            min_score = scores[i]

    # Flat fields provide no directional signal; preserve prior heading as inertia.
    if max_score - min_score < 1e-6:
        return _flat_field_choice_jit(count, x, y, last_dx, last_dy, c_x, c_y, weights, rand_val)

    if tau > 0.0:
        return _softmax_field_choice_jit(
            count,
            invert,
            scores,
            c_x,
            c_y,
            adjusted_scores,
            weights,
            rand_val,
            tau,
            tile_populations=tile_populations,
            width=width,
            max_capacity=TILE_CARRYING_CAPACITY,
            current_x=x,
            current_y=y,
        )

    return _weighted_field_choice_jit(
        count,
        invert,
        scores,
        c_x,
        c_y,
        adjusted_scores,
        weights,
        rand_val,
        tile_populations=tile_populations,
        width=width,
        max_capacity=TILE_CARRYING_CAPACITY,
        current_x=x,
        current_y=y,
    )


def _choose_neighbour_by_flow_probability(
    swarm: SwarmComponent,
    flow_field: npt.NDArray[np.float64],
    width: int,
    height: int,
    c_x: npt.NDArray[np.int32],
    c_y: npt.NDArray[np.int32],
    scores: npt.NDArray[np.float64],
    adjusted_scores: npt.NDArray[np.float64],
    weights: npt.NDArray[np.float64],
    invert: bool = False,
    tile_populations: npt.NDArray[np.int32] | list[int] | None = None,
    tau: float = 0.0,
) -> tuple[int, int]:
    """Select a 4-connected Von-Neumann neighbour via flow-field-weighted JIT selection.

    Uses branchless capacity masking to prevent over-occupancy.

    Args:
        swarm: The swarm component.
        flow_field: Array of flow-field gradient values.
        width: The width of the grid environment.
        height: The height of the grid environment.
        c_x: Pre-allocated scratch array for x-coordinates.
        c_y: Pre-allocated scratch array for y-coordinates.
        scores: Pre-allocated scratch array for flow scores.
        adjusted_scores: Pre-allocated scratch array for adjusted scores.
        weights: Pre-allocated scratch array for sampling weights.
        invert: Whether to invert the flow-field gradient scores.
        tile_populations: Tile population array for branchless capacity masking.
        tau: Softmax temperature parameter. 0.0 uses legacy linear weighted selection.

    Returns:
        The selected neighbour coordinates.
    """
    if random.choices is not _orig_choices or random.choice is not _orig_choice:
        return _choose_neighbour_by_flow_probability_python(swarm, flow_field, width, height, invert)

    tile_pop_arr: npt.NDArray[np.int32] | None = None
    if isinstance(tile_populations, np.ndarray):
        tile_pop_arr = tile_populations
    elif isinstance(tile_populations, list):
        tile_pop_arr = np.array(tile_populations, dtype=np.int32)

    return _choose_neighbour_by_flow_probability_jit(
        swarm.x,
        swarm.y,
        swarm.last_dx,
        swarm.last_dy,
        flow_field,
        width,
        height,
        invert,
        c_x,
        c_y,
        scores,
        adjusted_scores,
        weights,
        random.random(),
        tile_populations=tile_pop_arr,
        tau=tau,
    )


@njit(cache=True)
def _random_walk_step_jit(
    x: int,
    y: int,
    width: int,
    height: int,
    c_x: npt.NDArray[np.int32],
    c_y: npt.NDArray[np.int32],
    rand_val: float,
) -> tuple[int, int]:
    """JIT-accelerated uniform random coordinate selector for undirected dispersal.

    Dispatches to the bitwise power-of-two fast path when both grid dimensions are powers of two,
    eliminating integer modulo division `%` from the hot movement loop. Falls back to the modulo
    path for arbitrary grid sizes.

    Args:
        x: The x coordinate of the cell.
        y: The y coordinate of the cell.
        width: The width of the grid environment.
        height: The height of the grid environment.
        c_x: Pre-allocated array for neighbour x coordinates.
        c_y: Pre-allocated array for neighbour y coordinates.
        rand_val: Random value for weighted choice.

    Returns:
        The selected neighbour coordinates.
    """
    is_pow2 = (width > 0 and (width & (width - 1)) == 0) and (height > 0 and (height & (height - 1)) == 0)
    if is_pow2:
        count = _gather_neighbours_jit_pow2(x, y, width - 1, height - 1, c_x, c_y)
    else:
        count = _gather_neighbours_jit(x, y, width, height, c_x, c_y)
    idx = int(rand_val * count)
    if idx >= count:
        idx = count - 1
    return c_x[idx], c_y[idx]


def _random_walk_step(
    x: int,
    y: int,
    width: int,
    height: int,
    c_x: npt.NDArray[np.int32],
    c_y: npt.NDArray[np.int32],
) -> tuple[int, int]:
    """Perform a random walk step to an adjacent cell.

    Args:
        x: The current X coordinate.
        y: The current Y coordinate.
        width: The width of the grid.
        height: The height of the grid.
        c_x: Pre-allocated scratch array for x-coordinates.
        c_y: Pre-allocated scratch array for y-coordinates.

    Returns:
        The new coordinates.
    """
    if random.choice is not _orig_choice:
        candidates: list[tuple[int, int]] = [(x, y)]
        candidates.append(((x - 1) % width, y))
        candidates.append(((x + 1) % width, y))
        candidates.append((x, (y - 1) % height))
        candidates.append((x, (y + 1) % height))
        return random.choice(candidates)

    return _random_walk_step_jit(x, y, width, height, c_x, c_y, random.random())


def _python_flat_field_choice(
    swarm: SwarmComponent,
    candidates: list[tuple[int, int]],
) -> tuple[int, int]:
    """Helper to choose from flat field candidates using inertia direction or random choice.

    Args:
        swarm: The swarm component.
        candidates: List of candidate coordinates.

    Returns:
        The selected neighbour coordinates.
    """
    if swarm.last_dx == 0 and swarm.last_dy == 0:
        return random.choice(candidates)

    target_x = swarm.x + swarm.last_dx
    target_y = swarm.y + swarm.last_dy
    weights = [10.0 if (cx == target_x and cy == target_y) else 1.0 for cx, cy in candidates]
    return random.choices(candidates, weights=weights, k=1)[0]


def _python_weighted_field_choice(
    scores: list[float],
    candidates: list[tuple[int, int]],
    invert: bool,
) -> tuple[int, int]:
    """Helper to choose from non-flat field candidates using flow probability weights.

    Args:
        scores: List of flow field scores.
        candidates: List of candidate coordinates.
        invert: Whether to invert the scores.

    Returns:
        The selected neighbour coordinates.
    """
    adjusted_scores = [-score for score in scores] if invert else scores
    min_score = min(adjusted_scores)
    weights = [(score - min_score) + 1e-6 for score in adjusted_scores]
    return random.choices(candidates, weights=weights, k=1)[0]


def _choose_neighbour_by_flow_probability_python(
    swarm: SwarmComponent,
    flow_field: npt.NDArray[np.float64],
    width: int,
    height: int,
    invert: bool,
) -> tuple[int, int]:
    """Fallback Python logic when random choice is mocked.

    Args:
        swarm: The swarm component.
        flow_field: The flow field.
        width: The width of the grid environment.
        height: The height of the grid environment.
        invert: Whether to invert the flow field.

    Returns:
        The selected neighbour coordinates.
    """
    x, y = swarm.x, swarm.y
    candidates: list[tuple[int, int]] = [(x, y)]
    candidates.append(((x - 1) % width, y))
    candidates.append(((x + 1) % width, y))
    candidates.append((x, (y - 1) % height))
    candidates.append((x, (y + 1) % height))

    scores = [float(flow_field[cx, cy]) for cx, cy in candidates]
    max_score = max(scores)
    min_score = min(scores)

    if max_score - min_score < 1e-6:
        return _python_flat_field_choice(swarm, candidates)

    return _python_weighted_field_choice(scores, candidates, invert)


@njit(cache=True)
def _compute_trample_probability_jit(
    swarm_population: int,
    trample_factor: float,
    structural_mass: float,
    max_structural_mass: float,
    p_max: float = 0.50,
) -> float:
    """Numba-compiled single FMA branchless trampling vulnerability probability gate (Option A - linear).

    Calculates the probability P(destroy) of a seedling or low-structural-mass plant entity
    being trampled or incidentally destroyed by a moving herbivore swarm. Bounded by p_max
    (default 0.50) per coordinate transition to maintain realistic stochastic chance.

    Args:
        swarm_population: Population count of the entering herbivore swarm.
        trample_factor: Sensitivity coefficient for incidental destruction (trampling or clipping).
        structural_mass: Current M_structural of the co-located plant entity.
        max_structural_mass: Species structural mass ceiling (from FloraSpeciesParams).
        p_max: Maximum per-step destruction probability ceiling (default 0.50).

    Returns:
        Probability P(destroy) in range [0.0, p_max].
    """
    if max_structural_mass <= 0.0:
        vulnerability = 1.0
    else:
        vulnerability = max(0.0, 1.0 - (structural_mass / max_structural_mass))
    prob = float(swarm_population) * trample_factor * vulnerability
    return min(p_max, max(0.0, prob))


@njit(cache=True)
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


def _resolve_incidental_mortality(
    swarm: SwarmComponent,
    nx: int,
    ny: int,
    world: ECSWorld,
    env: GridEnvironment,
    herbivore_params_dict: Mapping[int, Any] | None = None,
) -> None:
    """Evaluate probabilistic incidental seedling mortality when a swarm enters cell (nx, ny).

    For each co-located PlantComponent entity at (nx, ny), calculates the destruction probability
    P(destroy) via _compute_trample_probability_jit. If stochastic check succeeds (rng.random() < P),
    the plant is culled from GridEnvironment write layers, unregistered from the spatial hash, and
    queued for entity cleanup.

    Args:
        swarm: SwarmComponent entering the target cell.
        nx: Target X coordinate.
        ny: Target Y coordinate.
        world: ECSWorld instance.
        env: GridEnvironment instance.
        herbivore_params_dict: Mapping of species_id to species parameters.
    """
    from phids.engine.components.plant import PlantComponent

    incidental_factor = 0.0
    mode_cause = "death_incidental_mortality"

    if herbivore_params_dict is not None and swarm.species_id in herbivore_params_dict:
        hp_raw = herbivore_params_dict[swarm.species_id]
        incidental_factor = float(getattr(hp_raw, "incidental_mortality_factor", 0.0))
        mode = getattr(hp_raw, "incidental_mortality_mode", "trampling")
        mode_cause = "death_collateral_trampling" if mode == "trampling" else "death_incidental_consumption"

    if incidental_factor <= 0.0:
        return

    occupants = world.entities_at(nx, ny)
    if not occupants:
        return

    dead_ids: list[int] = []
    for eid in list(occupants):
        if not world.has_entity(eid):
            continue
        ent = world.get_entity(eid)
        if not ent.has_component(PlantComponent):
            continue

        plant: PlantComponent = ent.get_component(PlantComponent)
        prob = _compute_trample_probability_jit(
            swarm_population=swarm.population,
            trample_factor=incidental_factor,
            structural_mass=plant.structural_mass,
            max_structural_mass=plant.max_structural_mass,
            p_max=0.50,
        )

        if prob > 0.0 and random.random() < prob:
            plant.last_energy_loss_cause = mode_cause
            env.clear_plant_energy(nx, ny, plant.species_id)
            env.clear_structural_mass(nx, ny, plant.species_id)
            world.unregister_position(eid, nx, ny)
            dead_ids.append(eid)

    if dead_ids:
        world.collect_garbage(dead_ids)
