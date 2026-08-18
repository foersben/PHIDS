# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Movement and pathfinding logic for swarms in the interaction system.

This package contains helper functions to move swarms from one tile to another, including flow-field based movement and
neighbour-based movement.

Numba `@njit`-compiled helper functions ensure high-performance execution of the critically-threaded movement routines,
minimising CPU branch mispredictions through branchless SIMD-friendly arithmetic where feasible.
"""

from phids.engine.systems.interaction.movement.anchoring import _is_swarm_anchored as _is_swarm_anchored
from phids.engine.systems.interaction.movement.anchoring import _is_swarm_anchored_jit as _is_swarm_anchored_jit
from phids.engine.systems.interaction.movement.capacity import (
    _apply_branchless_capacity_mask_jit as _apply_branchless_capacity_mask_jit,
)
from phids.engine.systems.interaction.movement.choices import (
    _choose_neighbour_by_flow_probability as _choose_neighbour_by_flow_probability,
)
from phids.engine.systems.interaction.movement.choices import (
    _choose_neighbour_by_flow_probability_jit as _choose_neighbour_by_flow_probability_jit,
)
from phids.engine.systems.interaction.movement.choices import (
    _choose_neighbour_by_flow_probability_python as _choose_neighbour_by_flow_probability_python,
)
from phids.engine.systems.interaction.movement.choices import _flat_field_choice_jit as _flat_field_choice_jit
from phids.engine.systems.interaction.movement.choices import _python_flat_field_choice as _python_flat_field_choice
from phids.engine.systems.interaction.movement.choices import (
    _python_weighted_field_choice as _python_weighted_field_choice,
)
from phids.engine.systems.interaction.movement.choices import _softmax_field_choice_jit as _softmax_field_choice_jit
from phids.engine.systems.interaction.movement.choices import _weighted_field_choice_jit as _weighted_field_choice_jit
from phids.engine.systems.interaction.movement.core import _resolve_swarm_movement as _resolve_swarm_movement
from phids.engine.systems.interaction.movement.incidental import (
    _compute_trample_probability_jit as _compute_trample_probability_jit,
)
from phids.engine.systems.interaction.movement.incidental import (
    _resolve_incidental_mortality as _resolve_incidental_mortality,
)
from phids.engine.systems.interaction.movement.neighbors import _calculate_toroidal_delta as _calculate_toroidal_delta
from phids.engine.systems.interaction.movement.neighbors import _gather_neighbours_jit as _gather_neighbours_jit
from phids.engine.systems.interaction.movement.neighbors import (
    _gather_neighbours_jit_pow2 as _gather_neighbours_jit_pow2,
)
from phids.engine.systems.interaction.movement.random_walk import _random_walk_step as _random_walk_step
from phids.engine.systems.interaction.movement.random_walk import _random_walk_step_jit as _random_walk_step_jit

__all__ = [
    "_apply_branchless_capacity_mask_jit",
    "_calculate_toroidal_delta",
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
    "_python_weighted_field_choice",
    "_random_walk_step",
    "_random_walk_step_jit",
    "_resolve_incidental_mortality",
    "_resolve_swarm_movement",
    "_softmax_field_choice_jit",
    "_weighted_field_choice_jit",
]
