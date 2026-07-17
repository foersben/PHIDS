# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Movement and pathfinding logic for swarms in the interaction system."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from numba import njit

from phids.engine.components.plant import PlantComponent
from phids.engine.systems.interaction.population import TILE_CARRYING_CAPACITY, _accumulate_tile_population

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt

    from phids.engine.components.swarm import SwarmComponent
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld, Entity

_orig_choice = random.choice
_orig_choices = random.choices


@njit(cache=True)
def _gather_neighbours_jit(
    x: int,
    y: int,
    width: int,
    height: int,
    c_x: npt.NDArray[np.int32],
    c_y: npt.NDArray[np.int32],
) -> int:
    """Numba-compiled helper function to gather neighbours of a cell.

    Args:
        x: The x coordinate of the cell.
        y: The y coordinate of the cell.
        width: The width of the grid environment.
        height: The height of the grid environment.
        c_x: Array to store the x coordinates of the neighbours.
        c_y: Array to store the y coordinates of the neighbours.

    Returns:
        The number of neighbours.
    """
    c_x[0] = x
    c_y[0] = y
    count = 1

    if x > 0:
        c_x[count] = x - 1
        c_y[count] = y
        count += 1
    if x < width - 1:
        c_x[count] = x + 1
        c_y[count] = y
        count += 1
    if y > 0:
        c_x[count] = x
        c_y[count] = y - 1
        count += 1
    if y < height - 1:
        c_x[count] = x
        c_y[count] = y + 1
        count += 1
    return count


@njit(cache=True)
def _flat_field_choice_jit(
    count: int,
    x: int,
    y: int,
    last_dx: int,
    last_dy: int,
    c_x: npt.NDArray[np.int32],
    c_y: npt.NDArray[np.int32],
    weights: npt.NDArray[np.float64],
    rand_val: float,
) -> tuple[int, int]:
    """Numba-compiled helper function to select a neighbour based on flow-field gradient.

    Args:
        count: The number of neighbours.
        x: The x coordinate of the cell.
        y: The y coordinate of the cell.
        last_dx: The last x delta.
        last_dy: The last y delta.
        c_x: Array to store the x coordinates of the neighbours.
        c_y: Array to store the y coordinates of the neighbours.
        weights: Pre-allocated array for flow-field weights.
        rand_val: Random value for weighted choice.

    Returns:
        The selected neighbour coordinates.
    """
    if last_dx == 0 and last_dy == 0:
        idx = int(rand_val * count)
        if idx >= count:
            idx = count - 1
        return c_x[idx], c_y[idx]

    target_x = x + last_dx
    target_y = y + last_dy
    total_w = 0.0
    for i in range(count):
        if c_x[i] == target_x and c_y[i] == target_y:
            weights[i] = 10.0
        else:
            weights[i] = 1.0
        total_w += weights[i]

    r = rand_val * total_w
    cum = 0.0
    for i in range(count):
        cum += weights[i]
        if r <= cum:
            return c_x[i], c_y[i]
    return c_x[count - 1], c_y[count - 1]


@njit(cache=True)
def _weighted_field_choice_jit(
    count: int,
    invert: bool,
    scores: npt.NDArray[np.float64],
    c_x: npt.NDArray[np.int32],
    c_y: npt.NDArray[np.int32],
    adjusted_scores: npt.NDArray[np.float64],
    weights: npt.NDArray[np.float64],
    rand_val: float,
) -> tuple[int, int]:
    """Numba-compiled helper function to select a neighbour based on flow-field gradient.

    Args:
        count: The number of neighbours.
        invert: Whether to invert the scores.
        scores: Array of flow-field gradient scores.
        c_x: Array to store the x coordinates of the neighbours.
        c_y: Array to store the y coordinates of the neighbours.
        adjusted_scores: Pre-allocated array for adjusted scores.
        weights: Pre-allocated array for flow-field weights.
        rand_val: Random value for weighted choice.

    Returns:
        The selected neighbour coordinates.
    """
    for i in range(count):
        adjusted_scores[i] = -scores[i] if invert else scores[i]

    min_score = adjusted_scores[0]
    for i in range(1, count):
        if adjusted_scores[i] < min_score:
            min_score = adjusted_scores[i]

    total_w = 0.0
    for i in range(count):
        weights[i] = (adjusted_scores[i] - min_score) + 1e-6
        total_w += weights[i]

    r = rand_val * total_w
    cum = 0.0
    for i in range(count):
        cum += weights[i]
        if r <= cum:
            return c_x[i], c_y[i]
    return c_x[count - 1], c_y[count - 1]


@njit(cache=True)
def _choose_neighbour_by_flow_probability_jit(
    x: int,
    y: int,
    last_dx: int,
    last_dy: int,
    flow_field: npt.NDArray[np.float64],
    width: int,
    height: int,
    invert: bool,
    c_x: npt.NDArray[np.int32],
    c_y: npt.NDArray[np.int32],
    scores: npt.NDArray[np.float64],
    adjusted_scores: npt.NDArray[np.float64],
    weights: npt.NDArray[np.float64],
    rand_val: float,
) -> tuple[int, int]:
    """JIT-accelerated Von-Neumann coordinate selector using flow weights.

    This function takes into account 4-connected Von-Neumann neighbours and selects a neighbour based on flow field
    gradient scores. If the flow-field is flat, the function will select a neighbour based on the last delta. Else, the
    function will select a neighbour based on the flow-field gradient scores, favouring higher gradient scores when
    ``invert`` is False and lower gradient scores when ``invert`` is True.

    Args:
        x: The x coordinate of the cell.
        y: The y coordinate of the cell.
        last_dx: The last x delta.
        last_dy: The last y delta.
        flow_field: Array of flow-field gradient values.
        width: The width of the grid environment.
        height: The height of the grid environment.
        invert: Whether to invert the flow-field gradient scores.
        c_x: Pre-allocated array for neighbour x coordinates.
        c_y: Pre-allocated array for neighbour y coordinates.
        scores: Pre-allocated array for flow-field scores.
        adjusted_scores: Pre-allocated array for adjusted scores.
        weights: Pre-allocated array for flow-field weights.
        rand_val: Random value for weighted choice.

    Returns:
        The selected neighbour coordinates.
    """
    count = _gather_neighbours_jit(x, y, width, height, c_x, c_y)

    for i in range(count):
        scores[i] = flow_field[c_x[i], c_y[i]]

    max_score = scores[0]
    min_score = scores[0]
    for i in range(1, count):
        if scores[i] > max_score:
            max_score = scores[i]
        if scores[i] < min_score:
            min_score = scores[i]

    # Flat fields provide no directional signal; preserve prior heading as inertia.
    if max_score - min_score < 1e-6:
        return _flat_field_choice_jit(count, x, y, last_dx, last_dy, c_x, c_y, weights, rand_val)

    return _weighted_field_choice_jit(count, invert, scores, c_x, c_y, adjusted_scores, weights, rand_val)


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
) -> tuple[int, int]:
    """Select a 4-connected Von-Neumann neighbour via flow-field-weighted JIT selection.

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

    Returns:
        The selected neighbour coordinates.
    """
    if random.choices is not _orig_choices or random.choice is not _orig_choice:
        return _choose_neighbour_by_flow_probability_python(swarm, flow_field, width, height, invert)

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
    )


@njit(cache=True)
def _random_walk_step_jit(
    x: int,
    y: int,
    width: int,
    height: int,
    c_x: npt.NDArray[np.int32],
    c_y: npt.NDArray[np.int32],
    rand_val: float,
) -> tuple[int, int]:
    """JIT-accelerated uniform random coordinate selector for undirected dispersal.

    Args:
        x: The x coordinate of the cell.
        y: The y coordinate of the cell.
        width: The width of the grid environment.
        height: The height of the grid environment.
        c_x: Pre-allocated array for neighbour x coordinates.
        c_y: Pre-allocated array for neighbour y coordinates.
        rand_val: Random value for weighted choice.

    Returns:
        The selected neighbour coordinates.
    """
    c_x[0] = x
    c_y[0] = y
    count = 1

    if x > 0:
        c_x[count] = x - 1
        c_y[count] = y
        count += 1
    if x < width - 1:
        c_x[count] = x + 1
        c_y[count] = y
        count += 1
    if y > 0:
        c_x[count] = x
        c_y[count] = y - 1
        count += 1
    if y < height - 1:
        c_x[count] = x
        c_y[count] = y + 1
        count += 1

    idx = int(rand_val * count)
    if idx >= count:
        idx = count - 1
    return c_x[idx], c_y[idx]


def _random_walk_step(
    x: int,
    y: int,
    width: int,
    height: int,
    c_x: npt.NDArray[np.int32],
    c_y: npt.NDArray[np.int32],
) -> tuple[int, int]:
    """Perform a random walk step to an adjacent cell.

    Args:
        x: The current X coordinate.
        y: The current Y coordinate.
        width: The width of the grid.
        height: The height of the grid.
        c_x: Pre-allocated scratch array for x-coordinates.
        c_y: Pre-allocated scratch array for y-coordinates.

    Returns:
        The new coordinates.
    """
    if random.choice is not _orig_choice:
        candidates: list[tuple[int, int]] = [(x, y)]
        if x > 0:
            candidates.append((x - 1, y))
        if x < width - 1:
            candidates.append((x + 1, y))
        if y > 0:
            candidates.append((x, y - 1))
        if y < height - 1:
            candidates.append((x, y + 1))
        return random.choice(candidates)

    return _random_walk_step_jit(x, y, width, height, c_x, c_y, random.random())


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
    weights = [10.0 if (cx == target_x and cy == target_y) else 1.0 for cx, cy in candidates]
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
    candidates = [(x, y)]
    if x > 0:
        candidates.append((x - 1, y))
    if x < width - 1:
        candidates.append((x + 1, y))
    if y > 0:
        candidates.append((x, y - 1))
    if y < height - 1:
        candidates.append((x, y + 1))

    scores = [float(flow_field[cx, cy]) for cx, cy in candidates]
    max_score = max(scores)
    min_score = min(scores)

    if max_score - min_score < 1e-6:
        return _python_flat_field_choice(swarm, candidates)

    return _python_weighted_field_choice(scores, candidates, invert)


def _is_swarm_anchored(
    swarm: SwarmComponent,
    world: ECSWorld,
    diet_matrix: list[list[bool]],
) -> bool:
    """Return True if swarm is currently co-located with compatible uneaten food.

    This function implements a collision-detection routine to determine whether a herbivore
    swarm is currently co-located with compatible uneaten food. If such a plant is found, the
    swarm is considered "anchored" and will ignore global flow fields for movement, instead
    remaining at its current location until the food source is depleted.

    Args:
        swarm: The swarm component.
        world: The ECS world.
        diet_matrix: The diet matrix.

    Returns:
        True if the swarm is anchored, False otherwise.
    """
    for co_eid in world.entities_at(swarm.x, swarm.y):
        if not world.has_entity(co_eid):
            continue
        co_entity = world.get_entity(co_eid)
        if not co_entity.has_component(PlantComponent):
            continue
        anchor_plant = co_entity.get_component(PlantComponent)
        herbivore_row = diet_matrix[swarm.species_id] if swarm.species_id < len(diet_matrix) else []
        if (
            anchor_plant.species_id < len(herbivore_row)
            and herbivore_row[anchor_plant.species_id]
            and anchor_plant.energy > 0
            and anchor_plant.apparent_nutrition_factor >= 0.999
        ):
            return True
    return False


def _resolve_swarm_movement(
    swarm: SwarmComponent,
    entity: Entity,
    env: GridEnvironment,
    world: ECSWorld,
    diet_matrix: list[list[bool]],
    tile_populations: list[int],
    scratch_cx: npt.NDArray[np.int32],
    scratch_cy: npt.NDArray[np.int32],
    scratch_scores: npt.NDArray[np.float64],
    scratch_adjusted: npt.NDArray[np.float64],
    scratch_weights: npt.NDArray[np.float64],
) -> bool:
    """Evaluate and execute movement phase for a single swarm, return has_moved.

    This function implements the core movement logic for a herbivore swarm, handling
    three distinct priority regimes: **anchoring** (staying put on food), **repulsion** (moving
    off crowded tiles), and **attraction** (moving along the global flow field).

    Args:
        swarm: The swarm component.
        entity: The entity.
        env: The grid environment.
        world: The ECS world.
        diet_matrix: The diet matrix.
        tile_populations: The tile populations.
        scratch_cx: Pre-allocated array for neighbour x coordinates.
        scratch_cy: Pre-allocated array for neighbour y coordinates.
        scratch_scores: Pre-allocated array for flow-field scores.
        scratch_adjusted: Pre-allocated array for adjusted scores.
        scratch_weights: Pre-allocated array for flow-field weights.

    Returns:
        True if the swarm has moved, False otherwise.
    """
    if swarm.move_cooldown > 0:
        swarm.move_cooldown -= 1
        return False

    old_x, old_y = swarm.x, swarm.y

    # 1. Crowding takes strict precedence (Physical Jostling)
    if (
        not swarm.repelled
        and 0 <= swarm.x < env.width
        and 0 <= swarm.y < env.height
        and tile_populations[swarm.y * env.width + swarm.x] > TILE_CARRYING_CAPACITY
    ):
        swarm.repelled = True
        swarm.repelled_ticks_remaining = 1

    if swarm.repelled and swarm.repelled_ticks_remaining > 0:
        nx, ny = _random_walk_step(swarm.x, swarm.y, env.width, env.height, scratch_cx, scratch_cy)
        swarm.repelled_ticks_remaining -= 1
        if swarm.repelled_ticks_remaining <= 0:
            swarm.repelled = False
    else:
        # 2. Fast O(1) check: are we already standing on valid, uneaten food?
        if _is_swarm_anchored(swarm, world, diet_matrix):
            nx, ny = swarm.x, swarm.y
        else:
            # 3. Resume normal gradient tracking if no food is present.
            nx, ny = _choose_neighbour_by_flow_probability(
                swarm,
                env.flow_field,
                env.width,
                env.height,
                scratch_cx,
                scratch_cy,
                scratch_scores,
                scratch_adjusted,
                scratch_weights,
            )

    has_moved = False
    if (nx, ny) != (old_x, old_y):
        world.move_entity(entity.entity_id, old_x, old_y, nx, ny)
        _accumulate_tile_population(tile_populations, old_x, old_y, env.width, -swarm.population)
        _accumulate_tile_population(tile_populations, nx, ny, env.width, swarm.population)
        swarm.x, swarm.y = nx, ny
        swarm.last_dx = nx - old_x
        swarm.last_dy = ny - old_y
        has_moved = True

    swarm.move_cooldown = swarm.velocity - 1
    return has_moved
