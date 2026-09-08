# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Iterative Jacobi relaxation solvers and camouflage attenuation for flow fields.

Provides multi-threaded OpenMP parallel solvers, power-of-2 fast paths, and the public
entry points :func:`compute_flow_field` and :func:`apply_camouflage`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import numpy as np
import numpy.typing as npt
from numba import njit

if TYPE_CHECKING:
    prange = range
else:
    from numba import prange

from phids.engine.core.flow.boundaries import _propagate_boundaries_jit, _propagate_inner_jit
from phids.engine.core.flow.stencils import (
    _init_base_and_current_jit,
    _truncate_subnormals_jit,
)

NUMBA_PARALLEL_THRESHOLD_CELLS: Final[int] = 128 * 128


@njit(cache=True, fastmath=True)
def _propagate_iteration_jit(
    width: int,
    height: int,
    decay: float,
    base: npt.NDArray[np.float64],
    current: npt.NDArray[np.float64],
    nxt: npt.NDArray[np.float64],
) -> float:
    """Perform one iteration of the Jacobi relaxation across the full grid.

    Args:
        width: The width of the grid environment.
        height: The height of the grid environment.
        decay: The decay rate.
        base: The base flow field.
        current: The current flow field.
        nxt: The next flow field.

    Returns:
        float: The maximum difference between current and next fields.
    """
    max_diff = 0.0
    for x in range(width):
        for y in range(height):
            neighbours_sum = (
                current[(x - 1) % width, y]
                + current[(x + 1) % width, y]
                + current[x, (y - 1) % height]
                + current[x, (y + 1) % height]
            )
            val = base[x, y] + (decay * neighbours_sum * 0.25)
            nxt[x, y] = val

            diff = abs(val - current[x, y])
            max_diff = max(max_diff, diff)
    return max_diff


@njit(cache=True, fastmath=True)
def _propagate_iteration_jit_pow2(
    width: int,
    height: int,
    mask_x: int,
    mask_y: int,
    decay: float,
    base: npt.NDArray[np.float64],
    current: npt.NDArray[np.float64],
    nxt: npt.NDArray[np.float64],
) -> float:
    """Perform one iteration of Jacobi relaxation using bitwise AND masking.

    Args:
        width: The width of the grid environment.
        height: The height of the grid environment.
        mask_x: Bitwise mask for width (width - 1).
        mask_y: Bitwise mask for height (height - 1).
        decay: The decay rate.
        base: The base flow field.
        current: The current flow field.
        nxt: The next flow field.

    Returns:
        float: The maximum difference between current and next fields.
    """
    max_diff = 0.0
    for x in range(width):
        for y in range(height):
            neighbours_sum = (
                current[(x - 1) & mask_x, y]
                + current[(x + 1) & mask_x, y]
                + current[x, (y - 1) & mask_y]
                + current[x, (y + 1) & mask_y]
            )
            val = base[x, y] + (decay * neighbours_sum * 0.25)
            nxt[x, y] = val

            diff = abs(val - current[x, y])
            max_diff = max(max_diff, diff)
    return max_diff


@njit(parallel=True, cache=True, fastmath=True)
def _propagate_iteration_jit_parallel(
    width: int,
    height: int,
    decay: float,
    base: npt.NDArray[np.float64],
    current: npt.NDArray[np.float64],
    nxt: npt.NDArray[np.float64],
) -> float:
    """Perform one multi-threaded OpenMP iteration of Jacobi relaxation.

    Args:
        width: Grid width.
        height: Grid height.
        decay: Decay factor.
        base: Base flow field.
        current: Current flow field.
        nxt: Next write buffer.

    Returns:
        float: Maximum difference between iterations.
    """
    max_diff = 0.0
    for x in prange(width):
        for y in range(height):
            neighbours_sum = (
                current[(x - 1) % width, y]
                + current[(x + 1) % width, y]
                + current[x, (y - 1) % height]
                + current[x, (y + 1) % height]
            )
            val = base[x, y] + (decay * neighbours_sum * 0.25)
            nxt[x, y] = val

            diff = abs(val - current[x, y])
            max_diff = max(max_diff, diff)
    return max_diff


@njit(parallel=True, cache=True, fastmath=True)
def _propagate_iteration_jit_pow2_parallel(
    width: int,
    height: int,
    mask_x: int,
    mask_y: int,
    decay: float,
    base: npt.NDArray[np.float64],
    current: npt.NDArray[np.float64],
    nxt: npt.NDArray[np.float64],
) -> float:
    """Perform one multi-threaded OpenMP iteration of bitwise Jacobi relaxation.

    Args:
        width: Grid width.
        height: Grid height.
        mask_x: Bitwise mask for width.
        mask_y: Bitwise mask for height.
        decay: Decay factor.
        base: Base flow field.
        current: Current flow field.
        nxt: Next write buffer.

    Returns:
        float: Maximum difference between iterations.
    """
    max_diff = 0.0
    for x in prange(width):
        for y in range(height):
            neighbours_sum = (
                current[(x - 1) & mask_x, y]
                + current[(x + 1) & mask_x, y]
                + current[x, (y - 1) & mask_y]
                + current[x, (y + 1) & mask_y]
            )
            val = base[x, y] + (decay * neighbours_sum * 0.25)
            nxt[x, y] = val

            diff = abs(val - current[x, y])
            max_diff = max(max_diff, diff)
    return max_diff


@njit(cache=True)
def _run_pow2_parallel(
    width: int,
    height: int,
    max_iterations: int,
    mask_x: int,
    mask_y: int,
    decay: float,
    base: npt.NDArray[np.float64],
    current: npt.NDArray[np.float64],
    nxt: npt.NDArray[np.float64],
    truncate_threshold: float,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Run iterative relaxation for power-of-2 grids using parallel OpenMP."""
    for _ in range(max_iterations):
        max_diff = _propagate_iteration_jit_pow2_parallel(width, height, mask_x, mask_y, decay, base, current, nxt)
        current, nxt = nxt, current
        if max_diff < truncate_threshold:
            break
    return current, nxt


@njit(cache=True)
def _run_pow2_serial(
    width: int,
    height: int,
    max_iterations: int,
    mask_x: int,
    mask_y: int,
    decay: float,
    base: npt.NDArray[np.float64],
    current: npt.NDArray[np.float64],
    nxt: npt.NDArray[np.float64],
    truncate_threshold: float,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Run iterative relaxation for power-of-2 grids serially."""
    for _ in range(max_iterations):
        max_diff = _propagate_iteration_jit_pow2(width, height, mask_x, mask_y, decay, base, current, nxt)
        current, nxt = nxt, current
        if max_diff < truncate_threshold:
            break
    return current, nxt


@njit(cache=True)
def _run_standard_parallel(
    width: int,
    height: int,
    max_iterations: int,
    decay: float,
    base: npt.NDArray[np.float64],
    current: npt.NDArray[np.float64],
    nxt: npt.NDArray[np.float64],
    truncate_threshold: float,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Run iterative relaxation for arbitrary grid sizes using parallel OpenMP."""
    for _ in range(max_iterations):
        max_diff = _propagate_iteration_jit_parallel(width, height, decay, base, current, nxt)
        current, nxt = nxt, current
        if max_diff < truncate_threshold:
            break
    return current, nxt


@njit(cache=True)
def _run_standard_serial(
    width: int,
    height: int,
    max_iterations: int,
    decay: float,
    base: npt.NDArray[np.float64],
    current: npt.NDArray[np.float64],
    nxt: npt.NDArray[np.float64],
    truncate_threshold: float,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Run iterative relaxation for arbitrary grid sizes serially."""
    for _ in range(max_iterations):
        diff_boundaries = _propagate_boundaries_jit(width, height, decay, base, current, nxt)
        diff_inner = _propagate_inner_jit(width, height, decay, base, current, nxt)
        max_diff = max(diff_boundaries, diff_inner)
        current, nxt = nxt, current
        if max_diff < truncate_threshold:
            break
    return current, nxt


def _compute_flow_field_impl(
    plant_energy: npt.NDArray[np.float64],
    apparent_nutrition_layer: npt.NDArray[np.float64],
    toxin_layers: npt.NDArray[np.float64],
    width: int,
    height: int,
    base: npt.NDArray[np.float64],
    current: npt.NDArray[np.float64],
    nxt: npt.NDArray[np.float64],
    alpha: float,
    beta: float,
    decay: float,
    truncate_threshold: float,
) -> npt.NDArray[np.float64]:
    """Execute iterative relaxation propagation to generate a navigation grid.

    Args:
        plant_energy: Array of plant energy per cell.
        apparent_nutrition_layer: Array of apparent nutrition multipliers per cell.
        toxin_layers: Array of toxin concentration layers per cell.
        width: The width of the grid environment.
        height: The height of the grid environment.
        base: Pre-allocated array for base flow field.
        current: Pre-allocated array for current flow field.
        nxt: Pre-allocated array for next flow field.
        alpha: Attractant weight.
        beta: Repellent weight.
        decay: Decay factor.
        truncate_threshold: Truncation threshold.

    Returns:
        npt.NDArray[np.float64]: Scalar attraction field of shape ``(W, H)``.
    """
    base.fill(0.0)
    current.fill(0.0)
    nxt.fill(0.0)

    _init_base_and_current_jit(
        width, height, plant_energy, apparent_nutrition_layer, toxin_layers, base, current, alpha, beta
    )

    max_iterations = width + height
    is_pow2 = (width > 0 and (width & (width - 1)) == 0) and (height > 0 and (height & (height - 1)) == 0)
    mask_x = width - 1
    mask_y = height - 1
    use_parallel = width * height >= NUMBA_PARALLEL_THRESHOLD_CELLS

    if is_pow2:
        if use_parallel:
            current, nxt = _run_pow2_parallel(
                width, height, max_iterations, mask_x, mask_y, decay, base, current, nxt, truncate_threshold
            )
        else:
            current, nxt = _run_pow2_serial(
                width, height, max_iterations, mask_x, mask_y, decay, base, current, nxt, truncate_threshold
            )
    else:
        if use_parallel:
            current, nxt = _run_standard_parallel(
                width, height, max_iterations, decay, base, current, nxt, truncate_threshold
            )
        else:
            current, nxt = _run_standard_serial(
                width, height, max_iterations, decay, base, current, nxt, truncate_threshold
            )

    _truncate_subnormals_jit(width, height, current, truncate_threshold)

    return current


_compute_flow_field = njit(cache=True)(_compute_flow_field_impl)


def compute_flow_field(
    plant_energy: npt.NDArray[np.float64],
    apparent_nutrition_layer: npt.NDArray[np.float64],
    toxin_layers: npt.NDArray[np.float64],
    width: int,
    height: int,
    base: npt.NDArray[np.float64] | None = None,
    current: npt.NDArray[np.float64] | None = None,
    nxt: npt.NDArray[np.float64] | None = None,
    alpha: float = 1.0,
    beta: float = 1.0,
    decay: float = 0.6,
    truncate_threshold: float = 1e-4,
) -> npt.NDArray[np.float64]:
    """Public wrapper: sum toxin layers and delegate to the Numba kernel.

    Args:
        plant_energy: Shape ``(W, H)`` aggregate plant energy.
        apparent_nutrition_layer: Shape ``(W, H)`` apparent nutrition modifiers.
        toxin_layers: Shape ``(num_toxins, W, H)`` toxin concentration layers.
        width: The horizontal bounds of the simulation grid environment.
        height: The vertical bounds of the simulation grid environment.
        base: Pre-allocated 2-D scratch array.
        current: Pre-allocated 2-D scratch array.
        nxt: Pre-allocated 2-D scratch array.
        alpha: Attractant weight.
        beta: Repellent weight.
        decay: Decay factor.
        truncate_threshold: Truncation threshold.

    Returns:
        npt.NDArray[np.float64]: Flow-field gradient of shape ``(W, H)``.
    """
    if base is None:
        base = np.zeros((width, height), dtype=np.float64)
    if current is None:
        current = np.zeros((width, height), dtype=np.float64)
    if nxt is None:
        nxt = np.zeros((width, height), dtype=np.float64)

    result = np.asarray(
        _compute_flow_field(
            plant_energy,
            apparent_nutrition_layer,
            toxin_layers,
            width,
            height,
            base,
            current,
            nxt,
            alpha,
            beta,
            decay,
            truncate_threshold,
        ),
        dtype=np.float64,
    )
    return result


def apply_camouflage(
    flow_field: npt.NDArray[np.float64],
    x: int,
    y: int,
    factor: float,
) -> None:
    """Attenuate the flow-field gradient at cell (x, y) in-place.

    Args:
        flow_field: Mutable gradient array ``(W, H)``.
        x: The X-axis spatial grid coordinate.
        y: The Y-axis spatial grid coordinate.
        factor: Multiplier in [0, 1]; 0 = invisible, 1 = no attenuation.
    """
    flow_field[x, y] *= factor
