# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Capacity masking logic for movement.

Provides JIT-compiled kernels for branchlessly filtering candidate neighbors based on population limits.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from numba import njit

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt


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
