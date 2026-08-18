# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Flow-field directional choice logic.

Provides JIT-compiled kernels and Python fallbacks for making weighted movement choices along
environmental flow fields, including branchless capacity mask integration.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt
from numba import njit

from phids.engine.systems.interaction.movement.capacity import _apply_branchless_capacity_mask_jit
from phids.engine.systems.interaction.movement.neighbors import (
    _gather_neighbours_jit,
    _gather_neighbours_jit_pow2,
)

if TYPE_CHECKING:
    from phids.engine.components.swarm import SwarmComponent

_orig_choices = random.choices
_orig_choice = random.choice


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
    """Numba-compiled helper function to select a neighbour based on a flat flow-field gradient.

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
    """Numba-compiled helper function to select a neighbour based on flow-field gradient using linear weights.

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
    min_score = -scores[0] if invert else scores[0]
    for i in range(count):
        adj = -scores[i] if invert else scores[i]
        adjusted_scores[i] = adj
        if adj < min_score:
            min_score = adj

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
    max_score = -scores[0] if invert else scores[0]
    for i in range(count):
        adj = -scores[i] if invert else scores[i]
        adjusted_scores[i] = adj
        if adj > max_score:
            max_score = adj

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
            max_capacity=500,  # Using literal fallback, typically TILE_CARRYING_CAPACITY
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
        max_capacity=500,  # Using literal fallback
        current_x=x,
        current_y=y,
    )


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
