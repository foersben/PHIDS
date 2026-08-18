"""Movement and pathfinding logic for swarms in the interaction system.

This package contains helper functions to move swarms from one tile to another, including flow-field based movement and
neighbour-based movement.

Numba `@njit`-compiled helper functions ensure high-performance execution of the critically-threaded movement routines,
minimising CPU branch mispredictions through branchless SIMD-friendly arithmetic where feasible.
"""

from phids.engine.systems.interaction.movement.core import (
    _choose_neighbour_by_flow_probability,
    _choose_neighbour_by_flow_probability_python,
    _is_swarm_anchored,
    _python_flat_field_choice,
    _random_walk_step,
    _resolve_incidental_mortality,
    _resolve_swarm_movement,
)
from phids.engine.systems.interaction.movement.math import (
    _apply_branchless_capacity_mask_jit,
    _choose_neighbour_by_flow_probability_jit,
    _compute_trample_probability_jit,
    _flat_field_choice_jit,
    _gather_neighbours_jit,
    _gather_neighbours_jit_pow2,
    _is_swarm_anchored_jit,
    _random_walk_step_jit,
    _weighted_field_choice_jit,
)

__all__ = [
    "_apply_branchless_capacity_mask_jit",
    "_choose_neighbour_by_flow_probability",
    "_choose_neighbour_by_flow_probability_jit",
    "_choose_neighbour_by_flow_probability_python",
    "_compute_trample_probability_jit",
    "_flat_field_choice_jit",
    "_gather_neighbours_jit",
    "_gather_neighbours_jit_pow2",
    "_is_swarm_anchored",
    "_is_swarm_anchored_jit",
    "_python_flat_field_choice",
    "_random_walk_step",
    "_random_walk_step_jit",
    "_resolve_incidental_mortality",
    "_resolve_swarm_movement",
    "_weighted_field_choice_jit",
]
