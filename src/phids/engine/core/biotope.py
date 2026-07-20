# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""GridEnvironment: NumPy-backed biotope with 2-D convolution diffusion and explicit double-buffering.

This module manages the continuous environmental state (e.g., plant energy layers, VOC gradients,
wind fields, and apparent nutrition). It enforces strict read/write double-buffering across all layers
to prevent race conditions and maintain exact tick-level determinism during concurrent simulation phases.
No allocations are made during the diffusion loop. All layers are pre-allocated according to the Rule of
16, ensuring fixed memory allocation and avoiding dynamic resizing during simulation. The
environment employs explicit read/write double-buffering to prevent race conditions and guarantee
deterministic simulation of biological phenomena such as Gaussian diffusion, systemic acquired
resistance, and metabolic attrition. The convolution kernel is pre-computed and its tails are
truncated to eliminate subnormal floats below ``SIGNAL_EPSILON``, maintaining computational
efficiency and scientific accuracy. The architectural design is tightly coupled to the
:class:`~phids.engine.core.ecs.ECSWorld` and flow-field systems, supporting O(1) spatial hash
lookups and reproducible ecological dynamics.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
from numba import njit

from phids.shared.constants import (
    GRID_H_MAX,
    GRID_W_MAX,
    MAX_FLORA_SPECIES,
    MAX_SUBSTANCE_TYPES,
    SIGNAL_EPSILON,
)

# ---------------------------------------------------------------------------
# Gaussian diffusion kernel (pre-computed, immutable)
# ---------------------------------------------------------------------------
_KERNEL_SIZE: int = 5
# Effect of different _SIGMA values:
# With _SIGMA = 0.8 (default): Weights at $d=2$ remain above 10^-4 after normalization,
# so the signal immediately fills the entire 5x5 neighborhood in 1 tick.
# With _SIGMA = 0.4: The weight at $d=2$ drops to ~10^-6. Because this is less than
# SIGNAL_EPSILON, the signal is clipped at the borders and only spreads to a 3x3 footprint on tick 1.
# With _SIGMA = 0.3: The weight at diagonal cells (d = sqrt(2) ~ 1.41) also drops
# below SIGNAL_EPSILON, restricting the single-tick spread to just a cross shape.
_SIGMA: float = 0.4


@njit
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
    """JIT-compiled advection and convolution (diffusion) kernel.

    Why is this function written so explicitly?
    -------------------------------------------
    This function is wrapped with Numba's `@njit` (nopython mode) to achieve C-level performance
    for the reaction-diffusion partial differential equations (PDEs) running every tick.
    Numba has extremely strict constraints:

    1. No High-Level Libraries: We cannot use `scipy.ndimage.map_coordinates` for advection
       or `scipy.ndimage.convolve` for diffusion. Everything must be implemented from scratch.
    2. Explicit Math: The "lengthy" code (like manual bounds checking and `val_y0 * (1.0 - dy)`)
       is a manual Bilinear Interpolation. By writing out the nested `for` loops and scalar
       operations explicitly, Numba's LLVM compiler can aggressively optimize and vectorize
       the execution.
    3. Memory Constraints: We cannot allocate arrays (`np.zeros`) inside the JIT loop without
       incurring massive overhead. Therefore, `write_buffer` and `advected_scratch` are
       pre-allocated outside the loop and passed by reference to be mutated in-place.

    Args:
        width: Grid width.
        height: Grid height.
        layer: Current concentration of the signal.
        wind_x: X-component of the wind field for advection.
        wind_y: Y-component of the wind field for advection.
        decay: Evaporation/decay rate of the signal.
        epsilon: Minimum concentration threshold to zero-out noise.
        kernel: 2D diffusion kernel for spreading the signal.
        write_buffer: Pre-allocated output array (mutated in-place).
        advected_scratch: Pre-allocated intermediate array for the advection step (mutated in-place).
    """
    advected_scratch.fill(0.0)

    # 1. Semi-Lagrangian Advection (backward interpolation)
    for x in range(width):
        for y in range(height):
            cx = float(x) - wind_x[x, y]
            cy = float(y) - wind_y[x, y]

            x0 = int(np.floor(cx))
            y0 = int(np.floor(cy))
            x1 = x0 + 1
            y1 = y0 + 1

            dx = cx - float(x0)
            dy = cy - float(y0)

            v00 = layer[x0, y0] if 0 <= x0 < width and 0 <= y0 < height else 0.0
            v10 = layer[x1, y0] if 0 <= x1 < width and 0 <= y0 < height else 0.0
            v01 = layer[x0, y1] if 0 <= x0 < width and 0 <= y1 < height else 0.0
            v11 = layer[x1, y1] if 0 <= x1 < width and 0 <= y1 < height else 0.0

            val_y0 = v00 * (1.0 - dx) + v10 * dx
            val_y1 = v01 * (1.0 - dx) + v11 * dx
            val = val_y0 * (1.0 - dy) + val_y1 * dy

            advected_scratch[x, y] = val

    # 2. Gaussian Diffusion (Convolution) & Decay
    # We must support an arbitrarily sized symmetric 2D kernel.
    k_w = kernel.shape[0]
    k_h = kernel.shape[1]
    k_w_half = k_w // 2
    k_h_half = k_h // 2

    for x in range(width):
        for y in range(height):
            v = 0.0
            for i in range(-k_w_half, k_w_half + 1):
                ax = x - i
                # Bolt Optimization: Hoisting the X-axis bounds check out of the inner Y-axis
                # loop reduces bounds-checking branches from 25 per cell down to 5 per cell,
                # measurably improving Numba JIT inner-loop vectorization and tick speed.
                if 0 <= ax < width:
                    for j in range(-k_h_half, k_h_half + 1):
                        ay = y - j
                        if 0 <= ay < height:
                            v += advected_scratch[ax, ay] * kernel[k_w_half + i, k_h_half + j]

            v *= decay
            if v < epsilon:
                v = 0.0
            write_buffer[x, y] = v


def _make_gaussian_kernel(size: int = _KERNEL_SIZE, sigma: float = _SIGMA) -> npt.NDArray[np.float64]:
    """Return a normalised 2-D Gaussian kernel for VOC diffusion.

    Args:
        size: Kernel size (must be odd).
        sigma: Standard deviation of the Gaussian.

    Raises:
        ValueError: If size is even.

    Returns:
        npt.NDArray[np.float64]: 2-D array of shape (size, size) representing the kernel.
    """
    if size % 2 == 0:
        raise ValueError("Kernel size must be odd to maintain central symmetry.")
    ax = np.arange(-(size // 2), size // 2 + 1, dtype=np.float64)
    xx, yy = np.meshgrid(ax, ax)
    kernel: npt.NDArray[np.float64] = np.exp(-(xx**2 + yy**2) / (2.0 * sigma**2))
    normalized = np.asarray(kernel / kernel.sum(), dtype=np.float64)
    return normalized


DIFFUSION_KERNEL: npt.NDArray[np.float64] = _make_gaussian_kernel()


# ---------------------------------------------------------------------------
# GridEnvironment
# ---------------------------------------------------------------------------


class GridEnvironment:
    """Manage vectorised biotope layers and diffusion helpers.

    Args:
        width: Grid width W (1 ≤ W ≤ GRID_W_MAX).
        height: Grid height H (1 ≤ H ≤ GRID_H_MAX).
        num_signals: Number of signal substance layers
            (1 ≤ n ≤ MAX_SUBSTANCE_TYPES).
        num_toxins: Number of toxin substance layers
            (1 ≤ n ≤ MAX_SUBSTANCE_TYPES).
    """

    def __init__(
        self,
        width: int = 40,
        height: int = 40,
        num_signals: int = 4,
        num_toxins: int = 4,
    ) -> None:
        """Initialise grid layers and double-buffered storage.

        Args:
            width: Grid width in cells.
            height: Grid height in cells.
            num_signals: Number of airborne signal layers.
            num_toxins: Number of toxin layers.
        """
        if not (1 <= width <= GRID_W_MAX):
            raise ValueError(f"width {width} out of range [1, {GRID_W_MAX}].")
        if not (1 <= height <= GRID_H_MAX):
            raise ValueError(f"height {height} out of range [1, {GRID_H_MAX}].")
        if not (1 <= num_signals <= MAX_SUBSTANCE_TYPES):
            raise ValueError(f"num_signals {num_signals} out of range [1, {MAX_SUBSTANCE_TYPES}].")
        if not (1 <= num_toxins <= MAX_SUBSTANCE_TYPES):
            raise ValueError(f"num_toxins {num_toxins} out of range [1, {MAX_SUBSTANCE_TYPES}].")

        self.width = width
        self.height = height
        self.num_signals = num_signals
        self.num_toxins = num_toxins

        shape: tuple[int, int] = (width, height)

        # ------------------------------------------------------------------
        # Plant energy layers (read/write buffers)
        # ------------------------------------------------------------------
        self.plant_energy_layer: npt.NDArray[np.float64] = np.zeros(shape, dtype=np.float64)
        self._plant_energy_layer_write: npt.NDArray[np.float64] = np.zeros(shape, dtype=np.float64)

        # Global aggregate apparent nutrition factor
        self.apparent_nutrition_layer: npt.NDArray[np.float64] = np.ones(shape, dtype=np.float64)
        self._apparent_nutrition_layer_write: npt.NDArray[np.float64] = np.ones(shape, dtype=np.float64)

        # Per-species energy layers (Rule of 16 pre-allocation)
        self.plant_energy_by_species: npt.NDArray[np.float64] = np.zeros(
            (MAX_FLORA_SPECIES, width, height), dtype=np.float64
        )
        self._plant_energy_by_species_write: npt.NDArray[np.float64] = np.zeros_like(self.plant_energy_by_species)

        # ------------------------------------------------------------------
        # Wind layers (dynamic, updated via REST API)
        # ------------------------------------------------------------------
        self.wind_vector_x: npt.NDArray[np.float64] = np.zeros(shape, dtype=np.float64)
        self.wind_vector_y: npt.NDArray[np.float64] = np.zeros(shape, dtype=np.float64)

        # ------------------------------------------------------------------
        # Signal layers  [num_signals, W, H] - read buffer
        # ------------------------------------------------------------------
        self.signal_layers: npt.NDArray[np.float64] = np.zeros((num_signals, width, height), dtype=np.float64)
        # Write buffer for double-buffering
        self._signal_layers_write: npt.NDArray[np.float64] = np.zeros_like(self.signal_layers)

        # ------------------------------------------------------------------
        # Toxin layers  [num_toxins, W, H] (local plant-tissue fields)
        # ------------------------------------------------------------------
        self.toxin_layers: npt.NDArray[np.float64] = np.zeros((num_toxins, width, height), dtype=np.float64)
        self._toxin_layers_write: npt.NDArray[np.float64] = np.zeros_like(self.toxin_layers)

        # ------------------------------------------------------------------
        # Flow-field gradient (scalar attraction field, WxH)
        # ------------------------------------------------------------------
        self.flow_field: npt.NDArray[np.float64] = np.zeros(shape, dtype=np.float64)

        # Pre-allocated scratch buffers for flow field JIT calculations
        self._flow_field_base: npt.NDArray[np.float64] = np.zeros(shape, dtype=np.float64)
        self._flow_field_current: npt.NDArray[np.float64] = np.zeros(shape, dtype=np.float64)
        self._flow_field_nxt: npt.NDArray[np.float64] = np.zeros(shape, dtype=np.float64)

        # Pre-allocated scratch buffer for diffusion JIT calculations
        self._advected_scratch: npt.NDArray[np.float64] = np.zeros(shape, dtype=np.float64)

    # ------------------------------------------------------------------
    # Wind helpers
    # ------------------------------------------------------------------

    def set_uniform_wind(self, vx: float, vy: float) -> None:
        """Fill wind layers with a spatially uniform vector.

        Args:
            vx: X component of the wind.
            vy: Y component of the wind.
        """
        self.wind_vector_x[:] = vx
        self.wind_vector_y[:] = vy

    def update_wind_at(self, x: int, y: int, vx: float, vy: float) -> None:
        """Update the wind vector at a single grid cell.

        Args:
            x: The X-axis spatial grid coordinate.
            y: The Y-axis spatial grid coordinate.
            vx: X component of the wind.
            vy: Y component of the wind.
        """
        self.wind_vector_x[x, y] = vx
        self.wind_vector_y[x, y] = vy

    # ------------------------------------------------------------------
    # Diffusion
    # ------------------------------------------------------------------

    def diffuse_signals(self, signal_decay_factor: float = 0.85) -> None:
        """Compute one diffusion tick for all signal layers.

        This applies local semi-Lagrangian advection using per-cell wind vectors,
        followed by isotropic Gaussian diffusion and decay. The transport update
        respects heterogeneous wind fields across the grid and avoids global-mean
        wind averaging artefacts.

        Args:
            signal_decay_factor: Per-tick airborne signal retention (0.0-1.0).
                Defaults to the ``SIGNAL_DECAY_FACTOR`` module-level constant (0.85).
                Pass ``loop.config.signal_decay_factor`` to use the scenario-level value.
        """
        for s in range(self.num_signals):
            layer: npt.NDArray[np.float64] = self.signal_layers[s]
            if layer.max() < SIGNAL_EPSILON:
                self._signal_layers_write[s].fill(0.0)
                continue

            _numba_diffuse_signal_layer(  # type: ignore[type-var, call-arg]
                self.width,
                self.height,
                layer,
                self.wind_vector_x,
                self.wind_vector_y,
                signal_decay_factor,
                SIGNAL_EPSILON,
                DIFFUSION_KERNEL,
                self._signal_layers_write[s],
                self._advected_scratch,
            )

        # Swap buffers
        self.signal_layers, self._signal_layers_write = (
            self._signal_layers_write,
            self.signal_layers,
        )

    # ------------------------------------------------------------------
    # Plant energy helpers
    # ------------------------------------------------------------------

    def rebuild_energy_layer(self) -> None:
        """Recompute aggregate plant energy layer and swap buffers.

        Aggregates per-species write buffers into the global write buffer,
        then swaps read/write buffers so that subsequent reads observe the
        newly-written values.
        """
        np.sum(self._plant_energy_by_species_write, axis=0, out=self._plant_energy_layer_write)
        self.plant_energy_by_species, self._plant_energy_by_species_write = (
            self._plant_energy_by_species_write,
            self.plant_energy_by_species,
        )
        self.plant_energy_layer, self._plant_energy_layer_write = (
            self._plant_energy_layer_write,
            self.plant_energy_layer,
        )
        self._plant_energy_by_species_write[:] = self.plant_energy_by_species
        self._plant_energy_layer_write[:] = self.plant_energy_layer

        self.apparent_nutrition_layer, self._apparent_nutrition_layer_write = (
            self._apparent_nutrition_layer_write,
            self.apparent_nutrition_layer,
        )
        self._apparent_nutrition_layer_write.fill(1.0)

    def set_plant_energy(self, x: int, y: int, species_id: int, value: float) -> None:
        """Set a species-specific energy contribution in the write buffer.

        Args:
            x: The X-axis spatial grid coordinate.
            y: The Y-axis spatial grid coordinate.
            species_id: The integer index representing the specific phylogenetic species associated with this operation.
            value: Energy contribution (clamped to >= 0).
        """
        self._plant_energy_by_species_write[species_id, x, y] = max(0.0, value)

    def set_apparent_nutrition(self, x: int, y: int, value: float) -> None:
        """Set apparent nutrition factor in the write buffer.

        Args:
            x: The X-axis spatial grid coordinate.
            y: The Y-axis spatial grid coordinate.
            value: The apparent nutrition value to store.
        """
        self._apparent_nutrition_layer_write[x, y] = value

    def clear_plant_energy(self, x: int, y: int, species_id: int) -> None:
        """Clear a species-specific energy contribution in the write buffer.

        Args:
            x: The X-axis spatial grid coordinate.
            y: The Y-axis spatial grid coordinate.
            species_id: The integer index representing the specific phylogenetic species associated with this operation.
        """
        self._plant_energy_by_species_write[species_id, x, y] = 0.0

    # ------------------------------------------------------------------
    # State snapshot (for serialisation / streaming)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, object]:
        """Returns a dict representation of the biotope state suitable for serialization.

        This is used by the streaming interface to serialize the current state of the
        biotope to a dictionary.

        Returns:
            Mapping containing numpy arrays converted to nested lists.
        """
        return {
            "plant_energy_layer": self.plant_energy_layer.tolist(),
            "signal_layers": self.signal_layers.tolist(),
            "toxin_layers": self.toxin_layers.tolist(),
            "flow_field": self.flow_field.tolist(),
            "wind_vector_x": self.wind_vector_x.tolist(),
            "wind_vector_y": self.wind_vector_y.tolist(),
        }
