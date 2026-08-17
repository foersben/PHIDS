# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Random Walk logic."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from phids.engine.systems.interaction.movement.neighbours import _gather_neighbours_jit, _gather_neighbours_jit_pow2

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt

_orig_choice = random.choice


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
