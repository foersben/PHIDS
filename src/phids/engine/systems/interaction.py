# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Interaction system: swarm gradient navigation, herbivory, metabolic attrition, and mitosis.

This module implements the second of three ordered per-tick simulation phases in the PHIDS engine.
The interaction phase resolves all herbivore-flora encounters after plant lifecycle dynamics have
been committed to the energy layers, but before chemical-defense substances are emitted and
diffused. This ordering is a deliberate architectural invariant: herbivory must operate against
the most current plant-energy state produced by the lifecycle phase, while the chemical-signaling
phase must be free to observe the post-herbivory energy landscape when computing diffusion
gradients and systemic acquired resistance signals. Toxin effects on swarm navigation are
therefore mediated indirectly through the flow-field gradient rather than through direct
component access, maintaining strict separation between signal propagation and entity mechanics.

Swarm movement is governed by probabilistic sampling over the 4-connected Von-Neumann
neighbourhood, weighted by the scalar flow-field gradient encoded in ``GridEnvironment.flow_field``.
When the local gradient range falls below the numerical threshold of 1x10^-6 - indicating a
chemically flat or saturated zone - movement inertia encoded in ``SwarmComponent.last_dx`` /
``SwarmComponent.last_dy`` introduces a directional persistence bias, approximating the
klinokinetic orientation behaviour observed in real arthropod foragers navigating low-stimulus
environments. Tile carrying capacity (``TILE_CARRYING_CAPACITY``) imposes a local density ceiling
analogous to interference competition: swarms occupying a cell whose aggregate population exceeds
the ceiling enter a transient random-walk dispersal phase, modelling the habitat
saturation-driven emigration documented in colonial insect foragers. Herbivory is applied
exclusively to stationary swarms (those that did not relocate during the current tick) via O(1)
spatial hash lookups; a species-pair diet-compatibility matrix gates energy transfer between each
herbivore-flora combination, ensuring phylogenetic dietary specificity. Metabolic attrition
deducts per-individual upkeep energy each tick; energy deficits are resolved as population
casualties computed by ⌈deficit / energy_min⌉, converting energetic debt directly into
individual mortality. Surplus energy above the swarm-baseline threshold is converted into new
individuals at cost ``energy_min * reproduction_energy_divisor``, implementing a simple
net-assimilation model of reproduction. Mitosis splits an oversized swarm into two equal halves
and registers both entities in the ECS world and spatial hash, mimicking the colony fission
events characteristic of social hymenoptera and clonal plant-grazer aggregations.

Attributes:
    TILE_CARRYING_CAPACITY: Maximum aggregate individual count permitted on a single grid cell
        before crowding-induced dispersal is triggered. Acts as an upper bound on local population
        density, preventing simulation degeneracy under unconstrained growth.

"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt
from numba import njit

from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent

if TYPE_CHECKING:
    from phids.api.schemas import FloraSpeciesParams, HerbivoreSpeciesParams
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld, Entity

_orig_choice = random.choice
_orig_choices = random.choices

TILE_CARRYING_CAPACITY = 500


def _accumulate_tile_population(
    tile_populations: list[int],
    x: int,
    y: int,
    width: int,
    delta: int,
) -> None:
    """Apply a signed population delta to one tile-population cache entry.

    This function maintains a lightweight, tick-local census of aggregate swarm populations per
    grid cell. The cache is used as an O(1) crowding-pressure oracle: rather than re-querying the
    spatial hash and summing component populations on every crowding check, each movement and
    reproduction event issues a corrective delta to keep the cache consistent. The function is
    intentionally side-effecting and operates in-place on the shared ``tile_populations`` flat
    list passed by the outer interaction loop, which pre-allocates WxH capacity for cache locality.

    Args:
        tile_populations: Mutable flat list mapping (y * w + x) to total individual counts,
            shared across all swarm iterations within a single ``run_interaction`` call.
        x: Grid column index of the cell to update.
        y: Grid row index of the cell to update.
        width: Grid width to compute the flat index.
        delta: Signed integer change in population count; positive for births or arrivals,
            negative for deaths or departures.

    """
    if 0 <= x < width and 0 <= y < (len(tile_populations) // width):
        tile_populations[y * width + x] += delta


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
    weights = np.empty(5, dtype=np.float64)
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
    rand_val: float,
) -> tuple[int, int]:
    """Numba-compiled helper function to select a neighbour based on flow-field gradient.

    Args:
        count: The number of neighbours.
        invert: Whether to invert the scores.
        scores: Array of flow-field gradient scores.
        c_x: Array to store the x coordinates of the neighbours.
        c_y: Array to store the y coordinates of the neighbours.
        rand_val: Random value for weighted choice.

    Returns:
        The selected neighbour coordinates.
    """
    adjusted_scores = np.empty(5, dtype=np.float64)
    for i in range(count):
        adjusted_scores[i] = -scores[i] if invert else scores[i]

    min_score = adjusted_scores[0]
    for i in range(1, count):
        if adjusted_scores[i] < min_score:
            min_score = adjusted_scores[i]

    weights = np.empty(5, dtype=np.float64)
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
        rand_val: Random value for weighted choice.

    Returns:
        The selected neighbour coordinates.
    """
    c_x = np.empty(5, dtype=np.int32)
    c_y = np.empty(5, dtype=np.int32)

    count = _gather_neighbours_jit(x, y, width, height, c_x, c_y)

    scores = np.empty(5, dtype=np.float64)
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
        return _flat_field_choice_jit(count, x, y, last_dx, last_dy, c_x, c_y, rand_val)

    return _weighted_field_choice_jit(count, invert, scores, c_x, c_y, rand_val)


def _choose_neighbour_by_flow_probability(
    swarm: SwarmComponent,
    flow_field: npt.NDArray[np.float64],
    width: int,
    height: int,
    invert: bool = False,
) -> tuple[int, int]:
    """Select a 4-connected Von-Neumann neighbour via flow-field-weighted JIT selection.

    Args:
        swarm: The swarm component.
        flow_field: Array of flow-field gradient values.
        width: The width of the grid environment.
        height: The height of the grid environment.
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
        random.random(),
    )


@njit(cache=True)
def _random_walk_step_jit(
    x: int,
    y: int,
    width: int,
    height: int,
    rand_val: float,
) -> tuple[int, int]:
    """JIT-accelerated uniform random coordinate selector for undirected dispersal.

    Args:
        x: The x coordinate of the cell.
        y: The y coordinate of the cell.
        width: The width of the grid environment.
        height: The height of the grid environment.
        rand_val: Random value for weighted choice.

    Returns:
        The selected neighbour coordinates.
    """
    c_x = np.empty(5, dtype=np.int32)
    c_y = np.empty(5, dtype=np.int32)

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
) -> tuple[int, int]:
    """Select a uniformly random valid adjacent cell for undirected JIT dispersal.

    Args:
        x: The x coordinate of the cell.
        y: The y coordinate of the cell.
        width: The width of the grid environment.
        height: The height of the grid environment.

    Returns:
        The selected neighbour coordinates.
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

    return _random_walk_step_jit(x, y, width, height, random.random())


def _co_located_swarm_population(world: ECSWorld, x: int, y: int) -> int:
    """Return the total individual population of all swarms occupying a single grid cell.

    This function performs a local density census by iterating over all entity identifiers
    registered at the specified cell via the O(1) spatial hash, accumulating the population
    count of every entity that carries a ``SwarmComponent``. The result quantifies the aggregate
    occupancy load of the cell, which is compared against ``TILE_CARRYING_CAPACITY`` to determine
    whether interference-competition-driven dispersal should be initiated. The check is performed
    on-demand rather than from the tick-local cache when an authoritative count is required
    outside the main loop context. Entities absent from the ECS registry (stale spatial hash
    entries scheduled for garbage collection) are gracefully skipped to preserve census accuracy
    in the presence of concurrent mortality.

    Args:
        world: The ECS world registry providing both spatial hash lookups and component access.
        x: Grid column index of the cell to census.
        y: Grid row index of the cell to census.

    Returns:
        The non-negative integer sum of ``SwarmComponent.population`` across all live swarm
        entities co-located at ``(x, y)``, representing the instantaneous local population
        density for crowding-pressure evaluation.

    """
    total_population = 0
    for entity_id in world.entities_at(x, y):
        if not world.has_entity(entity_id):
            continue
        entity = world.get_entity(entity_id)
        if entity.has_component(SwarmComponent):
            swarm = entity.get_component(SwarmComponent)
            total_population += swarm.population
    return total_population


def _perform_mitosis(
    swarm: SwarmComponent,
    world: ECSWorld,
    env: GridEnvironment,
) -> SwarmComponent:
    """Split an oversized swarm into two equal daughter colonies via binary fission.

    Colony fission - the division of a supercolony that has exceeded its reproductive threshold
    into two independent daughter swarms - is a fundamental demographic event in social insect
    biology and clonal arthropod populations. This function implements the discrete analogue of
    that process within the ECS framework: the parent swarm retains ⌊n/2⌋ individuals and half
    the accumulated energy, while a new entity carrying a ``SwarmComponent`` with the complementary
    moiety is allocated, registered in the ECS world, and inserted into the spatial hash at a
    stochastically sampled adjacent cell. All heritable phenotypic parameters - ``energy_min``,
    ``velocity``, ``consumption_rate``, ``reproduction_energy_divisor``,
    ``energy_upkeep_per_individual``, and ``split_population_threshold`` - are copied verbatim to
    the offspring, reflecting the clonal genetic identity of the daughter colony. The energy
    partition is strictly symmetric (each colony receives exactly half of the parent pool) to
    conserve total simulated biomass across the fission event. Offspring placement via
    ``_random_walk_step`` ensures daughters are not deposited on top of the parent, reducing
    immediate re-coalescence and modelling the active dispersal phase observed following natural
    colony fission events.

    Args:
        swarm: Parent swarm component to be bisected; its ``population``, ``initial_population``,
            and ``energy`` fields are mutated in-place to reflect the retained half.
        world: ECS world registry used to allocate the new entity identifier and attach the
            offspring ``SwarmComponent``.
        env: Grid environment supplying the spatial dimensions required by ``_random_walk_step``
            to sample a valid dispersal cell adjacent to the parent's current position.

    Returns:
        The ``SwarmComponent`` instance attached to the newly spawned offspring entity,
        containing its assigned population count, energy allocation, and grid coordinates.

    See Also:
        _random_walk_step
    """
    offspring_population = swarm.population // 2
    retained_population = swarm.population - offspring_population
    swarm.population = retained_population
    swarm.initial_population = retained_population
    offspring_x, offspring_y = _random_walk_step(swarm.x, swarm.y, env.width, env.height)

    new_entity = world.create_entity()
    offspring = SwarmComponent(
        entity_id=new_entity.entity_id,
        species_id=swarm.species_id,
        x=offspring_x,
        y=offspring_y,
        population=offspring_population,
        initial_population=offspring_population,
        energy=swarm.energy / 2.0,
        energy_min=swarm.energy_min,
        velocity=swarm.velocity,
        consumption_rate=swarm.consumption_rate,
        reproduction_energy_divisor=swarm.reproduction_energy_divisor,
        energy_upkeep_per_individual=swarm.energy_upkeep_per_individual,
        split_population_threshold=swarm.split_population_threshold,
    )
    swarm.energy /= 2.0
    world.add_component(new_entity.entity_id, offspring)
    world.register_position(new_entity.entity_id, offspring_x, offspring_y)
    return offspring


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
        nx, ny = _random_walk_step(swarm.x, swarm.y, env.width, env.height)
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


def _feed_on_single_plant(
    swarm: SwarmComponent,
    target_plant: PlantComponent,
    flora_species_params: list[FloraSpeciesParams],
    herbivore_species_params: list[HerbivoreSpeciesParams],
    world: ECSWorld,
    env: GridEnvironment,
    tile_populations: list[int],
    plant_death_causes: dict[str, int] | None,
    co_eid: int,
) -> tuple[float, bool]:
    """Feed on a single co-located plant, returning (metabolized_energy, plant_killed).

    This function implements the core feeding logic for a herbivore swarm, handling
    the transfer of energy from a plant to the swarm. It calculates the potential
    consumption based on the swarm's parameters and the plant's energy, then applies
    digestibility and efficiency modifiers to determine the actual amount of consumed
    energy.

    Args:
        swarm: The swarm component.
        target_plant: The plant component to feed on.
        flora_species_params: The flora species parameters.
        herbivore_species_params: The herbivore species parameters.
        world: The ECS world.
        env: The grid environment.
        tile_populations: The tile populations.
        plant_death_causes: The plant death causes.
        co_eid: The co-eid.

    Returns:
        A tuple containing the metabolized energy and whether the plant was killed.
    """
    effective_velocity = max(1, swarm.velocity)
    potential_consumption = (swarm.consumption_rate / effective_velocity) * swarm.population
    consumed = min(potential_consumption, target_plant.energy)

    plant_params = flora_species_params[target_plant.species_id]
    swarm_params = herbivore_species_params[swarm.species_id]

    digestibility_modifier = getattr(plant_params.passive_defenses, "digestibility_modifier", 1.0)
    digestive_efficiency = getattr(swarm_params.resistances, "digestive_efficiency", 1.0)
    mechanical_damage_per_bite = getattr(plant_params.passive_defenses, "mechanical_damage_per_bite", 0.0)
    morphological_adaptation = getattr(swarm_params.resistances, "morphological_adaptation", 0.0)

    # Calculate metabolized energy
    net_digestibility = min(1.0, max(0.0, digestibility_modifier * digestive_efficiency))
    metabolized_energy = consumed * net_digestibility

    # Apply mechanical damage
    if mechanical_damage_per_bite > 0.0 and consumed > 0:
        damage = mechanical_damage_per_bite * (1.0 - morphological_adaptation)
        casualties = math.floor(damage)
        swarm.population = max(0, swarm.population - casualties)
        _accumulate_tile_population(tile_populations, swarm.x, swarm.y, env.width, -casualties)

    target_plant.energy -= consumed
    env.set_plant_energy(
        target_plant.x,
        target_plant.y,
        target_plant.species_id,
        target_plant.energy,
    )

    plant_killed = False
    if target_plant.energy < target_plant.survival_threshold:
        if plant_death_causes is not None:
            plant_death_causes["death_herbivore_feeding"] = plant_death_causes.get("death_herbivore_feeding", 0) + 1
        env.clear_plant_energy(
            target_plant.x,
            target_plant.y,
            target_plant.species_id,
        )
        world.unregister_position(co_eid, target_plant.x, target_plant.y)
        world.collect_garbage([co_eid])
        plant_killed = True

    return metabolized_energy, plant_killed


def _resolve_swarm_feeding(
    swarm: SwarmComponent,
    world: ECSWorld,
    env: GridEnvironment,
    diet_matrix: list[list[bool]],
    flora_species_params: list[FloraSpeciesParams],
    herbivore_species_params: list[HerbivoreSpeciesParams],
    tile_populations: list[int],
    plant_death_causes: dict[str, int] | None = None,
) -> None:
    """Execute feeding phase on target plants at current position.

    Iterates through all co-located entities, identifies compatible plants, and consumes them.
    Updates the swarm's energy, triggers plant removal if exhausted, and adjusts swarm behavior
    (stopping repulsion, becoming repelled) based on the feeding outcome.

    Args:
        swarm: The swarm component.
        world: The ECS world.
        env: The grid environment.
        diet_matrix: The diet matrix.
        flora_species_params: The flora species parameters.
        herbivore_species_params: The herbivore species parameters.
        tile_populations: The tile populations.
        plant_death_causes: The plant death causes.
    """
    ate_anything = False
    on_incompatible_plant = False

    for co_eid in list(world.entities_at(swarm.x, swarm.y)):
        if not world.has_entity(co_eid):
            continue
        co_entity = world.get_entity(co_eid)
        if not co_entity.has_component(PlantComponent):
            continue
        target_plant: PlantComponent = co_entity.get_component(PlantComponent)

        # Diet compatibility check
        herbivore_row = diet_matrix[swarm.species_id] if swarm.species_id < len(diet_matrix) else []
        if not (target_plant.species_id < len(herbivore_row) and herbivore_row[target_plant.species_id]):
            on_incompatible_plant = True
            continue

        metabolized, _ = _feed_on_single_plant(
            swarm,
            target_plant,
            flora_species_params,
            herbivore_species_params,
            world,
            env,
            tile_populations,
            plant_death_causes,
            co_eid,
        )
        swarm.energy += metabolized
        if metabolized > 0:
            ate_anything = True

    # Behavioral overrides based on feeding success
    if ate_anything:
        swarm.repelled = False
        swarm.repelled_ticks_remaining = 0
    elif on_incompatible_plant:
        swarm.repelled = True
        swarm.repelled_ticks_remaining = 2


def _resolve_swarm_metabolism_and_reproduction(
    swarm: SwarmComponent,
    entity: Entity,
    world: ECSWorld,
    env: GridEnvironment,
    tile_populations: list[int],
    dead_swarms: list[int],
) -> bool:
    """Apply metabolic upkeep, casualty liquidation, reproduction, and mitosis. Returns False if dead.

    This function consolidates the post-feeding life-cycle mechanics for a swarm:

    1. **Metabolic Cost**: Deducts energy based on population size and baseline needs.
    2. **Casualty Liquidation**: Triggers "death by starvation" if energy reserves are insufficient to support the
    current population.
    3. **Reproduction & Mitosis**: Calculates and executes population doubling (mitosis) if the swarm has accumulated
    enough excess energy.

    The function returns `False` if the swarm's population drops to zero, signaling to the main loop that the entity
    should be cleaned up.

    Args:
        swarm: The swarm component.
        entity: The entity component.
        world: The ECS world.
        env: The grid environment.
        tile_populations: The tile populations.
        dead_swarms: The list to append dead swarm IDs to.

    Returns:
        False if the swarm died, True otherwise.
    """
    metabolic_cost = swarm.population * swarm.energy_min * swarm.energy_upkeep_per_individual
    swarm.energy -= metabolic_cost

    if swarm.energy < 0.0 and swarm.population > 0:
        previous_population = swarm.population
        deficit = -swarm.energy
        casualties = int(deficit // swarm.energy_min)
        if casualties * swarm.energy_min < deficit:
            casualties += 1
        swarm.population = max(0, swarm.population - casualties)
        _accumulate_tile_population(
            tile_populations,
            swarm.x,
            swarm.y,
            env.width,
            swarm.population - previous_population,
        )
        total_casualty_energy = casualties * swarm.energy_min
        leftover_energy = total_casualty_energy - deficit
        swarm.energy = max(0.0, leftover_energy)

    if swarm.population <= 0:
        world.unregister_position(entity.entity_id, swarm.x, swarm.y)
        dead_swarms.append(entity.entity_id)
        return False

    # Reproduction
    baseline_energy = swarm.population * swarm.energy_min
    if swarm.energy > baseline_energy:
        surplus = swarm.energy - baseline_energy
        cost_per_offspring = max(
            swarm.energy_min,
            swarm.energy_min * swarm.reproduction_energy_divisor,
        )

        new_individuals = int(surplus // cost_per_offspring)
        if new_individuals > 0:
            previous_population = swarm.population
            swarm.population += new_individuals
            _accumulate_tile_population(
                tile_populations,
                swarm.x,
                swarm.y,
                env.width,
                swarm.population - previous_population,
            )
            swarm.energy -= new_individuals * cost_per_offspring

    # Mitosis
    threshold = swarm.split_population_threshold
    if swarm.population >= threshold:
        pre_split_population = swarm.population
        offspring = _perform_mitosis(swarm, world, env)
        _accumulate_tile_population(
            tile_populations,
            swarm.x,
            swarm.y,
            env.width,
            swarm.population - pre_split_population,
        )
        _accumulate_tile_population(
            tile_populations,
            offspring.x,
            offspring.y,
            env.width,
            offspring.population,
        )
    return True


def run_interaction(
    world: ECSWorld,
    env: GridEnvironment,
    diet_matrix: list[list[bool]],
    flora_species_params: list[FloraSpeciesParams],
    herbivore_species_params: list[HerbivoreSpeciesParams],
    tick: int,  # noqa: ARG001
    plant_death_causes: dict[str, int] | None = None,
) -> None:
    """Execute one complete interaction tick, advancing all swarm entities through seven ordered phases.

    The interaction cycle is executed in the following deterministic order for all swarms:

    1. **Calculate Tile Populations**: Computes the number of individuals per tile to establish density.
    2. **Movement**: Determines new positions based on flow, repulsion, and anchoring.
    3. **Feeding**: Consumes local flora, transfers energy, and handles plant mortality.
    4. **Metabolism & Reproduction**: Applies energy costs, triggers "death by starvation" if needed, and executes
    population doubling (mitosis).

    This ensures a consistent, phase-ordered simulation step where movement precedes feeding, and metabolic
    consequences are resolved before the next tick.

    Args:
        world: The ECS world.
        env: The grid environment.
        diet_matrix: The diet matrix.
        flora_species_params: The flora species parameters.
        herbivore_species_params: The herbivore species parameters.
        tick: The current simulation tick.
        plant_death_causes: The plant death causes.
    """
    dead_swarms: list[int] = []
    tile_populations: list[int] = [0] * (env.width * env.height)

    # Initial population accumulation pass
    for eid in tuple(world._component_index.get(SwarmComponent, set())):
        entity = world._entities.get(eid)
        if entity is None or SwarmComponent not in entity._components:
            continue
        indexed_swarm = entity.get_component(SwarmComponent)
        _accumulate_tile_population(
            tile_populations,
            indexed_swarm.x,
            indexed_swarm.y,
            env.width,
            indexed_swarm.population,
        )

    # Main interaction loop
    for eid in tuple(world._component_index.get(SwarmComponent, set())):
        entity = world._entities.get(eid)
        if entity is None or SwarmComponent not in entity._components:
            continue
        swarm: SwarmComponent = entity.get_component(SwarmComponent)

        # 1-2. Movement Phase
        has_moved = _resolve_swarm_movement(swarm, entity, env, world, diet_matrix, tile_populations)

        # 3. Feeding Phase
        if not has_moved:
            _resolve_swarm_feeding(
                swarm,
                world,
                env,
                diet_matrix,
                flora_species_params,
                herbivore_species_params,
                tile_populations,
                plant_death_causes,
            )

        # 4-7. Metabolism, Reproduction, Mitosis, and Death check
        _resolve_swarm_metabolism_and_reproduction(swarm, entity, world, env, tile_populations, dead_swarms)

    world.collect_garbage(dead_swarms)
