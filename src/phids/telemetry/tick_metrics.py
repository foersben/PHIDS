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

from phids.engine.components.plant import PlantComponent
from phids.engine.components.substances import SubstanceComponent
from phids.engine.components.swarm import SwarmComponent
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


def collect_tick_metrics(world: ECSWorld) -> TickMetrics:
    """Aggregate one shared snapshot of live ECS metrics from the current world.

    Args:
        world: ECS world sampled after ordered system execution for the tick.

    Returns:
        TickMetrics: Shared aggregate metrics suitable for telemetry and termination.
    """
    metrics = TickMetrics()

    for entity in world.query(PlantComponent):
        plant: PlantComponent = entity.get_component(PlantComponent)
        species_id = int(plant.species_id)
        metrics.flora_population += 1
        metrics.flora_alive = True
        metrics.total_flora_energy += float(plant.energy)
        metrics.flora_species_alive.add(species_id)
        metrics.plant_pop_by_species[species_id] = (
            metrics.plant_pop_by_species.get(species_id, 0) + 1
        )
        metrics.plant_energy_by_species[species_id] = metrics.plant_energy_by_species.get(
            species_id, 0.0
        ) + float(plant.energy)

    for entity in world.query(SwarmComponent):
        swarm: SwarmComponent = entity.get_component(SwarmComponent)
        species_id = int(swarm.species_id)
        population = int(swarm.population)
        metrics.herbivore_clusters += 1
        metrics.herbivores_alive = True
        metrics.herbivore_population += population
        metrics.total_herbivore_population += population
        metrics.herbivore_species_alive.add(species_id)
        metrics.swarm_pop_by_species[species_id] = (
            metrics.swarm_pop_by_species.get(species_id, 0) + population
        )

    for entity in world.query(SubstanceComponent):
        substance: SubstanceComponent = entity.get_component(SubstanceComponent)
        if not substance.active or substance.energy_cost_per_tick <= 0.0:
            continue
        owner = (
            world.get_entity(substance.owner_plant_id)
            if world.has_entity(substance.owner_plant_id)
            else None
        )
        if owner is None or not owner.has_component(PlantComponent):
            continue
        owner_plant: PlantComponent = owner.get_component(PlantComponent)
        owner_species_id = int(owner_plant.species_id)
        metrics.defense_cost_by_species[owner_species_id] = metrics.defense_cost_by_species.get(
            owner_species_id, 0.0
        ) + float(substance.energy_cost_per_tick)

    return metrics
