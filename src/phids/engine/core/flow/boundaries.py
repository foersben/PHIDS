# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Toroidal boundary update kernels and inner grid propagation for flow fields.

Provides boundary relaxations for standard modulo arithmetic as well as bitwise
power-of-2 fast paths.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from numba import njit

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt

from phids.engine.core.flow.stencils import _sum_neighbours_jit, _sum_neighbours_jit_pow2


@njit(cache=True, fastmath=True)
def _update_boundary_x_jit(
    x: int,
    width: int,
    height: int,
    decay: float,
    base: npt.NDArray[np.float64],
    current: npt.NDArray[np.float64],
    nxt: npt.NDArray[np.float64],
) -> float:
    """Update top and bottom boundaries for a given x-coordinate on standard grids.

    Args:
        x: The x-coordinate.
        width: The width of the grid.
        height: The height of the grid.
        decay: The decay rate.
        base: The base flow field.
        current: The current flow field.
        nxt: The next flow field.

    Returns:
        float: The maximum difference for this x-coordinate slice.
    """
    max_diff = 0.0
    n_sum, _ = _sum_neighbours_jit(x, 0, width, height, current)
    val = base[x, 0] + (decay * n_sum * 0.25)
    nxt[x, 0] = val
    diff1 = abs(val - current[x, 0])
    max_diff = max(max_diff, diff1)

    n_sum, _ = _sum_neighbours_jit(x, height - 1, width, height, current)
    val = base[x, height - 1] + (decay * n_sum * 0.25)
    nxt[x, height - 1] = val
    diff2 = abs(val - current[x, height - 1])
    max_diff = max(max_diff, diff2)
    return float(max_diff)


@njit(cache=True, fastmath=True)
def _update_boundary_y_jit(
    y: int,
    width: int,
    height: int,
    decay: float,
    base: npt.NDArray[np.float64],
    current: npt.NDArray[np.float64],
    nxt: npt.NDArray[np.float64],
) -> float:
    """Update left and right boundaries for a given y-coordinate on standard grids.

    Args:
        y: The y-coordinate.
        width: The width of the grid.
        height: The height of the grid.
        decay: The decay rate.
        base: The base flow field.
        current: The current flow field.
        nxt: The next flow field.

    Returns:
        float: The maximum difference for this y-coordinate slice.
    """
    max_diff = 0.0
    n_sum, _ = _sum_neighbours_jit(0, y, width, height, current)
    val = base[0, y] + (decay * n_sum * 0.25)
    nxt[0, y] = val
    diff1 = abs(val - current[0, y])
    max_diff = max(max_diff, diff1)

    n_sum, _ = _sum_neighbours_jit(width - 1, y, width, height, current)
    val = base[width - 1, y] + (decay * n_sum * 0.25)
    nxt[width - 1, y] = val
    diff2 = abs(val - current[width - 1, y])
    max_diff = max(max_diff, diff2)
    return float(max_diff)


@njit(cache=True, fastmath=True)
def _propagate_boundaries_jit(
    width: int,
    height: int,
    decay: float,
    base: npt.NDArray[np.float64],
    current: npt.NDArray[np.float64],
    nxt: npt.NDArray[np.float64],
) -> float:
    """Propagate the flow field along all toroidal outer boundaries.

    Args:
        width: The width of the grid environment.
        height: The height of the grid environment.
        decay: The decay rate.
        base: The base flow field.
        current: The current flow field.
        nxt: The next flow field.

    Returns:
        float: The maximum difference between the current and next flow fields.
    """
    max_diff = 0.0

    for x in range(width):
        d = _update_boundary_x_jit(x, width, height, decay, base, current, nxt)
        max_diff = max(max_diff, d)

    for y in range(1, height - 1):
        d = _update_boundary_y_jit(y, width, height, decay, base, current, nxt)
        max_diff = max(max_diff, d)

    return float(max_diff)


@njit(cache=True, fastmath=True)
def _update_boundary_x_jit_pow2(
    x: int,
    height: int,
    mask_x: int,
    mask_y: int,
    decay: float,
    base: npt.NDArray[np.float64],
    current: npt.NDArray[np.float64],
    nxt: npt.NDArray[np.float64],
) -> float:
    """Update top and bottom boundaries for a given x-coordinate using bitmasking.

    Args:
        x: The x-coordinate.
        height: The height of the grid.
        mask_x: Bitmask for width.
        mask_y: Bitmask for height.
        decay: The decay rate.
        base: The base flow field.
        current: The current flow field.
        nxt: The next flow field.

    Returns:
        float: Maximum difference encountered along the boundary slice.
    """
    max_diff = 0.0
    n_sum, _ = _sum_neighbours_jit_pow2(x, 0, mask_x, mask_y, current)
    val = base[x, 0] + (decay * n_sum * 0.25)
    nxt[x, 0] = val
    diff1 = abs(val - current[x, 0])
    max_diff = max(max_diff, diff1)

    n_sum, _ = _sum_neighbours_jit_pow2(x, height - 1, mask_x, mask_y, current)
    val = base[x, height - 1] + (decay * n_sum * 0.25)
    nxt[x, height - 1] = val
    diff2 = abs(val - current[x, height - 1])
    max_diff = max(max_diff, diff2)
    return float(max_diff)


@njit(cache=True, fastmath=True)
def _update_boundary_y_jit_pow2(
    y: int,
    width: int,
    mask_x: int,
    mask_y: int,
    decay: float,
    base: npt.NDArray[np.float64],
    current: npt.NDArray[np.float64],
    nxt: npt.NDArray[np.float64],
) -> float:
    """Update left and right boundaries for a given y-coordinate using bitmasking.

    Args:
        y: The y-coordinate.
        width: The width of the grid.
        mask_x: Bitmask for width.
        mask_y: Bitmask for height.
        decay: The decay rate.
        base: The base flow field.
        current: The current flow field.
        nxt: The next flow field.

    Returns:
        float: Maximum difference encountered along the boundary slice.
    """
    max_diff = 0.0
    n_sum, _ = _sum_neighbours_jit_pow2(0, y, mask_x, mask_y, current)
    val = base[0, y] + (decay * n_sum * 0.25)
    nxt[0, y] = val
    diff1 = abs(val - current[0, y])
    max_diff = max(max_diff, diff1)

    n_sum, _ = _sum_neighbours_jit_pow2(width - 1, y, mask_x, mask_y, current)
    val = base[width - 1, y] + (decay * n_sum * 0.25)
    nxt[width - 1, y] = val
    diff2 = abs(val - current[width - 1, y])
    max_diff = max(max_diff, diff2)
    return float(max_diff)


@njit(cache=True, fastmath=True)
def _propagate_boundaries_jit_pow2(
    width: int,
    height: int,
    mask_x: int,
    mask_y: int,
    decay: float,
    base: npt.NDArray[np.float64],
    current: npt.NDArray[np.float64],
    nxt: npt.NDArray[np.float64],
) -> float:
    """Propagate the flow field along all outer boundaries using bitmasking.

    Args:
        width: The width of the grid.
        height: The height of the grid.
        mask_x: Bitmask for width.
        mask_y: Bitmask for height.
        decay: The decay rate.
        base: The base flow field.
        current: The current flow field.
        nxt: The next flow field.

    Returns:
        float: Maximum difference along all boundaries.
    """
    max_diff = 0.0

    for x in range(width):
        d = _update_boundary_x_jit_pow2(x, height, mask_x, mask_y, decay, base, current, nxt)
        max_diff = max(max_diff, d)

    for y in range(1, height - 1):
        d = _update_boundary_y_jit_pow2(y, width, mask_x, mask_y, decay, base, current, nxt)
        max_diff = max(max_diff, d)

    return float(max_diff)


@njit(cache=True, fastmath=True)
def _propagate_inner_jit(
    width: int,
    height: int,
    decay: float,
    base: npt.NDArray[np.float64],
    current: npt.NDArray[np.float64],
    nxt: npt.NDArray[np.float64],
) -> float:
    """Propagate the flow field in the inner grid without boundary wrap branches.

    Args:
        width: The width of the grid environment.
        height: The height of the grid environment.
        decay: The decay rate.
        base: The base flow field.
        current: The current flow field.
        nxt: The next flow field.

    Returns:
        float: The maximum difference in the inner grid.
    """
    max_diff = 0.0
    for x in range(1, width - 1):
        for y in range(1, height - 1):
            n_sum = current[x - 1, y] + current[x + 1, y] + current[x, y - 1] + current[x, y + 1]
            propagated = n_sum * 0.25
            val = base[x, y] + (decay * propagated)
            nxt[x, y] = val
            diff = abs(val - current[x, y])
            max_diff = max(max_diff, diff)
    return float(max_diff)
