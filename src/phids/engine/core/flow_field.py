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

import numpy as np
import numpy.typing as npt
from numba import njit


@njit(cache=True)
def _init_base_and_current_jit(
    width: int,
    height: int,
    plant_energy: npt.NDArray[np.float64],
    apparent_nutrition_layer: npt.NDArray[np.float64],
    toxin_sum: npt.NDArray[np.float64],
    base: npt.NDArray[np.float64],
    current: npt.NDArray[np.float64],
) -> None:
    """Helper function to initialize the base and current flow fields.

    Args:
        width: _description_
        height: _description_
        plant_energy: _description_
        apparent_nutrition_layer: _description_
        toxin_sum: _description_
        base: _description_
        current (npt.NDArray[np.float64]): _description_
    """
    for x in range(width):
        for y in range(height):
            base[x, y] = (plant_energy[x, y] * apparent_nutrition_layer[x, y]) - toxin_sum[x, y]
            current[x, y] = base[x, y]


@njit(cache=True)
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
    neighbours_sum = 0.0
    neighbour_count = 0
    if x > 0:
        neighbours_sum += current[x - 1, y]
        neighbour_count += 1
    if x < width - 1:
        neighbours_sum += current[x + 1, y]
        neighbour_count += 1
    if y > 0:
        neighbours_sum += current[x, y - 1]
        neighbour_count += 1
    if y < height - 1:
        neighbours_sum += current[x, y + 1]
        neighbour_count += 1
    return neighbours_sum, neighbour_count


@njit(cache=True)
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
            neighbours_sum, neighbour_count = _sum_neighbours_jit(x, y, width, height, current)
            propagated = neighbours_sum / neighbour_count if neighbour_count > 0 else 0.0
            val = base[x, y] + (decay * propagated)
            nxt[x, y] = val

            diff = abs(val - current[x, y])
            if diff > max_diff:
                max_diff = diff
    return max_diff


@njit(cache=True)
def _truncate_subnormals_jit(
    width: int,
    height: int,
    current: npt.NDArray[np.float64],
) -> None:
    """Helper function to truncate subnormal floats to exactly zero.

    Args:
        width: The width of the grid environment.
        height: The height of the grid environment.
        current: The current flow field.
    """
    for x in range(width):
        for y in range(height):
            if abs(current[x, y]) < 1e-4:
                current[x, y] = 0.0


# pragma: no mutate start
def _compute_flow_field_impl(
    plant_energy: npt.NDArray[np.float64],
    apparent_nutrition_layer: npt.NDArray[np.float64],
    toxin_sum: npt.NDArray[np.float64],
    width: int,
    height: int,
    base: npt.NDArray[np.float64],
    current: npt.NDArray[np.float64],
    nxt: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """Execute iterative relaxation propagation to generate a navigation grid.

    The scalar flow field converges globally towards botanical sources (positives)
    and expands away from warning chemicals (negatives) by resolving spatial
    gradients ticks-by-ticks dynamically.

    Args:
        plant_energy: Array of plant energy per cell.
        apparent_nutrition_layer: Array of apparent nutrition multipliers per cell.
        toxin_sum: Array of toxin concentrations per cell.
        width: The width of the grid environment.
        height: The height of the grid environment.
        base: Pre-allocated array for base flow field.
        current: Pre-allocated array for current flow field.
        nxt: Pre-allocated array for next flow field.

    Returns:
        Scalar attraction field of shape ``(W, H)``.
    """
    base.fill(0.0)
    current.fill(0.0)
    nxt.fill(0.0)

    _init_base_and_current_jit(width, height, plant_energy, apparent_nutrition_layer, toxin_sum, base, current)

    # Iterative propagation lets attraction/repulsion travel multiple hops.
    decay = 0.6
    max_iterations = width + height
    for _ in range(max_iterations):
        max_diff = _propagate_iteration_jit(width, height, decay, base, current, nxt)
        current, nxt = nxt, current

        # Early stopping if convergence is reached
        if max_diff < 1e-4:
            break

    # Truncate subnormal floats to exactly zero
    _truncate_subnormals_jit(width, height, current)

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

    Returns:
        npt.NDArray[np.float64]: Flow-field gradient of shape ``(W, H)``.
    """
    if base is None:
        base = np.zeros((width, height), dtype=np.float64)
    if current is None:
        current = np.zeros((width, height), dtype=np.float64)
    if nxt is None:
        nxt = np.zeros((width, height), dtype=np.float64)

    toxin_sum: npt.NDArray[np.float64] = toxin_layers.sum(axis=0)
    result = np.asarray(
        _compute_flow_field(plant_energy, apparent_nutrition_layer, toxin_sum, width, height, base, current, nxt),
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
