# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Finite difference stencils and initialization kernels for flow fields.

Provides Numba @njit kernels for base attraction/repulsion matrix initialization,
4-point toroidal neighbour summation, and subnormal float zeroing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from numba import njit

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt


@njit(cache=True)
def _init_base_and_current_jit(
    width: int,
    height: int,
    plant_energy: npt.NDArray[np.float64],
    apparent_nutrition_layer: npt.NDArray[np.float64],
    toxin_layers: npt.NDArray[np.float64],
    base: npt.NDArray[np.float64],
    current: npt.NDArray[np.float64],
    alpha: float,
    beta: float,
) -> None:
    """Initialize base and current attraction flow fields using SIMD-vectorized matrix math.

    Args:
        width: Grid width.
        height: Grid height.
        plant_energy: 2D array of plant energy per cell.
        apparent_nutrition_layer: 2D array of apparent nutrition multipliers per cell.
        toxin_layers: 3D array of toxin concentration layers per cell.
        base: Pre-allocated 2D array for base flow field.
        current: Pre-allocated 2D array for current flow field.
        alpha: Weight for botanical attractants.
        beta: Weight for toxic repellents.
    """
    num_toxins = toxin_layers.shape[0]

    for x in range(width):
        for y in range(height):
            base[x, y] = alpha * plant_energy[x, y] * apparent_nutrition_layer[x, y]

    for t in range(num_toxins):
        for x in range(width):
            for y in range(height):
                base[x, y] -= beta * toxin_layers[t, x, y]

    for x in range(width):
        for y in range(height):
            current[x, y] = base[x, y]


@njit(cache=True, fastmath=True)
def _sum_neighbours_jit(
    x: int,
    y: int,
    width: int,
    height: int,
    current: npt.NDArray[np.float64],
) -> tuple[float, int]:
    """Helper function to sum the neighbours of a cell on a standard toroidal grid.

    Args:
        x: The x-coordinate of the cell.
        y: The y-coordinate of the cell.
        width: The width of the grid environment.
        height: The height of the grid environment.
        current: The current flow field.

    Returns:
        tuple[float, int]: Sum of the 4 cardinal neighbours and the count (always 4).
    """
    neighbours_sum = (
        current[(x - 1) % width, y]
        + current[(x + 1) % width, y]
        + current[x, (y - 1) % height]
        + current[x, (y + 1) % height]
    )
    return neighbours_sum, 4


@njit(cache=True, fastmath=True)
def _sum_neighbours_jit_pow2(
    x: int,
    y: int,
    mask_x: int,
    mask_y: int,
    current: npt.NDArray[np.float64],
) -> tuple[float, int]:
    """Helper function to sum the neighbours of a cell using bitwise AND masking.

    Args:
        x: The x-coordinate of the cell.
        y: The y-coordinate of the cell.
        mask_x: Bitmask for width (width - 1).
        mask_y: Bitmask for height (height - 1).
        current: The current flow field.

    Returns:
        tuple[float, int]: Sum of the 4 cardinal neighbours and the count (always 4).
    """
    neighbours_sum = (
        current[(x - 1) & mask_x, y]
        + current[(x + 1) & mask_x, y]
        + current[x, (y - 1) & mask_y]
        + current[x, (y + 1) & mask_y]
    )
    return neighbours_sum, 4


@njit(cache=True, fastmath=True)
def _truncate_subnormals_jit(
    width: int,
    height: int,
    current: npt.NDArray[np.float64],
    threshold: float,
) -> None:
    """Helper function to truncate subnormal floats to exactly zero in-place.

    Args:
        width: The width of the grid environment.
        height: The height of the grid environment.
        current: The current flow field.
        threshold: Subnormal truncation threshold below which values are zeroed.
    """
    for x in range(width):
        for y in range(height):
            val = current[x, y]
            current[x, y] = 0.0 if abs(val) < threshold else val
