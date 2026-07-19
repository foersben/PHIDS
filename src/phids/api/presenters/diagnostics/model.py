"""Diagnostics model context presenters."""

from typing import TypedDict

from phids.engine.components.plant import PlantComponent
from phids.engine.components.substances import SubstanceComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.loop import SimulationLoop


class LiveSummary(TypedDict):
    """Structured live-runtime counters for diagnostics and status rendering."""

    tick: int
    running: bool
    paused: bool
    terminated: bool
    termination_reason: str | None
    plants: int
    swarms: int
    active_substances: int


class EnergyDeficitSwarmRow(TypedDict):
    """One leaderboard row describing a swarm with positive metabolic energy deficit."""

    entity_id: int
    name: str
    population: int
    energy_deficit: float
    x: int
    y: int
    repelled: bool


def build_live_summary(sim_loop: SimulationLoop | None) -> LiveSummary | None:
    """Aggregate coarse live-model counters for diagnostics surfaces.

    Args:
        sim_loop: Active simulation loop instance, or None if draft mode.

    Returns:
        Summary counters when a live loop exists, otherwise ``None``.
    """
    if sim_loop is None:
        return None

    world = sim_loop.world
    plants = sum(1 for _ in world.query(PlantComponent))
    swarms = sum(1 for _ in world.query(SwarmComponent))
    active_substances = 0
    for entity in world.query(SubstanceComponent):
        substance = entity.get_component(SubstanceComponent)
        if substance.active or substance.synthesis_remaining > 0 or substance.aftereffect_remaining_ticks > 0:
            active_substances += 1

    return {
        "tick": sim_loop.tick,
        "running": sim_loop.running,
        "paused": sim_loop.paused,
        "terminated": sim_loop.terminated,
        "termination_reason": sim_loop.termination_reason,
        "plants": plants,
        "swarms": swarms,
        "active_substances": active_substances,
    }


def build_energy_deficit_swarms(sim_loop: SimulationLoop | None) -> list[EnergyDeficitSwarmRow]:
    """Rank live swarms by metabolic energy deficit severity.

    Args:
        sim_loop: Active simulation loop instance, or None if draft mode.

    Returns:
        Sorted stress records for swarm entities with positive energy deficits.
    """
    if sim_loop is None:
        return []

    herbivore_names = {species.species_id: species.name for species in sim_loop.config.herbivore_species}
    energy_stressed: list[EnergyDeficitSwarmRow] = []
    for entity in sim_loop.world.query(SwarmComponent):
        swarm = entity.get_component(SwarmComponent)
        energy_deficit = float(max(0.0, swarm.population * swarm.energy_min - swarm.energy))
        if energy_deficit <= 0.0:
            continue
        energy_stressed.append(
            {
                "entity_id": swarm.entity_id,
                "name": herbivore_names.get(swarm.species_id, f"Herbivore {swarm.species_id}"),
                "population": swarm.population,
                "energy_deficit": energy_deficit,
                "x": swarm.x,
                "y": swarm.y,
                "repelled": swarm.repelled,
            }
        )
    energy_stressed.sort(
        key=lambda swarm: (
            -swarm["energy_deficit"],
            swarm["name"],
        )
    )
    return energy_stressed[:12]
