# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Neighbours logic."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt

    from phids.engine.components.swarm import SwarmComponent


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
