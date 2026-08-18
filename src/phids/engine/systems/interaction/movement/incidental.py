# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Incidental mortality calculation for movement.

Provides probabilistic calculation for trampling and collateral plant destruction during swarm movement.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from numba import njit

if TYPE_CHECKING:
    from collections.abc import Mapping

    from phids.engine.components.swarm import SwarmComponent
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld


@njit(cache=True)
def _compute_trample_probability_jit(
    swarm_population: int,
    trample_factor: float,
    structural_mass: float,
    max_structural_mass: float,
    p_max: float = 0.50,
) -> float:
    """Numba-compiled single FMA branchless trampling vulnerability probability gate.

    Calculates the probability P(destroy) of a seedling or low-structural-mass plant entity
    being trampled or incidentally destroyed by a moving herbivore swarm. Bounded by p_max
    (default 0.50) per coordinate transition to maintain realistic stochastic chance.

    Args:
        swarm_population: Population count of the entering herbivore swarm.
        trample_factor: Sensitivity coefficient for incidental destruction (trampling or clipping).
        structural_mass: Current M_structural of the co-located plant entity.
        max_structural_mass: Species structural mass ceiling (from FloraSpeciesParams).
        p_max: Maximum per-step destruction probability ceiling (default 0.50).

    Returns:
        Probability P(destroy) in range [0.0, p_max].
    """
    if max_structural_mass <= 0.0:
        vulnerability = 1.0
    else:
        vulnerability = max(0.0, 1.0 - (structural_mass / max_structural_mass))
    prob = float(swarm_population) * trample_factor * vulnerability
    return min(p_max, max(0.0, prob))


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
