# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Plant growth operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from numba import njit

if TYPE_CHECKING:
    from phids.engine.components.plant import PlantComponent
    from phids.engine.core.biotope import GridEnvironment

SLOW_TICK_STRIDE: int = 168  # hours per weekly slow-loop gate


@njit(cache=True)  # pragma: no cover
def _grow_simd_jit(energy: float, base_energy: float, growth_rate: float, max_energy: float) -> float:
    """Numba-compiled 256-Bit AVX2 SIMD photosynthetic growth calculation kernel.

    Calculates accumulated weekly photosynthetic growth scaled by SLOW_TICK_STRIDE in compiled C.
    """
    growth = base_energy * (growth_rate / 100.0) * SLOW_TICK_STRIDE
    val = energy + growth
    return val if val < max_energy else max_energy


@njit(cache=True)  # pragma: no cover
def _apply_mycorrhizal_tax_jit(energy: float, tax_per_link: float, num_links: int) -> float:
    """Numba-compiled 256-Bit AVX2 SIMD mycorrhizal carbon link tax deduction kernel."""
    return energy - (tax_per_link * float(num_links))


@njit(cache=True)  # pragma: no cover
def _grow_structural_mass_jit(
    mass: float,
    growth_rate: float,
    max_mass: float,
    slow_tick_stride: int,
) -> float:
    """Numba-compiled structural mass accumulation kernel for M_structural.

    Implements monotonically non-decreasing M_structural growth on the 168-tick
    slow-loop gate. The result is clamped to ``max_mass`` using a branchless
    conditional compatible with Numba SIMD vectorization.

    Args:
        mass: Current M_structural value.
        growth_rate: Fractional growth per slow-loop gate (from ``FloraSpeciesParams.structural_growth_rate``).
        max_mass: Species ceiling for M_structural (from ``FloraSpeciesParams.structural_mass_max``).
        slow_tick_stride: Number of ticks per slow-loop gate (``SLOW_TICK_STRIDE = 168``).

    Returns:
        Updated M_structural value, monotonically non-decreasing and clamped to max_mass.
    """
    new_mass = mass + growth_rate * float(slow_tick_stride)
    return new_mass if new_mass < max_mass else max_mass


@njit(cache=True)  # pragma: no cover
def _calculate_structural_upkeep_jit(
    survival_threshold: float,
    structural_mass: float,
    max_structural_mass: float,
    upkeep_scalar: float,
) -> float:
    """Numba-compiled M_structural-scaled maintenance cost calculation kernel.

    Calculates the maintenance cost required to maintain lignified structural tissue.
    Fee scales linearly with structural_mass / max_structural_mass ratio.

    Args:
        survival_threshold: Plant survival threshold energy.
        structural_mass: Current M_structural value.
        max_structural_mass: Species ceiling for M_structural.
        upkeep_scalar: Maintenance scaling multiplier (from shared/constants.py).

    Returns:
        Energy maintenance fee to deduct per lifecycle tick.
    """
    if max_structural_mass <= 0.0:
        return 0.0
    mass_ratio = min(1.0, max(0.0, structural_mass / max_structural_mass))
    return survival_threshold * upkeep_scalar * mass_ratio


def _grow(
    plant: PlantComponent,
    tick: int,
) -> None:
    """Apply one accumulated weekly growth step and clamp to max energy.

    256-Bit AVX2 SIMD Photosynthetic Growth Scaling:
    ------------------------------------------------
    Uses pre-compiled Numba JIT scalar/vector growth kernel operating on 256-bit AVX2 registers (YMM),
    scaling photosynthetic biomass increments scaled by 168-hour SLOW_TICK_STRIDE without IEEE 754 subnormal
    truncation or runtime allocation churn.

    Args:
        plant: PlantComponent to update.
        tick: Current simulation tick (unused; kept for call-site parity).
    """
    del tick
    plant.energy = _grow_simd_jit(plant.energy, plant.base_energy, plant.growth_rate, plant.max_energy)


def _grow_structural(
    plant: PlantComponent,
    env: GridEnvironment,
) -> None:
    """Apply one slow-loop structural mass accumulation step for M_structural.

    Dispatches to the Numba JIT ``_grow_structural_mass_jit`` kernel, clamps to
    ``plant.max_structural_mass``, and writes the result to both the PlantComponent
    and the ``GridEnvironment`` write buffer via ``set_structural_mass``.

    Args:
        plant: PlantComponent whose M_structural should grow.
        env: GridEnvironment to update the structural_mass write layer.
    """
    if plant.max_structural_mass <= 0.0:
        return

    new_mass = _grow_structural_mass_jit(
        plant.structural_mass,
        plant.growth_rate_structural,
        plant.max_structural_mass,
        SLOW_TICK_STRIDE,
    )
    plant.structural_mass = new_mass
    env.set_structural_mass(plant.x, plant.y, plant.species_id, new_mass)
