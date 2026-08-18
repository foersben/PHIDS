# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Flow-field gradient generation accelerated with Numba ``@njit`` for deterministic ecological simulation.

This module provides the Jacobi iteration solver for pathfinding. It strictly adheres to Numba compilation
constraints: no Python dictionaries, lists, or custom classes are used inside `@njit` kernels. All array
operations rely on pre-allocated buffers and contiguous layouts to prevent memory allocation latency
during the hot-path evaluation phase. The global attraction gradient is
computed by combining plant attraction and toxin repulsion base values, then propagating them
across the grid via a multi-iteration neighbourhood averaging pass with configurable decay. The
resulting scalar field is intended to populate ``GridEnvironment.flow_field``, supporting O(1)
spatial hash-mediated swarm navigation and deterministic simulation of emergent plant-herbivore
dynamics. The design strictly adheres to data-oriented principles, using pre-allocated NumPy
arrays and truncating subnormal floats (values with absolute magnitude below 1e-4) to zero after
propagation to maintain computational efficiency. Camouflage is applied post-computation via
``apply_camouflage``, which attenuates the gradient at specific plant-occupied cells to model
constitutive gradient masking.
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

NUMBA_PARALLEL_THRESHOLD_CELLS: Final[int] = 128 * 128


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

    256-Bit AVX2 SIMD Vectorization & Zero-Allocation Memory Constraints:
    ----------------------------------------------------------------------
    While NumPy array operations like `np.sum(toxin_layers, axis=0)` implicitly utilize SIMD
    instructions, they allocate temporary arrays in memory. Because this function is called on
    the hot path every simulation tick, such dynamic allocations violate the engine's strict
    zero-allocation mandate and introduce garbage collection latency.

    Instead, we use explicit nested loops tailored for contiguous memory access (ensuring the
    last array dimension `y` is the innermost loop). Numba's LLVM backend auto-vectorizes these
    contiguous scalar operations into the exact same 256-bit AVX2 vector instructions (e.g.,
    fused multiply-add `vfmadd213pd`) without ever allocating intermediate arrays. This achieves
    maximum hardware performance while strictly adhering to ECS memory constraints.

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

    # Pre-calculate base values (Perfectly contiguous, LLVM will AVX2 vectorize this)
    for x in range(width):
        for y in range(height):
            base[x, y] = alpha * plant_energy[x, y] * apparent_nutrition_layer[x, y]

    # Subtract toxins inline (Perfectly contiguous, LLVM will AVX2 vectorize this)
    for t in range(num_toxins):
        for x in range(width):
            for y in range(height):
                base[x, y] -= beta * toxin_layers[t, x, y]

    # Copy to current buffer (LLVM will vectorize this into AVX2 block copies)
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
    """Helper function to sum the neighbours of a cell.

    Args:
        x: The x-coordinate of the cell.
        y: The y-coordinate of the cell.
        width: The width of the grid environment.
        height: The height of the grid environment.
        current: The current flow field.

    Returns:
        The sum of the neighbours and the number of neighbours.
    """
    neighbours_sum = (
        current[(x - 1) % width, y]
        + current[(x + 1) % width, y]
        + current[x, (y - 1) % height]
        + current[x, (y + 1) % height]
    )
    # Toroidal grid always has width >= 4 and height >= 4; count is always 4.
    return neighbours_sum, 4


@njit(cache=True, fastmath=True)
def _sum_neighbours_jit_pow2(
    x: int,
    y: int,
    mask_x: int,
    mask_y: int,
    current: npt.NDArray[np.float64],
) -> tuple[float, int]:
    """Helper function to sum the neighbours of a cell using bitwise AND masking."""
    neighbours_sum = (
        current[(x - 1) & mask_x, y]
        + current[(x + 1) & mask_x, y]
        + current[x, (y - 1) & mask_y]
        + current[x, (y + 1) & mask_y]
    )
    return neighbours_sum, 4


@njit(cache=True, fastmath=True)
def _propagate_iteration_jit(
    width: int,
    height: int,
    decay: float,
    base: npt.NDArray[np.float64],
    current: npt.NDArray[np.float64],
    nxt: npt.NDArray[np.float64],
) -> float:
    """Helper function to perform one iteration of the Jacobi relaxation.

    Args:
        width: The width of the grid environment.
        height: The height of the grid environment.
        decay: The decay rate.
        base: The base flow field.
        current: The current flow field.
        nxt: The next flow field.

    Returns:
        The maximum difference between the current and next flow fields.
    """
    max_diff = 0.0
    for x in range(width):
        for y in range(height):
            # neighbour_count is always 4 on a toroidal grid (width >= 4, height >= 4)
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
    """Helper function to perform one iteration of the Jacobi relaxation using bitwise AND masking.

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
        The maximum difference between the current and next flow fields.
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
    """Helper function to perform one multi-threaded OpenMP iteration of Jacobi relaxation."""
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
    """Helper function to perform one multi-threaded OpenMP iteration of bitwise Jacobi relaxation."""
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


@njit(cache=True, fastmath=True)
def _truncate_subnormals_jit(
    width: int,
    height: int,
    current: npt.NDArray[np.float64],
    threshold: float,
) -> None:
    """Helper function to truncate subnormal floats to exactly zero.

    Args:
        width: The width of the grid environment.
        height: The height of the grid environment.
        current: The current flow field.
        threshold: Subnormal truncation threshold.
    """
    for x in range(width):
        for y in range(height):
            if abs(current[x, y]) < threshold:
                current[x, y] = 0.0


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
    """Helper function to update the top and bottom boundaries for a given x-coordinate.

    Args:
        x: The x-coordinate.
        width: The width of the grid.
        height: The height of the grid.
        decay: The decay rate.
        base: The base flow field.
        current: The current flow field.
        nxt: The next flow field.

    Returns:
        The maximum difference for this x-coordinate slice.
    """
    max_diff = 0.0
    # Top boundary (y=0): neighbour_count always 4 on toroidal grid
    n_sum, _ = _sum_neighbours_jit(x, 0, width, height, current)
    val = base[x, 0] + (decay * n_sum * 0.25)
    nxt[x, 0] = val
    diff1 = abs(val - current[x, 0])
    if diff1 > max_diff:
        max_diff = diff1

    # Bottom boundary (y=height-1)
    n_sum, _ = _sum_neighbours_jit(x, height - 1, width, height, current)
    val = base[x, height - 1] + (decay * n_sum * 0.25)
    nxt[x, height - 1] = val
    diff2 = abs(val - current[x, height - 1])
    if diff2 > max_diff:
        max_diff = diff2
    return max_diff


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
    """Helper function to update the left and right boundaries for a given y-coordinate.

    Args:
        y: The y-coordinate.
        width: The width of the grid.
        height: The height of the grid.
        decay: The decay rate.
        base: The base flow field.
        current: The current flow field.
        nxt: The next flow field.

    Returns:
        The maximum difference for this y-coordinate slice.
    """
    max_diff = 0.0
    # Left boundary (x=0): neighbour_count always 4 on toroidal grid
    n_sum, _ = _sum_neighbours_jit(0, y, width, height, current)
    val = base[0, y] + (decay * n_sum * 0.25)
    nxt[0, y] = val
    diff1 = abs(val - current[0, y])
    if diff1 > max_diff:
        max_diff = diff1

    # Right boundary (x=width-1)
    n_sum, _ = _sum_neighbours_jit(width - 1, y, width, height, current)
    val = base[width - 1, y] + (decay * n_sum * 0.25)
    nxt[width - 1, y] = val
    diff2 = abs(val - current[width - 1, y])
    if diff2 > max_diff:
        max_diff = diff2
    return max_diff


@njit(cache=True, fastmath=True)
def _propagate_boundaries_jit(
    width: int,
    height: int,
    decay: float,
    base: npt.NDArray[np.float64],
    current: npt.NDArray[np.float64],
    nxt: npt.NDArray[np.float64],
) -> float:
    """Helper function to propagate the flow field along the boundaries.

    Args:
        width: The width of the grid environment.
        height: The height of the grid environment.
        decay: The decay rate.
        base: The base flow field.
        current: The current flow field.
        nxt: The next flow field.

    Returns:
        The maximum difference between the current and next flow fields along the boundaries.
    """
    max_diff = 0.0

    for x in range(width):
        d = _update_boundary_x_jit(x, width, height, decay, base, current, nxt)
        if d > max_diff:
            max_diff = d

    for y in range(1, height - 1):
        d = _update_boundary_y_jit(y, width, height, decay, base, current, nxt)
        if d > max_diff:
            max_diff = d

    return max_diff


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
    max_diff = 0.0
    n_sum, _ = _sum_neighbours_jit_pow2(x, 0, mask_x, mask_y, current)
    val = base[x, 0] + (decay * n_sum * 0.25)
    nxt[x, 0] = val
    diff1 = abs(val - current[x, 0])
    if diff1 > max_diff:
        max_diff = diff1

    n_sum, _ = _sum_neighbours_jit_pow2(x, height - 1, mask_x, mask_y, current)
    val = base[x, height - 1] + (decay * n_sum * 0.25)
    nxt[x, height - 1] = val
    diff2 = abs(val - current[x, height - 1])
    if diff2 > max_diff:
        max_diff = diff2
    return max_diff


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
    max_diff = 0.0
    n_sum, _ = _sum_neighbours_jit_pow2(0, y, mask_x, mask_y, current)
    val = base[0, y] + (decay * n_sum * 0.25)
    nxt[0, y] = val
    diff1 = abs(val - current[0, y])
    if diff1 > max_diff:
        max_diff = diff1

    n_sum, _ = _sum_neighbours_jit_pow2(width - 1, y, mask_x, mask_y, current)
    val = base[width - 1, y] + (decay * n_sum * 0.25)
    nxt[width - 1, y] = val
    diff2 = abs(val - current[width - 1, y])
    if diff2 > max_diff:
        max_diff = diff2
    return max_diff


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
    max_diff = 0.0

    for x in range(width):
        d = _update_boundary_x_jit_pow2(x, height, mask_x, mask_y, decay, base, current, nxt)
        if d > max_diff:
            max_diff = d

    for y in range(1, height - 1):
        d = _update_boundary_y_jit_pow2(y, width, mask_x, mask_y, decay, base, current, nxt)
        if d > max_diff:
            max_diff = d

    return max_diff


@njit(cache=True, fastmath=True)
def _propagate_inner_jit(
    width: int,
    height: int,
    decay: float,
    base: npt.NDArray[np.float64],
    current: npt.NDArray[np.float64],
    nxt: npt.NDArray[np.float64],
) -> float:
    """Helper function to propagate the flow field in the inner grid.

    Args:
        width: The width of the grid environment.
        height: The height of the grid environment.
        decay: The decay rate.
        base: The base flow field.
        current: The current flow field.
        nxt: The next flow field.

    Returns:
        The maximum difference between the current and next flow fields in the inner grid.
    """
    max_diff = 0.0
    # Handle inner cells without boundary checks
    for x in range(1, width - 1):
        for y in range(1, height - 1):
            n_sum = current[x - 1, y] + current[x + 1, y] + current[x, y - 1] + current[x, y + 1]
            propagated = n_sum * 0.25  # neighbour_count is always 4
            val = base[x, y] + (decay * propagated)
            nxt[x, y] = val
            diff = abs(val - current[x, y])
            if diff > max_diff:
                max_diff = diff
    return max_diff


# pragma: no mutate start
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

    The scalar flow field converges globally towards botanical sources (positives)
    and expands away from warning chemicals (negatives) by resolving spatial
    gradients ticks-by-ticks dynamically.

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
        Scalar attraction field of shape ``(W, H)``.
    """
    base.fill(0.0)
    current.fill(0.0)
    nxt.fill(0.0)

    _init_base_and_current_jit(
        width, height, plant_energy, apparent_nutrition_layer, toxin_layers, base, current, alpha, beta
    )

    # Iterative propagation lets attraction/repulsion travel multiple hops.
    max_iterations = width + height
    is_pow2 = (width > 0 and (width & (width - 1)) == 0) and (height > 0 and (height & (height - 1)) == 0)
    mask_x = width - 1
    mask_y = height - 1
    use_parallel = width * height >= NUMBA_PARALLEL_THRESHOLD_CELLS

    if is_pow2:
        if use_parallel:
            for _ in range(max_iterations):
                max_diff = _propagate_iteration_jit_pow2_parallel(
                    width, height, mask_x, mask_y, decay, base, current, nxt
                )
                current, nxt = nxt, current
                if max_diff < truncate_threshold:
                    break
        else:
            for _ in range(max_iterations):
                max_diff = _propagate_iteration_jit_pow2(width, height, mask_x, mask_y, decay, base, current, nxt)
                current, nxt = nxt, current
                if max_diff < truncate_threshold:
                    break
    else:
        if use_parallel:
            for _ in range(max_iterations):
                max_diff = _propagate_iteration_jit_parallel(width, height, decay, base, current, nxt)
                current, nxt = nxt, current
                if max_diff < truncate_threshold:
                    break
        else:
            for _ in range(max_iterations):
                diff_boundaries = _propagate_boundaries_jit(width, height, decay, base, current, nxt)
                diff_inner = _propagate_inner_jit(width, height, decay, base, current, nxt)
                max_diff = diff_boundaries if diff_boundaries > diff_inner else diff_inner
                current, nxt = nxt, current
                if max_diff < truncate_threshold:
                    break

    # Truncate subnormal floats to exactly zero
    _truncate_subnormals_jit(width, height, current, truncate_threshold)

    return current


_compute_flow_field = njit(cache=True)(_compute_flow_field_impl)
# pragma: no mutate end


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
        base = np.zeros((width, height), dtype=np.float64)  # pragma: no mutate
    if current is None:
        current = np.zeros((width, height), dtype=np.float64)  # pragma: no mutate
    if nxt is None:
        nxt = np.zeros((width, height), dtype=np.float64)  # pragma: no mutate

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
