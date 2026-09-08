# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Numba-accelerated 2D advection and Gaussian convolution diffusion kernels.

This module provides high-performance JIT-compiled kernels implementing the reaction-diffusion
and semi-Lagrangian advection partial differential equations (PDEs) for environmental signal
and toxin layers. Both standard modulo wrapping and bitwise power-of-two toroidal boundary
conditions are supported.

Double-buffering and pre-allocation constraints are strictly enforced: no dynamic array
allocations occur inside JIT loops.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt
from numba import njit

if TYPE_CHECKING:
    prange = range
else:
    from numba import prange

# ---------------------------------------------------------------------------
# Gaussian diffusion kernel configuration
# ---------------------------------------------------------------------------
KERNEL_SIZE: int = 5
"""Standard odd-sized spatial window dimension (5x5) for discrete Gaussian kernel."""

SIGMA: float = 0.4
"""Standard deviation of the Gaussian spatial kernel.

With sigma = 0.4, weights at Euclidean distance d >= 2 drop below SIGNAL_EPSILON (~10^-4),
ensuring compact 3x3 footprint dispersion per tick without long-range numerical leakage.
"""

_KERNEL_SIZE: int = KERNEL_SIZE
_SIGMA: float = SIGMA


@njit(parallel=True, cache=True, fastmath=True)
def _numba_advect_signal_layer(
    width: int,
    height: int,
    layer: npt.NDArray[np.float64],
    wind_x: npt.NDArray[np.float64],
    wind_y: npt.NDArray[np.float64],
    advected_scratch: npt.NDArray[np.float64],
) -> None:
    """Semi-Lagrangian backward advection across toroidal boundaries using standard modulo arithmetic.

    Args:
        width: Grid width in cells.
        height: Grid height in cells.
        layer: Read-only source concentration layer of shape (width, height).
        wind_x: Read-only wind velocity field along X axis of shape (width, height).
        wind_y: Read-only wind velocity field along Y axis of shape (width, height).
        advected_scratch: Pre-allocated destination scratch buffer mutated in-place.
    """
    advected_scratch.fill(0.0)
    # 1. Semi-Lagrangian Advection (backward interpolation with Toroidal wrap)
    for x in prange(width):
        for y in range(height):
            cx = x - wind_x[x, y]
            cy = y - wind_y[x, y]

            floor_x = int(np.floor(cx))
            floor_y = int(np.floor(cy))

            x0 = floor_x % width
            y0 = floor_y % height
            x1 = (floor_x + 1) % width
            y1 = (floor_y + 1) % height

            dx = cx - floor_x
            dy = cy - floor_y

            v00 = layer[x0, y0]
            v10 = layer[x1, y0]
            v01 = layer[x0, y1]
            v11 = layer[x1, y1]

            val_y0 = v00 * (1.0 - dx) + v10 * dx
            val_y1 = v01 * (1.0 - dx) + v11 * dx
            val = val_y0 * (1.0 - dy) + val_y1 * dy

            advected_scratch[x, y] = val


@njit(parallel=True, cache=True, fastmath=True)
def _numba_convolve_signal_layer(
    width: int,
    height: int,
    decay: float,
    epsilon: float,
    kernel: npt.NDArray[np.float64],
    write_buffer: npt.NDArray[np.float64],
    advected_scratch: npt.NDArray[np.float64],
) -> None:
    """Toroidal Gaussian convolution diffusion and decay using standard modulo arithmetic.

    Args:
        width: Grid width in cells.
        height: Grid height in cells.
        decay: Evaporation multiplier applied per tick (0.0 < decay <= 1.0).
        epsilon: Signal epsilon threshold below which values are clamped to zero.
        kernel: 2D discrete Gaussian kernel of shape (k_w, k_h).
        write_buffer: Pre-allocated output buffer mutated in-place.
        advected_scratch: Intermediate advected concentration buffer.
    """
    # 2. Toroidal Gaussian Diffusion (Convolution) & Decay
    k_w = kernel.shape[0]
    k_h = kernel.shape[1]
    k_w_half = k_w // 2
    k_h_half = k_h // 2

    for x in prange(width):
        for y in range(height):
            v = 0.0
            for i in range(-k_w_half, k_w_half + 1):
                ax = (x - i) % width
                for j in range(-k_h_half, k_h_half + 1):
                    ay = (y - j) % height
                    v += advected_scratch[ax, ay] * kernel[k_w_half + i, k_h_half + j]

            # Apply decay and zero-out subnormal floats branchlessly via ternary select
            v *= decay
            v = 0.0 if v < epsilon else v
            write_buffer[x, y] = v


@njit(cache=True, fastmath=True)
def _numba_diffuse_signal_layer(
    width: int,
    height: int,
    layer: npt.NDArray[np.float64],
    wind_x: npt.NDArray[np.float64],
    wind_y: npt.NDArray[np.float64],
    decay: float,
    epsilon: float,
    kernel: npt.NDArray[np.float64],
    write_buffer: npt.NDArray[np.float64],
    advected_scratch: npt.NDArray[np.float64],
) -> None:
    """Execute combined advection and Gaussian convolution diffusion for arbitrary grid dimensions.

    Args:
        width: Grid width in cells.
        height: Grid height in cells.
        layer: Current concentration of the signal layer.
        wind_x: X-component of the advecting wind field.
        wind_y: Y-component of the advecting wind field.
        decay: Evaporation/decay rate per tick.
        epsilon: Minimum concentration threshold to clamp noise to zero.
        kernel: 2D diffusion kernel for spatial dispersion.
        write_buffer: Pre-allocated output array (mutated in-place).
        advected_scratch: Pre-allocated scratch array for intermediate advection (mutated in-place).
    """
    _numba_advect_signal_layer(width, height, layer, wind_x, wind_y, advected_scratch)
    _numba_convolve_signal_layer(width, height, decay, epsilon, kernel, write_buffer, advected_scratch)


@njit(parallel=True, cache=True, fastmath=True)
def _numba_advect_signal_layer_pow2(
    width: int,
    height: int,
    mask_x: int,
    mask_y: int,
    layer: npt.NDArray[np.float64],
    wind_x: npt.NDArray[np.float64],
    wind_y: npt.NDArray[np.float64],
    advected_scratch: npt.NDArray[np.float64],
) -> None:
    """Semi-Lagrangian backward advection optimized for power-of-two grids using bitwise masks.

    Args:
        width: Grid width in cells.
        height: Grid height in cells.
        mask_x: Bitwise mask for width (width - 1).
        mask_y: Bitwise mask for height (height - 1).
        layer: Read-only source concentration layer of shape (width, height).
        wind_x: Read-only wind velocity field along X axis of shape (width, height).
        wind_y: Read-only wind velocity field along Y axis of shape (width, height).
        advected_scratch: Pre-allocated destination scratch buffer mutated in-place.
    """
    advected_scratch.fill(0.0)
    for x in prange(width):
        for y in range(height):
            cx = x - wind_x[x, y]
            cy = y - wind_y[x, y]

            floor_x = int(np.floor(cx))
            floor_y = int(np.floor(cy))

            x0 = floor_x & mask_x
            y0 = floor_y & mask_y
            x1 = (floor_x + 1) & mask_x
            y1 = (floor_y + 1) & mask_y

            dx = cx - floor_x
            dy = cy - floor_y

            v00 = layer[x0, y0]
            v10 = layer[x1, y0]
            v01 = layer[x0, y1]
            v11 = layer[x1, y1]

            val_y0 = v00 * (1.0 - dx) + v10 * dx
            val_y1 = v01 * (1.0 - dx) + v11 * dx
            val = val_y0 * (1.0 - dy) + val_y1 * dy

            advected_scratch[x, y] = val


@njit(parallel=True, cache=True, fastmath=True)
def _numba_convolve_signal_layer_pow2(
    width: int,
    height: int,
    mask_x: int,
    mask_y: int,
    decay: float,
    epsilon: float,
    kernel: npt.NDArray[np.float64],
    write_buffer: npt.NDArray[np.float64],
    advected_scratch: npt.NDArray[np.float64],
) -> None:
    """Toroidal Gaussian convolution diffusion and decay optimized for power-of-two grids using bitwise masks.

    Args:
        width: Grid width in cells.
        height: Grid height in cells.
        mask_x: Bitwise mask for width (width - 1).
        mask_y: Bitwise mask for height (height - 1).
        decay: Evaporation multiplier applied per tick.
        epsilon: Signal epsilon threshold below which values are clamped to zero.
        kernel: 2D discrete Gaussian kernel of shape (k_w, k_h).
        write_buffer: Pre-allocated output buffer mutated in-place.
        advected_scratch: Intermediate advected concentration buffer.
    """
    k_w = kernel.shape[0]
    k_h = kernel.shape[1]
    k_w_half = k_w // 2
    k_h_half = k_h // 2

    for x in prange(width):
        for y in range(height):
            v = 0.0
            for i in range(-k_w_half, k_w_half + 1):
                ax = (x - i) & mask_x
                for j in range(-k_h_half, k_h_half + 1):
                    ay = (y - j) & mask_y
                    v += advected_scratch[ax, ay] * kernel[k_w_half + i, k_h_half + j]

            v *= decay
            v = 0.0 if v < epsilon else v
            write_buffer[x, y] = v


@njit(cache=True, fastmath=True)
def _numba_diffuse_signal_layer_pow2(
    width: int,
    height: int,
    mask_x: int,
    mask_y: int,
    layer: npt.NDArray[np.float64],
    wind_x: npt.NDArray[np.float64],
    wind_y: npt.NDArray[np.float64],
    decay: float,
    epsilon: float,
    kernel: npt.NDArray[np.float64],
    write_buffer: npt.NDArray[np.float64],
    advected_scratch: npt.NDArray[np.float64],
) -> None:
    """Execute combined advection and Gaussian convolution diffusion for power-of-two grid dimensions.

    Args:
        width: Grid width in cells (must be a power of two).
        height: Grid height in cells (must be a power of two).
        mask_x: Bitwise mask for width (width - 1).
        mask_y: Bitwise mask for height (height - 1).
        layer: Current concentration of the signal layer.
        wind_x: X-component of the advecting wind field.
        wind_y: Y-component of the advecting wind field.
        decay: Evaporation/decay rate per tick.
        epsilon: Minimum concentration threshold to clamp noise to zero.
        kernel: 2D diffusion kernel for spatial dispersion.
        write_buffer: Pre-allocated output array (mutated in-place).
        advected_scratch: Pre-allocated scratch array for intermediate advection (mutated in-place).
    """
    _numba_advect_signal_layer_pow2(width, height, mask_x, mask_y, layer, wind_x, wind_y, advected_scratch)
    _numba_convolve_signal_layer_pow2(
        width, height, mask_x, mask_y, decay, epsilon, kernel, write_buffer, advected_scratch
    )


def _make_gaussian_kernel(size: int = _KERNEL_SIZE, sigma: float = _SIGMA) -> npt.NDArray[np.float64]:
    """Return a normalised 2-D Gaussian kernel for VOC diffusion.

    Args:
        size: Kernel size (must be odd). Defaults to 5.
        sigma: Standard deviation of the Gaussian. Defaults to 0.4.

    Returns:
        npt.NDArray[np.float64]: 2-D array of shape (size, size) representing the kernel.

    Raises:
        ValueError: If size is even.

    Example:
        >>> kernel = _make_gaussian_kernel(size=5, sigma=0.4)
        >>> np.isclose(kernel.sum(), 1.0)
        True
    """
    if size % 2 == 0:
        raise ValueError("Kernel size must be odd to maintain central symmetry.")
    ax = np.arange(-(size // 2), size // 2 + 1, dtype=np.float64)  # pragma: no mutate
    xx, yy = np.meshgrid(ax, ax)
    kernel: npt.NDArray[np.float64] = np.exp(-(xx**2 + yy**2) / (2.0 * sigma**2))
    normalized = np.asarray(kernel / kernel.sum(), dtype=np.float64)  # pragma: no mutate
    return normalized


DIFFUSION_KERNEL: npt.NDArray[np.float64] = _make_gaussian_kernel()
"""Pre-computed 5x5 normalized discrete Gaussian convolution kernel with sigma=0.4."""

__all__ = [
    "DIFFUSION_KERNEL",
    "KERNEL_SIZE",
    "SIGMA",
    "_KERNEL_SIZE",
    "_SIGMA",
    "_make_gaussian_kernel",
    "_numba_advect_signal_layer",
    "_numba_advect_signal_layer_pow2",
    "_numba_convolve_signal_layer",
    "_numba_convolve_signal_layer_pow2",
    "_numba_diffuse_signal_layer",
    "_numba_diffuse_signal_layer_pow2",
]
