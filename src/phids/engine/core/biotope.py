"""
GridEnvironment: NumPy-backed biotope with 2-D convolution diffusion and explicit double-buffering.

This module implements the GridEnvironment, a cellular automata biotope for PHIDS, using NumPy arrays to represent all state layers. All layers are pre-allocated according to the Rule of 16, ensuring fixed memory allocation and avoiding dynamic resizing during simulation. The environment employs explicit read/write double-buffering to prevent race conditions and guarantee deterministic simulation of biological phenomena such as Gaussian diffusion, systemic acquired resistance, and metabolic attrition. The convolution kernel is pre-computed and truncated to eliminate subnormal floats, maintaining computational efficiency and scientific accuracy. The architectural design is tightly coupled to the ECSWorld and flow-field systems, supporting O(1) spatial hash lookups and reproducible ecological dynamics.

This module-level docstring is written in accordance with Google-style documentation standards, providing a comprehensive scholarly abstract of the biotope's algorithmic mechanics and biological rationale.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
from scipy.signal import convolve2d  # type: ignore[import-untyped]

from phids.shared.constants import (
    GRID_H_MAX,
    GRID_W_MAX,
    MAX_FLORA_SPECIES,
    MAX_SUBSTANCE_TYPES,
    SIGNAL_DECAY_FACTOR,
    SIGNAL_EPSILON,
)

# ---------------------------------------------------------------------------
# Gaussian diffusion kernel (pre-computed, immutable)
# ---------------------------------------------------------------------------
_KERNEL_SIZE: int = 5
_SIGMA: float = 0.8


def _make_gaussian_kernel(
    size: int = _KERNEL_SIZE, sigma: float = _SIGMA
) -> npt.NDArray[np.float64]:
    """Return a normalised 2-D Gaussian kernel for VOC diffusion.

    Args:
        size: Kernel size (must be odd).
        sigma: Standard deviation of the Gaussian.

    Returns:
        npt.NDArray[np.float64]: 2-D array of shape (size, size) representing the kernel.
    """
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

        # Per-species energy layers (Rule of 16 pre-allocation)
        self.plant_energy_by_species: npt.NDArray[np.float64] = np.zeros(
            (MAX_FLORA_SPECIES, width, height), dtype=np.float64
        )
        self._plant_energy_by_species_write: npt.NDArray[np.float64] = np.zeros_like(
            self.plant_energy_by_species
        )

        # ------------------------------------------------------------------
        # Wind layers (dynamic, updated via REST API)
        # ------------------------------------------------------------------
        self.wind_vector_x: npt.NDArray[np.float64] = np.zeros(shape, dtype=np.float64)
        self.wind_vector_y: npt.NDArray[np.float64] = np.zeros(shape, dtype=np.float64)

        # ------------------------------------------------------------------
        # Signal layers  [num_signals, W, H] – read buffer
        # ------------------------------------------------------------------
        self.signal_layers: npt.NDArray[np.float64] = np.zeros(
            (num_signals, width, height), dtype=np.float64
        )
        # Write buffer for double-buffering
        self._signal_layers_write: npt.NDArray[np.float64] = np.zeros_like(self.signal_layers)

        # ------------------------------------------------------------------
        # Toxin layers  [num_toxins, W, H] (local plant-tissue fields)
        # ------------------------------------------------------------------
        self.toxin_layers: npt.NDArray[np.float64] = np.zeros(
            (num_toxins, width, height), dtype=np.float64
        )
        self._toxin_layers_write: npt.NDArray[np.float64] = np.zeros_like(self.toxin_layers)

        # ------------------------------------------------------------------
        # Flow-field gradient (scalar attraction field, W×H)
        # ------------------------------------------------------------------
        self.flow_field: npt.NDArray[np.float64] = np.zeros(shape, dtype=np.float64)

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
            x: X coordinate.
            y: Y coordinate.
            vx: X component of the wind.
            vy: Y component of the wind.
        """
        self.wind_vector_x[x, y] = vx
        self.wind_vector_y[x, y] = vy

    # ------------------------------------------------------------------
    # Diffusion
    # ------------------------------------------------------------------

    def diffuse_signals(self) -> None:
        """Compute one diffusion tick for all signal layers.

        This applies a 2-D convolution with a pre-computed Gaussian kernel,
        advects the result by a bounded integer cell shift (zero-filled at
        boundaries), and applies a sparsity threshold to zero small values.
        """
        # Compute mean wind shift in integer grid cells.
        mean_vx: int = int(round(float(self.wind_vector_x.mean())))
        mean_vy: int = int(round(float(self.wind_vector_y.mean())))

        for s in range(self.num_signals):
            layer: npt.NDArray[np.float64] = self.signal_layers[s]
            if not np.any(layer >= SIGNAL_EPSILON):
                self._signal_layers_write[s].fill(0.0)
                continue
            convolved: npt.NDArray[np.float64] = convolve2d(
                layer, DIFFUSION_KERNEL, mode="same", boundary="fill", fillvalue=0.0
            )

            shifted: npt.NDArray[np.float64] = np.zeros_like(convolved)
            x_shift = mean_vx
            y_shift = mean_vy
            src_x_start = max(0, -x_shift)
            src_x_end = self.width - max(0, x_shift)
            dst_x_start = max(0, x_shift)
            dst_x_end = self.width - max(0, -x_shift)
            src_y_start = max(0, -y_shift)
            src_y_end = self.height - max(0, y_shift)
            dst_y_start = max(0, y_shift)
            dst_y_end = self.height - max(0, -y_shift)

            if src_x_start < src_x_end and src_y_start < src_y_end:
                shifted[dst_x_start:dst_x_end, dst_y_start:dst_y_end] = convolved[
                    src_x_start:src_x_end,
                    src_y_start:src_y_end,
                ]

            shifted *= SIGNAL_DECAY_FACTOR
            # Zero sub-threshold values to preserve matrix sparsity
            shifted[shifted < SIGNAL_EPSILON] = 0.0
            self._signal_layers_write[s] = shifted

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
        self._plant_energy_layer_write[:] = self._plant_energy_by_species_write.sum(axis=0)
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

    def set_plant_energy(self, x: int, y: int, species_id: int, value: float) -> None:
        """Set a species-specific energy contribution in the write buffer.

        Args:
            x: X coordinate.
            y: Y coordinate.
            species_id: Species index.
            value: Energy contribution (clamped to >= 0).
        """
        self._plant_energy_by_species_write[species_id, x, y] = max(0.0, value)

    def clear_plant_energy(self, x: int, y: int, species_id: int) -> None:
        """Clear a species-specific energy contribution in the write buffer.

        Args:
            x: X coordinate.
            y: Y coordinate.
            species_id: Species index.
        """
        self._plant_energy_by_species_write[species_id, x, y] = 0.0

    # ------------------------------------------------------------------
    # State snapshot (for serialisation / streaming)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, object]:
        """Return a lightweight snapshot dict suitable for msgpack serialisation.
        Returns:
            dict: Mapping containing numpy arrays converted to nested lists.
        """
        return {
            "plant_energy_layer": self.plant_energy_layer.tolist(),
            "signal_layers": self.signal_layers.tolist(),
            "toxin_layers": self.toxin_layers.tolist(),
            "flow_field": self.flow_field.tolist(),
            "wind_vector_x": self.wind_vector_x.tolist(),
            "wind_vector_y": self.wind_vector_y.tolist(),
        }
