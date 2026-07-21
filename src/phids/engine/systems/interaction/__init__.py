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

from typing import TYPE_CHECKING

from phids.engine.components.swarm import SwarmComponent
from phids.engine.systems.interaction.feeding import _resolve_swarm_feeding
from phids.engine.systems.interaction.metabolism import _resolve_swarm_metabolism_and_reproduction
from phids.engine.systems.interaction.movement import (
    _choose_neighbour_by_flow_probability as _choose_neighbour_by_flow_probability,
)
from phids.engine.systems.interaction.movement import _random_walk_step as _random_walk_step
from phids.engine.systems.interaction.movement import _resolve_swarm_movement
from phids.engine.systems.interaction.population import TILE_CARRYING_CAPACITY as TILE_CARRYING_CAPACITY
from phids.engine.systems.interaction.population import _accumulate_tile_population
from phids.engine.systems.interaction.population import _co_located_swarm_population as _co_located_swarm_population

if TYPE_CHECKING:
    from phids.api.schemas import FloraSpeciesParams, HerbivoreSpeciesParams
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld
import numpy as np
import numpy.typing as npt


def run_interaction(
    world: ECSWorld,
    env: GridEnvironment,
    diet_matrix: list[list[bool]],
    flora_species_params: list[FloraSpeciesParams],
    herbivore_species_params: list[HerbivoreSpeciesParams],
    tick: int,  # noqa: ARG001
    plant_death_causes: dict[str, int] | None = None,
    herbivore_death_causes: dict[str, int] | None = None,
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
        herbivore_death_causes: The herbivore death causes.
    """
    dead_swarms: list[int] = []
    tile_populations: list[int] = [0] * (env.width * env.height)

    # Pre-allocate scratch buffers for zero-allocation Numba JIT movement
    scratch_cx: npt.NDArray[np.int32] = np.empty(5, dtype=np.int32)
    scratch_cy: npt.NDArray[np.int32] = np.empty(5, dtype=np.int32)
    scratch_scores: npt.NDArray[np.float64] = np.empty(5, dtype=np.float64)
    scratch_adjusted: npt.NDArray[np.float64] = np.empty(5, dtype=np.float64)
    scratch_weights: npt.NDArray[np.float64] = np.empty(5, dtype=np.float64)

    # Initial population accumulation pass
    for eid in world._component_index.get(SwarmComponent, set()):
        # ⚡ Bolt Optimization: Rely on ECS lifecycle invariants.
        # _component_index is strictly synchronized with _entities during this read-only pass.
        indexed_swarm = world._entities[eid]._components[SwarmComponent]
        _accumulate_tile_population(
            tile_populations,
            indexed_swarm.x,
            indexed_swarm.y,
            env.width,
            indexed_swarm.population,
        )

    # Main interaction loop
    for eid in tuple(world._component_index.get(SwarmComponent, set())):
        # We must keep the defensive .get() here because entities can be destroyed mid-loop.
        entity = world._entities.get(eid)
        if entity is None:
            continue
        # ⚡ Bolt Optimization: Rely on ECS lifecycle invariants.
        swarm: SwarmComponent = entity._components[SwarmComponent]

        # 1-2. Movement Phase
        has_moved = _resolve_swarm_movement(
            swarm,
            entity,
            env,
            world,
            diet_matrix,
            tile_populations,
            scratch_cx,
            scratch_cy,
            scratch_scores,
            scratch_adjusted,
            scratch_weights,
        )

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

        # 4. Metabolism & Reproduction
        if not swarm.repelled:
            _resolve_swarm_metabolism_and_reproduction(
                swarm, entity, world, env, tile_populations, dead_swarms, scratch_cx, scratch_cy, herbivore_death_causes
            )

    world.collect_garbage(dead_swarms)
