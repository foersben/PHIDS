"""Flow-field gradient generation accelerated with Numba @njit.

The global attraction gradient is computed by combining plant attraction
and toxin repulsion, then propagating values to neighbours. The scalar
field is intended to populate :class:`GridEnvironment.flow_field`.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
from numba import njit  # type: ignore[import-untyped]


@njit(cache=True)
def _compute_flow_field(
    plant_energy: npt.NDArray[np.float64],
    toxin_sum: npt.NDArray[np.float64],
    width: int,
    height: int,
) -> npt.NDArray[np.float64]:
    """Compute the attraction gradient using an iterative propagation.

    Args:
        plant_energy: 2-D array ``(W, H)`` of aggregated plant energy per cell.
        toxin_sum: 2-D array ``(W, H)`` of aggregated toxin concentration per cell.
        width: Grid width W.
        height: Grid height H.

    Returns:
        npt.NDArray[np.float64]: Scalar attraction field of shape ``(W, H)``.
    """
    gradient = np.zeros((width, height), dtype=np.float64)

    # Base layer: plant attraction minus toxin repulsion
    for x in range(width):
        for y in range(height):
            gradient[x, y] = plant_energy[x, y] - toxin_sum[x, y]

    # Single BFS-style propagation pass (spreading attraction to neighbours)
    propagated = np.zeros((width, height), dtype=np.float64)
    decay = 0.5
    for x in range(width):
        for y in range(height):
            val = gradient[x, y]
            propagated[x, y] += val
            # Propagate to 4-connected neighbours with decay
            if x > 0:
                propagated[x - 1, y] += val * decay
            if x < width - 1:
                propagated[x + 1, y] += val * decay
            if y > 0:
                propagated[x, y - 1] += val * decay
            if y < height - 1:
                propagated[x, y + 1] += val * decay

    return propagated


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
