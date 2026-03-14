"""Flow-field gradient generation accelerated with Numba @njit.

The global attraction gradient is computed by combining plant attraction
and toxin repulsion, then propagating values to neighbours. The scalar
field is intended to populate :class:`GridEnvironment.flow_field`.
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
) -> npt.NDArray[np.float64]:
    """Compute the attraction gradient using iterative Jacobi propagation.

    Args:
        plant_energy: 2-D array ``(W, H)`` of aggregated plant energy per cell.
        toxin_sum: 2-D array ``(W, H)`` of aggregated toxin concentration per cell.
        width: Grid width W.
        height: Grid height H.

    Returns:
        npt.NDArray[np.float64]: Scalar attraction field of shape ``(W, H)``.
    """
    base = np.zeros((width, height), dtype=np.float64)
    current = np.zeros((width, height), dtype=np.float64)
    nxt = np.zeros((width, height), dtype=np.float64)

    for x in range(width):
        for y in range(height):
            base[x, y] = plant_energy[x, y] - toxin_sum[x, y]
            current[x, y] = base[x, y]

    # Iterative propagation lets attraction/repulsion travel multiple hops.
    decay = 0.6
    max_iterations = width + height
    for _ in range(max_iterations):
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
                nxt[x, y] = base[x, y] + (decay * propagated)

        current, nxt = nxt, current

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
) -> npt.NDArray[np.float64]:
    """Public wrapper: sum toxin layers and delegate to the Numba kernel.

    Args:
        plant_energy: Shape ``(W, H)`` aggregate plant energy.
        toxin_layers: Shape ``(num_toxins, W, H)`` toxin concentration layers.
        width: Grid width.
        height: Grid height.

    Returns:
        npt.NDArray[np.float64]: Flow-field gradient of shape ``(W, H)``.
    """
    toxin_sum: npt.NDArray[np.float64] = toxin_layers.sum(axis=0)
    return _compute_flow_field(plant_energy, toxin_sum, width, height)


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
