"""Interaction system: swarm gradient navigation, herbivory, metabolic attrition, and mitosis.

This module implements the second of three ordered per-tick simulation phases in the PHIDS engine.
The interaction phase resolves all predator–flora encounters after plant lifecycle dynamics have
been committed to the energy layers, but before chemical-defense substances are emitted and
diffused. This ordering is a deliberate architectural invariant: herbivory must operate against
the most current plant-energy state produced by the lifecycle phase, while the chemical-signaling
phase must be free to observe the post-herbivory energy landscape when computing diffusion
gradients and systemic acquired resistance signals. Toxin effects on swarm navigation are
therefore mediated indirectly through the flow-field gradient rather than through direct
component access, maintaining strict separation between signal propagation and entity mechanics.

Swarm movement is governed by probabilistic sampling over the 4-connected Von-Neumann
neighbourhood, weighted by the scalar flow-field gradient encoded in ``GridEnvironment.flow_field``.
When the local gradient range falls below the numerical threshold of 1×10⁻⁶ — indicating a
chemically flat or saturated zone — movement inertia encoded in ``SwarmComponent.last_dx`` /
``SwarmComponent.last_dy`` introduces a directional persistence bias, approximating the
klinokinetic orientation behaviour observed in real arthropod foragers navigating low-stimulus
environments. Tile carrying capacity (``TILE_CARRYING_CAPACITY``) imposes a local density ceiling
analogous to interference competition: swarms occupying a cell whose aggregate population exceeds
the ceiling enter a transient random-walk dispersal phase, modelling the habitat
saturation-driven emigration documented in colonial insect foragers. Herbivory is applied
exclusively to stationary swarms (those that did not relocate during the current tick) via O(1)
spatial hash lookups; a species-pair diet-compatibility matrix gates energy transfer between each
predator–flora combination, ensuring phylogenetic dietary specificity. Metabolic attrition
deducts per-individual upkeep energy each tick; energy deficits are resolved as population
casualties computed by ⌈deficit / energy_min⌉, converting energetic debt directly into
individual mortality. Surplus energy above the swarm-baseline threshold is converted into new
individuals at cost ``energy_min × reproduction_energy_divisor``, implementing a simple
net-assimilation model of reproduction. Mitosis splits an oversized swarm into two equal halves
and registers both entities in the ECS world and spatial hash, mimicking the colony fission
events characteristic of social hymenoptera and clonal plant-grazer aggregations.

Attributes:
    TILE_CARRYING_CAPACITY: Maximum aggregate individual count permitted on a single grid cell
        before crowding-induced dispersal is triggered. Acts as an upper bound on local population
        density, preventing simulation degeneracy under unconstrained growth.
"""

from __future__ import annotations

import random

import numpy as np
import numpy.typing as npt

from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld


TILE_CARRYING_CAPACITY = 500


def _accumulate_tile_population(
    tile_populations: dict[tuple[int, int], int],
    x: int,
    y: int,
    delta: int,
) -> None:
    """Apply a signed population delta to one tile-population cache entry.

    This function maintains a lightweight, tick-local census of aggregate swarm populations per
    grid cell. The cache is used as an O(1) crowding-pressure oracle: rather than re-querying the
    spatial hash and summing component populations on every crowding check, each movement and
    reproduction event issues a corrective delta to keep the cache consistent. Zero and negative
    population tiles are evicted immediately to avoid unbounded memory growth across a simulation
    run with many birth–death cycles. The function is intentionally side-effecting and operates
    in-place on the shared ``tile_populations`` mapping passed by the outer interaction loop.

    Args:
        tile_populations: Mutable tick-local mapping of grid coordinates to total individual
            counts, shared across all swarm iterations within a single ``run_interaction`` call.
        x: Grid column index of the cell to update.
        y: Grid row index of the cell to update.
        delta: Signed integer change in population count; positive for births or arrivals,
            negative for deaths or departures.
    """
    pos = (x, y)
    next_population = tile_populations.get(pos, 0) + delta
    if next_population > 0:
        tile_populations[pos] = next_population
    else:
        tile_populations.pop(pos, None)


def _choose_neighbour_by_flow_probability(
    swarm: SwarmComponent,
    flow_field: npt.NDArray[np.float64],
    width: int,
    height: int,
    invert: bool = False,
) -> tuple[int, int]:
    """Select a 4-connected Von-Neumann neighbour via flow-field-weighted stochastic sampling.

    This function encodes the klinokinetic orientation strategy used by swarms navigating the
    chemical signal landscape. Candidate cells — the current cell plus each in-bounds cardinal
    neighbour — are assigned softmax-like weights derived from the scalar flow-field values read
    at each position. Stochastic rather than deterministic selection is employed to prevent the
    entire population from converging on a single cell, producing the diffuse foraging fronts
    observed in natural herbivore aggregations. When the local gradient range falls below the
    numerical threshold of 1×10⁻⁶ — signifying a chemically flat or diffusion-saturated zone
    where the signal provides no reliable directional information — movement inertia stored in
    ``swarm.last_dx`` and ``swarm.last_dy`` is used to bias selection toward the prior heading,
    with a 10:1 preference weight, emulating the directional persistence (orthokinesis)
    documented in foraging hymenoptera. If no prior heading exists, isotropic random dispersal
    is applied. The ``invert`` flag reverses gradient preference, enabling repulsion or
    aversion behaviour to be expressed through the same selection mechanism.

    Args:
        swarm: Swarm component supplying current grid coordinates and the last recorded movement
            vector ``(last_dx, last_dy)`` used for inertial heading when the gradient is flat.
        flow_field: Two-dimensional scalar field indexed as ``[x, y]``, encoding the aggregated
            chemical attraction signal produced by Gaussian diffusion of plant volatiles.
        width: Horizontal extent of the simulation grid in cells; used to clamp neighbour
            candidates to valid column indices.
        height: Vertical extent of the simulation grid in cells; used to clamp neighbour
            candidates to valid row indices.
        invert: When ``True``, gradient scores are negated prior to weight computation, causing
            the swarm to preferentially move toward lower-signal regions (flee or aversion
            behaviour).

    Returns:
        The ``(nx, ny)`` integer grid coordinates of the stochastically selected target cell,
        which may equal the current position if the swarm is already occupying the
        highest-scored cell or if the random draw selects in-place movement.

    See Also:
        _random_walk_step
    """
    x, y = swarm.x, swarm.y
    candidates: list[tuple[int, int]] = [(x, y)]
    if x > 0:
        candidates.append((x - 1, y))
    if x < width - 1:
        candidates.append((x + 1, y))
    if y > 0:
        candidates.append((x, y - 1))
    if y < height - 1:
        candidates.append((x, y + 1))

    scores = [
        float(flow_field[candidate_x, candidate_y]) for candidate_x, candidate_y in candidates
    ]
    max_score = max(scores)
    min_score = min(scores)

    # Flat fields provide no directional signal; preserve prior heading as inertia.
    if max_score - min_score < 1e-6:
        if swarm.last_dx == 0 and swarm.last_dy == 0:
            return random.choice(candidates)

        target_x = x + swarm.last_dx
        target_y = y + swarm.last_dy
        weights: list[float] = []
        for candidate_x, candidate_y in candidates:
            if candidate_x == target_x and candidate_y == target_y:
                weights.append(10.0)
            else:
                weights.append(1.0)
        return random.choices(candidates, weights=weights, k=1)[0]

    adjusted_scores = [-score for score in scores] if invert else scores
    min_score = min(adjusted_scores)
    weights = [(score - min_score) + 1e-6 for score in adjusted_scores]
    return random.choices(candidates, weights=weights, k=1)[0]


def _random_walk_step(
    x: int,
    y: int,
    width: int,
    height: int,
) -> tuple[int, int]:
    """Select a uniformly random valid adjacent cell for undirected dispersal.

    Undirected random movement — equivalent to a discrete isotropic random walk on the grid
    lattice — is invoked in two ecologically distinct contexts: first, when a swarm is expelled
    from an overcrowded tile (interference competition-driven dispersal); and second, as the
    offspring placement strategy during mitosis. In both cases, the absence of gradient
    information necessitates a spatially unbiased step. The candidate set comprises the current
    cell and all in-bounds cardinal neighbours, ensuring boundary-adjacent swarms are never
    driven off the grid. The uniform selection over this set matches the Brownian-motion
    approximation commonly applied to arthropod dispersal in the absence of environmental
    chemosensory cues.

    Args:
        x: Current grid column index of the entity initiating dispersal.
        y: Current grid row index of the entity initiating dispersal.
        width: Horizontal extent of the simulation grid; used to enforce the right-boundary
            constraint on candidate generation.
        height: Vertical extent of the simulation grid; used to enforce the bottom-boundary
            constraint on candidate generation.

    Returns:
        An ``(nx, ny)`` coordinate pair drawn uniformly at random from the set of valid
        adjacent cells and the current cell, representing the dispersal destination.

    See Also:
        _choose_neighbour_by_flow_probability
    """
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

    Colony fission — the division of a supercolony that has exceeded its reproductive threshold
    into two independent daughter swarms — is a fundamental demographic event in social insect
    biology and clonal arthropod populations. This function implements the discrete analogue of
    that process within the ECS framework: the parent swarm retains ⌊n/2⌋ individuals and half
    the accumulated energy, while a new entity carrying a ``SwarmComponent`` with the complementary
    moiety is allocated, registered in the ECS world, and inserted into the spatial hash at a
    stochastically sampled adjacent cell. All heritable phenotypic parameters — ``energy_min``,
    ``velocity``, ``consumption_rate``, ``reproduction_energy_divisor``,
    ``energy_upkeep_per_individual``, and ``split_population_threshold`` — are copied verbatim to
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


def run_interaction(
    world: ECSWorld,
    env: GridEnvironment,
    diet_matrix: list[list[bool]],
    tick: int,
    plant_death_causes: dict[str, int] | None = None,
) -> None:
    """Execute one complete interaction tick, advancing all swarm entities through seven ordered phases.

    This function is the primary entry point for the interaction system and orchestrates the full
    predator–flora encounter resolution cycle for a single simulation tick. The seven sequential
    sub-phases — movement cooldown, gradient-directed navigation with anchoring, herbivorous
    feeding, metabolic attrition, mortality evaluation, net-assimilation reproduction, and colony
    fission — are applied atomically to each swarm entity in sequence. The ordering is a strict
    architectural invariant grounded in ecological causality: entities must first attempt movement
    before feeding is evaluated (stationary swarms only feed), and reproduction is assessed only
    after attrition has resolved the energy budget, ensuring that population gains are never
    computed against an energetically bankrupt swarm.

    A tick-local ``tile_populations`` census is initialised from the full swarm roster at the
    start of the call and maintained incrementally via ``_accumulate_tile_population`` throughout
    all movement, birth, and death events. This O(1) crowding oracle prevents repeated spatial
    hash traversals and is the performance-critical mechanism that decouples crowding checks from
    the quadratic complexity that would result from naive per-entity density queries.

    Movement navigation employs a two-level priority hierarchy: (1) if the current tile is
    overcrowded beyond ``TILE_CARRYING_CAPACITY``, an isotropic random-walk dispersal step is
    forced, irrespective of the chemical gradient, modelling interference-competition-driven
    emigration; (2) if compatible food is detected at the current position via O(1) spatial hash
        lookup, the swarm is anchored and flow-field navigation is suppressed, encoding the
        arrestment reflex documented in herbivorous arthropods upon contact with a palatable host.
        Complementarily, contact with only diet-incompatible plants triggers a short aversive
        random-walk episode (taste rejection), enabling escape from misleading scent maxima.
        Only when neither condition holds is gradient-directed movement via
    ``_choose_neighbour_by_flow_probability`` invoked.

    Herbivory computes consumed energy as ``min((consumption_rate / velocity) × population,
    plant.energy)`` and transfers it directly to the swarm's energy budget, modelling
    assimilation efficiency. Plants whose post-consumption energy falls below
    ``survival_threshold`` are immediately removed from the ECS registry and spatial hash,
    recording the cause of death in ``plant_death_causes`` if provided. Metabolic attrition
    applies a per-tick upkeep cost of ``population × energy_min × energy_upkeep_per_individual``;
    any resulting energy deficit is liquidated by computing casualties as ⌈deficit / energy_min⌉
    and reducing the population accordingly, with residual energy redistributed among survivors.
    Reproduction converts swarm-scale surplus energy above the per-capita baseline into new
    individuals at the configured cost per offspring. Colony fission via ``_perform_mitosis`` is
    triggered when population exceeds ``split_population_threshold`` (or twice the initial
    population when that field is zero), registering the daughter entity in the ECS world and
    spatial hash. Deceased swarms are collected in a deferred ``dead_swarms`` list and purged
    from the ECS registry in a single ``collect_garbage`` call at the end of the tick, avoiding
    iterator invalidation during traversal.

    Args:
        world: ECS world registry providing entity iteration, spatial hash operations,
            component access, entity creation, and garbage collection.
        env: Grid environment instance supplying the flow-field scalar array, toxin layers,
            grid dimensions, and plant-energy mutation methods.
        diet_matrix: Boolean compatibility matrix indexed as ``[predator_species_id][flora_species_id]``;
            a ``True`` entry at position ``[i][j]`` indicates that predator species ``i`` is able
            to consume flora species ``j``.
        tick: Current simulation tick index; reserved for future tick-conditional logic and
            diagnostic instrumentation.
        plant_death_causes: Optional mutable mapping from string cause identifiers to integer
            occurrence counts; when provided, herbivory-induced plant deaths are recorded under
            the key ``"death_herbivore_feeding"``.
    """
    dead_swarms: list[int] = []
    tile_populations: dict[tuple[int, int], int] = {}
    for entity in world.query(SwarmComponent):
        indexed_swarm = entity.get_component(SwarmComponent)
        _accumulate_tile_population(
            tile_populations,
            indexed_swarm.x,
            indexed_swarm.y,
            indexed_swarm.population,
        )

    for entity in list(world.query(SwarmComponent)):
        swarm: SwarmComponent = entity.get_component(SwarmComponent)
        has_moved = False

        # ----------------------------------------------------------------
        # 1. Movement cooldown
        # ----------------------------------------------------------------
        if swarm.move_cooldown > 0:
            swarm.move_cooldown -= 1
        else:
            # ----------------------------------------------------------------
            # 2. Navigate with local crowding pressure & Anchoring (Option B)
            # ----------------------------------------------------------------
            old_x, old_y = swarm.x, swarm.y

            # 1. Crowding takes strict precedence (Physical Jostling)
            if (
                not swarm.repelled
                and tile_populations.get((swarm.x, swarm.y), 0) > TILE_CARRYING_CAPACITY
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
                is_anchored = False
                for co_eid in world.entities_at(swarm.x, swarm.y):
                    if not world.has_entity(co_eid):
                        continue
                    co_entity = world.get_entity(co_eid)
                    if not co_entity.has_component(PlantComponent):
                        continue
                    anchor_plant = co_entity.get_component(PlantComponent)
                    pred_row = (
                        diet_matrix[swarm.species_id] if swarm.species_id < len(diet_matrix) else []
                    )
                    if (
                        anchor_plant.species_id < len(pred_row)
                        and pred_row[anchor_plant.species_id]
                        and anchor_plant.energy > 0
                    ):
                        is_anchored = True
                        break

                if is_anchored:
                    # Override flow-field movement entirely. Stay and feed.
                    nx, ny = swarm.x, swarm.y
                else:
                    # 3. Resume normal gradient tracking if no food is present.
                    nx, ny = _choose_neighbour_by_flow_probability(
                        swarm,
                        env.flow_field,
                        env.width,
                        env.height,
                    )

            if (nx, ny) != (old_x, old_y):
                world.move_entity(entity.entity_id, old_x, old_y, nx, ny)
                _accumulate_tile_population(tile_populations, old_x, old_y, -swarm.population)
                _accumulate_tile_population(tile_populations, nx, ny, swarm.population)
                swarm.x, swarm.y = nx, ny
                swarm.last_dx = nx - old_x
                swarm.last_dy = ny - old_y
                has_moved = True

            swarm.move_cooldown = swarm.velocity - 1

        # ----------------------------------------------------------------
        # 3. Feeding – check co-located plants via spatial hash
        # ----------------------------------------------------------------
        if not has_moved:
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
                pred_row = (
                    diet_matrix[swarm.species_id] if swarm.species_id < len(diet_matrix) else []
                )
                if not (
                    target_plant.species_id < len(pred_row) and pred_row[target_plant.species_id]
                ):
                    on_incompatible_plant = True
                    continue

                effective_velocity = max(1, swarm.velocity)
                consumed = min(
                    (swarm.consumption_rate / effective_velocity) * swarm.population,
                    target_plant.energy,
                )

                target_plant.energy -= consumed
                env.set_plant_energy(
                    target_plant.x,
                    target_plant.y,
                    target_plant.species_id,
                    target_plant.energy,
                )
                swarm.energy += consumed

                if consumed > 0:
                    ate_anything = True

                # Kill plant if energy below threshold
                if target_plant.energy < target_plant.survival_threshold:
                    if plant_death_causes is not None:
                        plant_death_causes["death_herbivore_feeding"] = (
                            plant_death_causes.get("death_herbivore_feeding", 0) + 1
                        )
                    env.clear_plant_energy(
                        target_plant.x,
                        target_plant.y,
                        target_plant.species_id,
                    )
                    world.unregister_position(co_eid, target_plant.x, target_plant.y)
                    world.collect_garbage([co_eid])

            # Behavioral overrides based on feeding success.
            if ate_anything:
                # Arrestment reflex: valid food contact clears panic/repel state immediately.
                swarm.repelled = False
                swarm.repelled_ticks_remaining = 0
            elif on_incompatible_plant:
                # Taste rejection: incompatible plant contact triggers a short random walk.
                swarm.repelled = True
                swarm.repelled_ticks_remaining = 2

        # ----------------------------------------------------------------
        # 4. Metabolic upkeep and deficit attrition
        # ----------------------------------------------------------------
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
                swarm.population - previous_population,
            )
            total_casualty_energy = casualties * swarm.energy_min
            leftover_energy = total_casualty_energy - deficit
            swarm.energy = max(0.0, leftover_energy)

        # ----------------------------------------------------------------
        # 5. Death check
        # ----------------------------------------------------------------
        if swarm.population <= 0:
            world.unregister_position(entity.entity_id, swarm.x, swarm.y)
            dead_swarms.append(entity.entity_id)
            continue

        # ----------------------------------------------------------------
        # 6. Reproduction: convert only swarm-scale surplus energy into growth
        # ----------------------------------------------------------------
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
                    swarm.population - previous_population,
                )
                swarm.energy -= new_individuals * cost_per_offspring

        # ----------------------------------------------------------------
        # 7. Mitosis
        # ----------------------------------------------------------------
        split_threshold = (
            swarm.split_population_threshold
            if swarm.split_population_threshold > 0
            else 2 * swarm.initial_population
        )
        if swarm.population >= split_threshold:
            pre_split_population = swarm.population
            offspring = _perform_mitosis(swarm, world, env)
            _accumulate_tile_population(
                tile_populations,
                swarm.x,
                swarm.y,
                swarm.population - pre_split_population,
            )
            _accumulate_tile_population(
                tile_populations,
                offspring.x,
                offspring.y,
                offspring.population,
            )

    world.collect_garbage(dead_swarms)
