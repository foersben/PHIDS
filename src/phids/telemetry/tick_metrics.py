# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Tick-level ECS aggregation structures for shared telemetry and termination evaluation.

This module defines the :class:`TickMetrics` dataclass and the corresponding
:func:`collect_tick_metrics` helper, which execute a single deterministic pass
over live ECS components to materialize scalar and per-species aggregates used by
both telemetry recording and termination-condition evaluation. The explicit
shared-aggregation contract eliminates duplicated component scans in the hot
simulation loop while preserving strict data-oriented semantics.

The collector accumulates flora and herbivore populations, aggregate energies,
species-presence sets, and active defense-maintenance costs attributed to flora
species through owner-linked substance components. These metrics encode both the
biological observables (population size, energetic state, active chemical
maintenance burden) and the computational invariants required by PHIDS phase
ordering, thereby allowing telemetry and termination logic to observe an
identical post-system world snapshot without divergent sampling artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from phids.engine.components.plant import PlantComponent
from phids.engine.components.substances import SubstanceComponent
from phids.engine.components.swarm import SwarmComponent

if TYPE_CHECKING:
    from phids.engine.core.ecs import ECSWorld


@dataclass(slots=True)
class TickMetrics:
    """Shared per-tick aggregate metrics for telemetry and termination consumers.

    Attributes:
        flora_population: Number of live flora entities.
        herbivore_clusters: Number of live herbivore swarm entities.
        herbivore_population: Total herbivore individuals across all swarms.
        total_flora_energy: Sum of flora energy across all live plants.
        total_herbivore_population: Alias for termination readability.
        flora_alive: Whether any flora entities are alive.
        herbivores_alive: Whether any herbivore swarms are alive.
        flora_species_alive: Set of live flora species IDs.
        herbivore_species_alive: Set of live herbivore species IDs.
        plant_pop_by_species: Flora population counts keyed by species ID.
        plant_energy_by_species: Flora aggregate energy keyed by species ID.
        swarm_pop_by_species: Herbivore population keyed by species ID.
        defense_cost_by_species: Active defense-maintenance costs keyed by flora species ID.

    """

    flora_population: int = 0
    herbivore_clusters: int = 0
    herbivore_population: int = 0
    total_flora_energy: float = 0.0
    total_herbivore_population: int = 0
    flora_alive: bool = False
    herbivores_alive: bool = False
    flora_species_alive: set[int] = field(default_factory=set)
    herbivore_species_alive: set[int] = field(default_factory=set)
    plant_pop_by_species: dict[int, int] = field(default_factory=dict)
    plant_energy_by_species: dict[int, float] = field(default_factory=dict)
    swarm_pop_by_species: dict[int, int] = field(default_factory=dict)
    defense_cost_by_species: dict[int, float] = field(default_factory=dict)
    plant_death_causes: dict[str, int] = field(default_factory=dict)
    herbivore_death_causes: dict[str, int] = field(default_factory=dict)


def collect_tick_metrics(world: ECSWorld) -> TickMetrics:
    """Aggregate one shared snapshot of live ECS metrics from the current world.

    Args:
        world: ECS world sampled after ordered system execution for the tick.

    Returns:
        TickMetrics: Shared aggregate metrics suitable for telemetry and termination.

    """
    metrics = TickMetrics()

    plant_entities = world.query(PlantComponent)
    plant_components: list[PlantComponent] = [e.get_component(PlantComponent) for e in plant_entities]
    metrics.flora_population = len(plant_components)
    metrics.flora_alive = metrics.flora_population > 0

    total_flora_energy = 0.0
    for plant in plant_components:
        species_id = int(plant.species_id)
        total_flora_energy += plant.energy
        metrics.flora_species_alive.add(species_id)
        metrics.plant_pop_by_species[species_id] = metrics.plant_pop_by_species.get(species_id, 0) + 1
        metrics.plant_energy_by_species[species_id] = (
            metrics.plant_energy_by_species.get(species_id, 0.0) + plant.energy
        )

    # Round to 6 decimals to prevent IEEE 754 ULP drift in telemetry
    metrics.total_flora_energy = round(total_flora_energy, 6)
    for sid in metrics.plant_energy_by_species:
        metrics.plant_energy_by_species[sid] = round(metrics.plant_energy_by_species[sid], 6)

    swarm_entities = world.query(SwarmComponent)
    swarm_components: list[SwarmComponent] = [e.get_component(SwarmComponent) for e in swarm_entities]
    metrics.herbivore_clusters = len(swarm_components)
    metrics.herbivores_alive = metrics.herbivore_clusters > 0

    for swarm in swarm_components:
        species_id = int(swarm.species_id)
        population = int(swarm.population)
        metrics.herbivore_population += population
        metrics.total_herbivore_population += population
        metrics.herbivore_species_alive.add(species_id)
        metrics.swarm_pop_by_species[species_id] = metrics.swarm_pop_by_species.get(species_id, 0) + population

    substance_entities = world.query(SubstanceComponent)
    substances: list[SubstanceComponent] = [e.get_component(SubstanceComponent) for e in substance_entities]
    for substance in substances:
        if not substance.active or substance.energy_cost_per_tick <= 0.0:
            continue

        owner = world._entities.get(substance.owner_plant_id)
        if owner is None or not owner.has_component(PlantComponent):
            continue

        owner_plant = owner.get_component(PlantComponent)
        owner_species_id = int(owner_plant.species_id)
        metrics.defense_cost_by_species[owner_species_id] = metrics.defense_cost_by_species.get(
            owner_species_id, 0.0
        ) + float(substance.energy_cost_per_tick)

    for sid in metrics.defense_cost_by_species:
        metrics.defense_cost_by_species[sid] = round(metrics.defense_cost_by_species[sid], 6)

    return metrics
