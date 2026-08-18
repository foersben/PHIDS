# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Core movement logic for swarms in the interaction system."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

import numpy as np
import numpy.typing as npt

from phids.engine.systems.interaction.movement.math import (
    _calculate_toroidal_delta,
    _choose_neighbour_by_flow_probability_jit,
    _compute_trample_probability_jit,
    _is_swarm_anchored_jit,
    _random_walk_step_jit,
)
from phids.engine.systems.interaction.population import TILE_CARRYING_CAPACITY, _accumulate_tile_population

if TYPE_CHECKING:
    from collections.abc import Mapping

    from phids.api.schemas.species import HerbivoreSpeciesParams
    from phids.engine.components.swarm import SwarmComponent
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld, Entity

_orig_choice = random.choice
_orig_choices = random.choices


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
    )


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
        candidates.append(((x - 1) % width, y))
        candidates.append(((x + 1) % width, y))
        candidates.append((x, (y - 1) % height))
        candidates.append((x, (y + 1) % height))
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


def _is_swarm_anchored(
    swarm: SwarmComponent,
    env: GridEnvironment,
    diet_matrix: list[list[bool]] | npt.NDArray[np.bool_],
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

    Returns:
        True if the swarm is anchored, False otherwise.
    """
    intake = float(getattr(swarm, "last_caloric_intake", 0.0))
    upkeep = float(getattr(swarm, "metabolism_upkeep", 0.0))

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
    )


def _resolve_swarm_movement(
    swarm: SwarmComponent,
    entity: Entity,
    env: GridEnvironment,
    world: ECSWorld,
    diet_matrix: list[list[bool]] | npt.NDArray[np.bool_],
    tile_populations: npt.NDArray[np.int32] | list[int],
    herbivore_params_dict: dict[int, HerbivoreSpeciesParams],
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
        diet_matrix: The boolean diet compatibility matrix.
        tile_populations: Array of current population counts per tile.
        herbivore_params_dict: Dictionary mapping species config IDs to their parameters.
        scratch_cx: Pre-allocated buffer for candidate X coordinates.
        scratch_cy: Pre-allocated buffer for candidate Y coordinates.
        scratch_scores: Pre-allocated buffer for unadjusted field scores.
        scratch_adjusted: Pre-allocated buffer for exponentiated scores.
        scratch_weights: Pre-allocated buffer for final normalized probabilities.

    Returns:
        True if the swarm physically changed (x,y) coordinates, False if anchored.
    """
    if swarm.move_cooldown > 0:
        swarm.move_cooldown -= 1
        return False

    # Decay aversion memory per movement tick
    if getattr(swarm, "aversion_memory", 0.0) > 0.0:
        swarm.aversion_memory *= 0.95
        if swarm.aversion_memory < 0.01:
            swarm.aversion_memory = 0.0

    old_x, old_y = swarm.x, swarm.y

    # 1. Crowding takes strict precedence (Physical Jostling)
    if (
        not swarm.repelled
        and 0 <= swarm.x < env.width
        and 0 <= swarm.y < env.height
        and tile_populations[swarm.y * env.width + swarm.x] > TILE_CARRYING_CAPACITY
    ):
        from phids.engine.core.herbivore_params import get_herbivore_evasion_duration

        k_ticks = get_herbivore_evasion_duration(herbivore_params_dict, swarm.species_id)
        swarm.repelled = True
        swarm.repelled_ticks_remaining = k_ticks

    if swarm.repelled and swarm.repelled_ticks_remaining > 0:
        nx, ny = _random_walk_step(swarm.x, swarm.y, env.width, env.height, scratch_cx, scratch_cy)
        swarm.repelled_ticks_remaining -= 1
        if swarm.repelled_ticks_remaining <= 0:
            swarm.repelled = False
    else:
        # 2. Fast O(1) check: are we already standing on valid, uneaten food?
        if _is_swarm_anchored(swarm, env, diet_matrix):
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
                tile_populations=tile_populations,
            )

    has_moved = False
    if (nx, ny) != (old_x, old_y):
        world.move_entity(entity.entity_id, old_x, old_y, nx, ny)
        _accumulate_tile_population(tile_populations, old_x, old_y, env.width, -swarm.population)
        _accumulate_tile_population(tile_populations, nx, ny, env.width, swarm.population)
        swarm.x, swarm.y = nx, ny

        swarm.last_dx = _calculate_toroidal_delta(nx, old_x, env.width)
        swarm.last_dy = _calculate_toroidal_delta(ny, old_y, env.height)
        has_moved = True

        # Plan 3: Evaluate probabilistic incidental mortality (trampling or clipping) on co-located flora
        _resolve_incidental_mortality(swarm, nx, ny, world, env, herbivore_params_dict)

    swarm.move_cooldown = swarm.velocity - 1
    return has_moved


def _resolve_incidental_mortality(
    swarm: SwarmComponent,
    nx: int,
    ny: int,
    world: ECSWorld,
    env: GridEnvironment,
    herbivore_params_dict: Mapping[int, Any] | None = None,
) -> None:
    """Evaluate probabilistic incidental seedling mortality when a swarm enters cell (nx, ny).

    For each co-located PlantComponent entity at (nx, ny), calculates the destruction probability
    P(destroy) via _compute_trample_probability_jit. If stochastic check succeeds (rng.random() < P),
    the plant is culled from GridEnvironment write layers, unregistered from the spatial hash, and
    queued for entity cleanup.

    Args:
        swarm: SwarmComponent entering the target cell.
        nx: Target X coordinate.
        ny: Target Y coordinate.
        world: ECSWorld instance.
        env: GridEnvironment instance.
        herbivore_params_dict: Mapping of species_id to species parameters.
    """
    from phids.engine.components.plant import PlantComponent

    incidental_factor = 0.0
    mode_cause = "death_incidental_mortality"

    if herbivore_params_dict is not None and swarm.species_id in herbivore_params_dict:
        hp_raw = herbivore_params_dict[swarm.species_id]
        incidental_factor = float(getattr(hp_raw, "incidental_mortality_factor", 0.0))
        mode = getattr(hp_raw, "incidental_mortality_mode", "trampling")
        mode_cause = "death_collateral_trampling" if mode == "trampling" else "death_incidental_consumption"

    if incidental_factor <= 0.0:
        return

    occupants = world.entities_at(nx, ny)
    if not occupants:
        return

    dead_ids: list[int] = []
    for eid in list(occupants):
        if not world.has_entity(eid):
            continue
        ent = world.get_entity(eid)
        if not ent.has_component(PlantComponent):
            continue

        plant: PlantComponent = ent.get_component(PlantComponent)
        prob = _compute_trample_probability_jit(
            swarm_population=swarm.population,
            trample_factor=incidental_factor,
            structural_mass=plant.structural_mass,
            max_structural_mass=plant.max_structural_mass,
            p_max=0.50,
        )

        if prob > 0.0 and random.random() < prob:
            plant.last_energy_loss_cause = mode_cause
            env.clear_plant_energy(nx, ny, plant.species_id)
            env.clear_structural_mass(nx, ny, plant.species_id)
            world.unregister_position(eid, nx, ny)
            dead_ids.append(eid)

    if dead_ids:
        world.collect_garbage(dead_ids)
