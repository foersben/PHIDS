"""Flow-field gradient generation accelerated with Numba ``@njit`` for deterministic ecological simulation.

This module implements the flow-field gradient computation for PHIDS, leveraging Numba JIT
compilation to accelerate iterative Jacobi propagation. The global attraction gradient is
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
from numba import njit  # type: ignore[import-untyped]


def _compute_flow_field_impl(
    plant_energy: npt.NDArray[np.float64],
    toxin_sum: npt.NDArray[np.float64],
    width: int,
    height: int,
    base: npt.NDArray[np.float64] | None = None,
    current: npt.NDArray[np.float64] | None = None,
    nxt: npt.NDArray[np.float64] | None = None,
) -> npt.NDArray[np.float64]:
    """Compute the attraction gradient using iterative Jacobi propagation.

    Args:
        plant_energy: 2-D array ``(W, H)`` of aggregated plant energy per cell.
        toxin_sum: 2-D array ``(W, H)`` of aggregated toxin concentration per cell.
        width: Grid width W.
        height: Grid height H.
        base: Pre-allocated 2-D scratch array.
        current: Pre-allocated 2-D scratch array.
        nxt: Pre-allocated 2-D scratch array.

    Returns:
        npt.NDArray[np.float64]: Scalar attraction field of shape ``(W, H)``.
    """
    if base is None:
        base = np.zeros((width, height), dtype=np.float64)
    else:
        base.fill(0.0)

    if current is None:
        current = np.zeros((width, height), dtype=np.float64)
    else:
        current.fill(0.0)

    if nxt is None:
        nxt = np.zeros((width, height), dtype=np.float64)
    else:
        nxt.fill(0.0)

    for x in range(width):
        for y in range(height):
            base[x, y] = plant_energy[x, y] - toxin_sum[x, y]
            current[x, y] = base[x, y]

    # Iterative propagation lets attraction/repulsion travel multiple hops.
    decay = 0.6
    max_iterations = width + height
    for _ in range(max_iterations):
        max_diff = 0.0  # Track maximum delta in this pass

        for x in range(width):
            for y in range(height):
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

                propagated = neighbours_sum / neighbour_count if neighbour_count > 0 else 0.0
                val = base[x, y] + (decay * propagated)
                nxt[x, y] = val

                # Evaluate convergence
                diff = abs(val - current[x, y])
                if diff > max_diff:
                    max_diff = diff

        current, nxt = nxt, current

        # Early stopping if convergence is reached
        if max_diff < 1e-4:
            break

    # Truncate subnormal floats to exactly zero
    for x in range(width):
        for y in range(height):
            if abs(current[x, y]) < 1e-4:
                current[x, y] = 0.0

    return current


_compute_flow_field = njit(cache=True)(_compute_flow_field_impl)


def compute_flow_field(
    plant_energy: npt.NDArray[np.float64],
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
        toxin_layers: Shape ``(num_toxins, W, H)`` toxin concentration layers.
        width: Grid width.
        height: Grid height.
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
        _compute_flow_field(plant_energy, toxin_sum, width, height, base, current, nxt),
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
        x: X coordinate.
        y: Y coordinate.
        factor: Multiplier in [0, 1]; 0 = invisible, 1 = no attenuation.
    """
    flow_field[x, y] *= factor
