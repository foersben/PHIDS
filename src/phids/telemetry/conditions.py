"""Termination condition evaluators (Z1–Z7).

Provide checks for simulation termination conditions such as maximum ticks,
species extinction and aggregate population/energy thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass

from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.ecs import ECSWorld


@dataclass(slots=True)
class TerminationResult:
    """Result returned by :func:`check_termination`.

    Attributes:
        terminated: True when a termination condition has been met.
        reason: Human-readable explanation for termination.
    """

    terminated: bool
    reason: str


def check_termination(
    world: ECSWorld,
    tick: int,
    max_ticks: int,
    z2_flora_species: int = -1,
    z3_check_all_flora: bool = True,
    z4_predator_species: int = -1,
    z5_check_all_predators: bool = True,
    z6_max_flora_energy: float = -1.0,
    z7_max_predator_population: int = -1,
) -> TerminationResult:
    """Evaluate termination conditions and return the first triggered one.

    Args:
        world: ECS world registry.
        tick: Current simulation tick.
        max_ticks: Z1 – maximum allowed ticks (halt when reached).
        z2_flora_species: Species id that triggers Z2 on extinction (-1 disables).
        z3_check_all_flora: If True, halt when all flora are extinct (Z3).
        z4_predator_species: Species id that triggers Z4 on extinction (-1 disables).
        z5_check_all_predators: If True, halt when all predators are extinct (Z5).
        z6_max_flora_energy: Aggregate flora energy threshold for Z6 (-1 disables).
        z7_max_predator_population: Aggregate predator population threshold for Z7 (-1 disables).

    Returns:
        TerminationResult: Object indicating whether termination occurred and why.
    """
    # Z1 – maximum tick count
    if tick >= max_ticks:
        return TerminationResult(terminated=True, reason=f"Z1: reached max_ticks={max_ticks}")

    # Gather live flora
    flora_species_alive: set[int] = set()
    total_flora_energy = 0.0
    flora_alive = False
    for entity in world.query(PlantComponent):
        plant: PlantComponent = entity.get_component(PlantComponent)
        flora_species_alive.add(plant.species_id)
        total_flora_energy += plant.energy
        flora_alive = True

    # Z2 – specific flora species extinction
    if z2_flora_species >= 0 and z2_flora_species not in flora_species_alive:
        return TerminationResult(
            terminated=True, reason=f"Z2: flora species {z2_flora_species} extinct"
        )

    # Z3 – all flora extinct
    if z3_check_all_flora and not flora_alive:
        return TerminationResult(terminated=True, reason="Z3: all flora extinct")

    # Z6 – aggregate flora energy exceeds upper bound
    if z6_max_flora_energy > 0.0 and total_flora_energy > z6_max_flora_energy:
        return TerminationResult(
            terminated=True,
            reason=f"Z6: total flora energy {total_flora_energy:.1f} > {z6_max_flora_energy}",
        )

    # Gather live predators
    predator_species_alive: set[int] = set()
    total_predator_population = 0
    predators_alive = False
    for entity in world.query(SwarmComponent):
        swarm: SwarmComponent = entity.get_component(SwarmComponent)
        predator_species_alive.add(swarm.species_id)
        total_predator_population += swarm.population
        predators_alive = True

    # Z4 – specific predator species extinction
    if z4_predator_species >= 0 and z4_predator_species not in predator_species_alive:
        return TerminationResult(
            terminated=True, reason=f"Z4: predator species {z4_predator_species} extinct"
        )

    # Z5 – all predators extinct
    if z5_check_all_predators and not predators_alive:
        return TerminationResult(terminated=True, reason="Z5: all predators extinct")

    # Z7 – aggregate predator population exceeds upper bound
    if z7_max_predator_population > 0 and total_predator_population > z7_max_predator_population:
        return TerminationResult(
            terminated=True,
            reason=(
                f"Z7: total predator population {total_predator_population} "
                f"> {z7_max_predator_population}"
            ),
        )

    return TerminationResult(terminated=False, reason="")
