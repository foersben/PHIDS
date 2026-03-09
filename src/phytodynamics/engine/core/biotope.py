"""GridEnvironment: NumPy-backed biotope with SciPy 2-D convolution diffusion.

All cellular automata layers are pre-allocated according to the Rule of 16.
Double-buffering (read/write pair) is enforced to prevent race conditions.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
from scipy.signal import convolve2d  # type: ignore[import-untyped]

from phytodynamics.shared.constants import (
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
_SIGMA: float = 0.8


def _make_gaussian_kernel(
    size: int = _KERNEL_SIZE, sigma: float = _SIGMA
) -> npt.NDArray[np.float64]:
    """Return a normalised 2-D Gaussian kernel for VOC diffusion."""
    ax = np.arange(-(size // 2), size // 2 + 1, dtype=np.float64)
    xx, yy = np.meshgrid(ax, ax)
    kernel: npt.NDArray[np.float64] = np.exp(-(xx**2 + yy**2) / (2.0 * sigma**2))
    return kernel / kernel.sum()


DIFFUSION_KERNEL: npt.NDArray[np.float64] = _make_gaussian_kernel()


# ---------------------------------------------------------------------------
# GridEnvironment
# ---------------------------------------------------------------------------


class GridEnvironment:
    """Manages all vectorised biotope layers for the PHIDS simulation.

    Parameters
    ----------
    width:
        Grid width W (1 ≤ W ≤ GRID_W_MAX).
    height:
        Grid height H (1 ≤ H ≤ GRID_H_MAX).
    num_signals:
        Number of signal substance layers (1 ≤ n ≤ MAX_SUBSTANCE_TYPES).
    num_toxins:
        Number of toxin substance layers (1 ≤ n ≤ MAX_SUBSTANCE_TYPES).
    """

    def __init__(
        self,
        width: int = 40,
        height: int = 40,
        num_signals: int = 4,
        num_toxins: int = 4,
    ) -> None:
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
        # Plant energy layer – read buffer
        # ------------------------------------------------------------------
        self.plant_energy_layer: npt.NDArray[np.float64] = np.zeros(shape, dtype=np.float64)

        # Per-species energy layers (Rule of 16 pre-allocation)
        self.plant_energy_by_species: npt.NDArray[np.float64] = np.zeros(
            (MAX_FLORA_SPECIES, width, height), dtype=np.float64
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
        # Toxin layers  [num_toxins, W, H]
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
        """Fill wind layers with a spatially uniform vector (vx, vy)."""
        self.wind_vector_x[:] = vx
        self.wind_vector_y[:] = vy

    def update_wind_at(self, x: int, y: int, vx: float, vy: float) -> None:
        """Update the wind vector at a single grid cell."""
        self.wind_vector_x[x, y] = vx
        self.wind_vector_y[x, y] = vy

    # ------------------------------------------------------------------
    # Diffusion
    # ------------------------------------------------------------------

    def diffuse_signals(self) -> None:
        """Compute one diffusion tick for all signal layers.

        Uses SciPy 2-D convolution with the pre-computed Gaussian kernel,
        then applies a wind shift and enforces the SIGNAL_EPSILON sparsity
        threshold to prevent subnormal float accumulation.
        """
        # Compute mean wind shift (integer pixel shift for np.roll)
        mean_vx: int = int(round(float(self.wind_vector_x.mean())))
        mean_vy: int = int(round(float(self.wind_vector_y.mean())))

        for s in range(self.num_signals):
            layer: npt.NDArray[np.float64] = self.signal_layers[s]
            convolved: npt.NDArray[np.float64] = convolve2d(
                layer, DIFFUSION_KERNEL, mode="same", boundary="fill", fillvalue=0.0
            )
            # Wind advection via cyclic roll
            shifted: npt.NDArray[np.float64] = np.roll(
                np.roll(convolved, mean_vx, axis=0), mean_vy, axis=1
            )
            # Zero sub-threshold values to preserve matrix sparsity
            shifted[shifted < SIGNAL_EPSILON] = 0.0
            self._signal_layers_write[s] = shifted

        # Swap buffers
        self.signal_layers, self._signal_layers_write = (
            self._signal_layers_write,
            self.signal_layers,
        )

    def diffuse_toxins(self) -> None:
        """Compute one diffusion tick for all toxin layers.

        Toxins diffuse identically to signals but dissipate completely
        when their triggering condition ceases (handled externally by the
        signaling system).  Here we apply convolution and epsilon threshold.
        """
        mean_vx: int = int(round(float(self.wind_vector_x.mean())))
        mean_vy: int = int(round(float(self.wind_vector_y.mean())))

        for t in range(self.num_toxins):
            layer: npt.NDArray[np.float64] = self.toxin_layers[t]
            convolved: npt.NDArray[np.float64] = convolve2d(
                layer, DIFFUSION_KERNEL, mode="same", boundary="fill", fillvalue=0.0
            )
            shifted: npt.NDArray[np.float64] = np.roll(
                np.roll(convolved, mean_vx, axis=0), mean_vy, axis=1
            )
            shifted[shifted < SIGNAL_EPSILON] = 0.0
            self._toxin_layers_write[t] = shifted

        self.toxin_layers, self._toxin_layers_write = (
            self._toxin_layers_write,
            self.toxin_layers,
        )

    # ------------------------------------------------------------------
    # Plant energy helpers
    # ------------------------------------------------------------------

    def rebuild_energy_layer(self) -> None:
        """Recompute aggregate plant_energy_layer from per-species slices."""
        self.plant_energy_layer[:] = self.plant_energy_by_species.sum(axis=0)

    def set_plant_energy(self, x: int, y: int, species_id: int, value: float) -> None:
        """Set the energy contribution of a specific species at (x, y)."""
        self.plant_energy_by_species[species_id, x, y] = max(0.0, value)

    def clear_plant_energy(self, x: int, y: int, species_id: int) -> None:
        """Remove a plant's energy contribution (on death)."""
        self.plant_energy_by_species[species_id, x, y] = 0.0

    # ------------------------------------------------------------------
    # State snapshot (for serialisation / streaming)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, object]:
        """Return a lightweight dict snapshot suitable for msgpack serialisation."""
        return {
            "plant_energy_layer": self.plant_energy_layer.tolist(),
            "signal_layers": self.signal_layers.tolist(),
            "toxin_layers": self.toxin_layers.tolist(),
            "flow_field": self.flow_field.tolist(),
            "wind_vector_x": self.wind_vector_x.tolist(),
            "wind_vector_y": self.wind_vector_y.tolist(),
        }
