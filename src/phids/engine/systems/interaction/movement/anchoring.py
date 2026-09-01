"""Anchoring evaluation for movement system."""

from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt
from numba import njit

if TYPE_CHECKING:
    from phids.engine.components.swarm import SwarmComponent
    from phids.engine.core.biotope import GridEnvironment


@njit(cache=True)
def _is_swarm_anchored_jit(
    x: int,
    y: int,
    species_id: int,
    apparent_nutrition_val: float,
    plant_energy_by_species: npt.NDArray[np.float64],
    diet_matrix: npt.NDArray[np.bool_],
    caloric_intake: float = 0.0,
    metabolic_upkeep: float = 0.0,
    rand_val: float = 0.0,
) -> bool:
    """Numba-compiled fast collision check for swarm anchoring on compatible uneaten flora.

    Evaluates co-located plant energy layers using a pre-compiled boolean diet matrix,
    eliminating Python list iteration and NumPy `.item()` scalar conversion overhead.
    Evaluates a stochastic departure curve based on the Marginal Value Theorem (MVT).

    Args:
        x: X-coordinate of the swarm.
        y: Y-coordinate of the swarm.
        species_id: Species identifier of the swarm.
        apparent_nutrition_val: Current apparent nutrition level at (x, y).
        plant_energy_by_species: 3D array of plant energy levels [num_flora_species, W, H].
        diet_matrix: 2D boolean array of diet compatibility [num_herbivore_species, num_flora_species].
        caloric_intake: Total calories consumed in the last tick.
        metabolic_upkeep: Swarm's minimum caloric requirements.
        rand_val: A random float in [0.0, 1.0) for stochastic departure evaluation.

    Returns:
        True if the swarm anchors, False otherwise.
    """
    if apparent_nutrition_val <= 0.0:
        return False

    num_herbivores, num_flora = diet_matrix.shape
    if species_id >= num_herbivores:
        return False

    for flora_species_id in range(num_flora):
        if diet_matrix[species_id, flora_species_id]:
            if plant_energy_by_species[flora_species_id, x, y] > 0.0:
                # Stochastic MVT Departure
                if metabolic_upkeep > 0.0:
                    ratio = caloric_intake / metabolic_upkeep
                    p_depart = 1.0 / (1.0 + np.exp(5.0 * (ratio - 1.0)))
                    if rand_val < p_depart:
                        return False
                return True
    return False


def _is_swarm_anchored(
    swarm: "SwarmComponent",
    env: "GridEnvironment",
    diet_matrix: list[list[bool]] | npt.NDArray[np.bool_],
    rand_val: float = 0.0,
) -> bool:
    """Return True if swarm is currently co-located with compatible uneaten food or full belly.

    Numba JIT Anchoring Resolution & Array Scalar Extraction Avoidance:
    ------------------------------------------------------------------
    Evaluating herbivore anchoring via Python list iteration and dynamic NumPy `.item()` scalar calls
    on every movement tick induces interpreter overhead. Dispatching to `_is_swarm_anchored_jit`
    evaluates 3D species energy arrays and 2D boolean diet matrices in compiled C, eliminating
    object creation and scalar extraction overhead in the movement hot path.

    Args:
        swarm: The swarm component.
        env: The grid environment.
        diet_matrix: The boolean diet matrix (2D NumPy array or list of lists).
        rand_val: A random float in [0.0, 1.0) for stochastic departure evaluation.

    Returns:
        True if the swarm is anchored, False otherwise.
    """
    # Optimized: direct attribute access avoids getattr overhead in hot loop
    intake = float(swarm.last_caloric_intake)
    upkeep = float(swarm.metabolism_upkeep)

    if isinstance(diet_matrix, np.ndarray):
        return _is_swarm_anchored_jit(
            swarm.x,
            swarm.y,
            swarm.species_id,
            float(env.apparent_nutrition_layer[swarm.x, swarm.y]),
            env.plant_energy_by_species,
            diet_matrix,
            caloric_intake=intake,
            metabolic_upkeep=upkeep,
            rand_val=rand_val,
        )

    diet_arr = np.array(diet_matrix, dtype=np.bool_)
    return _is_swarm_anchored_jit(
        swarm.x,
        swarm.y,
        swarm.species_id,
        float(env.apparent_nutrition_layer[swarm.x, swarm.y]),
        env.plant_energy_by_species,
        diet_arr,
        caloric_intake=intake,
        metabolic_upkeep=upkeep,
        rand_val=rand_val,
    )
