# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Flow-field directional choice logic (Python fallbacks)."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import numpy as np

from phids.shared.constants import ORTHOKINETIC_MOMENTUM_WEIGHT

from .jit import _choose_neighbour_by_flow_probability_jit

if TYPE_CHECKING:
    import numpy.typing as npt

    from phids.engine.components.swarm import SwarmComponent

_orig_choices = random.choices
_orig_choice = random.choice


def _python_flat_field_choice(
    swarm: SwarmComponent,
    candidates: list[tuple[int, int]],
) -> tuple[int, int]:
    """Helper to choose from flat field candidates using inertia direction or random choice.

    Args:
        swarm: The swarm component.
        candidates: List of candidate coordinates.

    Returns:
        The selected neighbour coordinates.
    """
    if swarm.last_dx == 0 and swarm.last_dy == 0:
        return random.choice(candidates)

    target_x = swarm.x + swarm.last_dx
    target_y = swarm.y + swarm.last_dy
    weights = [ORTHOKINETIC_MOMENTUM_WEIGHT if (cx == target_x and cy == target_y) else 1.0 for cx, cy in candidates]
    return random.choices(candidates, weights=weights, k=1)[0]


def _python_weighted_field_choice(
    scores: list[float],
    candidates: list[tuple[int, int]],
    invert: bool,
) -> tuple[int, int]:
    """Helper to choose from non-flat field candidates using flow probability weights.

    Args:
        scores: List of flow field scores.
        candidates: List of candidate coordinates.
        invert: Whether to invert the scores.

    Returns:
        The selected neighbour coordinates.
    """
    adjusted_scores = [-score for score in scores] if invert else scores
    min_score = min(adjusted_scores)
    weights = [(score - min_score) + 1e-6 for score in adjusted_scores]
    return random.choices(candidates, weights=weights, k=1)[0]


def _choose_neighbour_by_flow_probability_python(
    swarm: SwarmComponent,
    flow_field: npt.NDArray[np.float64],
    width: int,
    height: int,
    invert: bool,
) -> tuple[int, int]:
    """Fallback Python logic when random choice is mocked.

    Args:
        swarm: The swarm component.
        flow_field: The flow field.
        width: The width of the grid environment.
        height: The height of the grid environment.
        invert: Whether to invert the flow field.

    Returns:
        The selected neighbour coordinates.
    """
    x, y = swarm.x, swarm.y
    candidates: list[tuple[int, int]] = [(x, y)]
    candidates.append(((x - 1) % width, y))
    candidates.append(((x + 1) % width, y))
    candidates.append((x, (y - 1) % height))
    candidates.append((x, (y + 1) % height))

    scores = [float(flow_field[cx, cy]) for cx, cy in candidates]
    max_score = max(scores)
    min_score = min(scores)

    if max_score - min_score < 1e-6:
        return _python_flat_field_choice(swarm, candidates)

    return _python_weighted_field_choice(scores, candidates, invert)


def _choose_neighbour_by_flow_probability(
    swarm: SwarmComponent,
    flow_field: npt.NDArray[np.float64],
    width: int,
    height: int,
    c_x: npt.NDArray[np.int32],
    c_y: npt.NDArray[np.int32],
    scores: npt.NDArray[np.float64],
    adjusted_scores: npt.NDArray[np.float64],
    weights: npt.NDArray[np.float64],
    invert: bool = False,
    tile_populations: npt.NDArray[np.int32] | list[int] | None = None,
    tau: float = 0.0,
) -> tuple[int, int]:
    """Select a 4-connected Von-Neumann neighbour via flow-field-weighted JIT selection.

    Uses branchless capacity masking to prevent over-occupancy.

    Args:
        swarm: The swarm component.
        flow_field: Array of flow-field gradient values.
        width: The width of the grid environment.
        height: The height of the grid environment.
        c_x: Pre-allocated scratch array for x-coordinates.
        c_y: Pre-allocated scratch array for y-coordinates.
        scores: Pre-allocated scratch array for flow scores.
        adjusted_scores: Pre-allocated scratch array for adjusted scores.
        weights: Pre-allocated scratch array for sampling weights.
        invert: Whether to invert the flow-field gradient scores.
        tile_populations: Tile population array for branchless capacity masking.
        tau: Softmax temperature parameter. 0.0 uses legacy linear weighted selection.

    Returns:
        The selected neighbour coordinates.
    """
    if random.choices is not _orig_choices or random.choice is not _orig_choice:
        return _choose_neighbour_by_flow_probability_python(swarm, flow_field, width, height, invert)

    tile_pop_arr: npt.NDArray[np.int32] | None = None
    if isinstance(tile_populations, np.ndarray):
        tile_pop_arr = tile_populations
    elif isinstance(tile_populations, list):
        tile_pop_arr = np.array(tile_populations, dtype=np.int32)

    return _choose_neighbour_by_flow_probability_jit(
        swarm.x,
        swarm.y,
        swarm.last_dx,
        swarm.last_dy,
        flow_field,
        width,
        height,
        invert,
        c_x,
        c_y,
        scores,
        adjusted_scores,
        weights,
        random.random(),
        tile_populations=tile_pop_arr,
        tau=tau,
    )
