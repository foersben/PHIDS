# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Neighbor gathering logic for grid environments.

Provides JIT-compiled kernels for calculating toroidal deltas and gathering 4-connected neighbors.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from numba import njit

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt


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
