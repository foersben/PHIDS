# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Numba-compiled math kernels for movement logic for swarms in the interaction system."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from numba import njit

from phids.engine.systems.interaction.population import TILE_CARRYING_CAPACITY

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt

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
        if r <= cum:
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
        if r <= cum:
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
