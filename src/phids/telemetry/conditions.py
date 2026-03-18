"""Termination condition evaluators (Z1–Z7) for deterministic simulation halting.

This module implements the rule-based termination logic that determines when a PHIDS simulation
run should end. Seven named termination conditions are supported: Z1 halts when the configured
maximum tick count is reached; Z2 halts when a specified flora species goes extinct (zero
remaining plant entities with that species identifier); Z3 halts when all flora entities are
extinct; Z4 and Z5 apply the analogous extinction conditions to herbivore species; Z6 halts when
total aggregate flora energy exceeds a configured upper bound (modelling uncontrolled biomass
expansion); and Z7 halts when total aggregate herbivore population exceeds a configured upper
bound (modelling herbivore outbreak conditions).

All conditions are evaluated by a single pass over live ECS component queries, keeping the
computational cost proportional to the number of living entities rather than to any grid
dimension. Conditions with negative threshold values are disabled by convention, enabling
selective activation of any subset of the seven rules for a given scenario. The
:class:`TerminationResult` dataclass encodes both the terminated flag and a human-readable
reason string, which is logged and surfaced through the REST API ``/api/simulation/status``
endpoint when the simulation halts.
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
    z4_herbivore_species: int = -1,
    z5_check_all_herbivores: bool = True,
    z6_max_flora_energy: float = -1.0,
    z7_max_total_herbivore_population: int = -1,
) -> TerminationResult:
    """Evaluate termination conditions and return the first triggered one.

    Args:
        world: ECS world registry.
        tick: Current simulation tick.
        max_ticks: Z1 – maximum allowed ticks (halt when reached).
        z2_flora_species: Species id that triggers Z2 on extinction (-1 disables).
        z3_check_all_flora: If True, halt when all flora are extinct (Z3).
        z4_herbivore_species: Species id that triggers Z4 on extinction (-1 disables).
        z5_check_all_herbivores: If True, halt when all herbivores are extinct (Z5).
        z6_max_flora_energy: Aggregate flora energy threshold for Z6 (-1 disables).
        z7_max_total_herbivore_population: Aggregate herbivore population threshold for Z7 (-1 disables).

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
    if 0.0 < z6_max_flora_energy < total_flora_energy:
        return TerminationResult(
            terminated=True,
            reason=f"Z6: total flora energy {total_flora_energy:.1f} > {z6_max_flora_energy}",
        )

    # Gather live herbivores
    herbivore_species_alive: set[int] = set()
    total_herbivore_population = 0
    herbivores_alive = False
    for entity in world.query(SwarmComponent):
        swarm: SwarmComponent = entity.get_component(SwarmComponent)
        herbivore_species_alive.add(swarm.species_id)
        total_herbivore_population += swarm.population
        herbivores_alive = True

    # Z4 – specific herbivore species extinction
    if z4_herbivore_species >= 0 and z4_herbivore_species not in herbivore_species_alive:
        return TerminationResult(
            terminated=True, reason=f"Z4: herbivore species {z4_herbivore_species} extinct"
        )

    # Z5 – all herbivores extinct
    if z5_check_all_herbivores and not herbivores_alive:
        return TerminationResult(terminated=True, reason="Z5: all herbivores extinct")

    # Z7 – aggregate herbivore population exceeds upper bound
    if 0 < z7_max_total_herbivore_population < total_herbivore_population:
        return TerminationResult(
            terminated=True,
            reason=(
                f"Z7: total herbivore population {total_herbivore_population} "
                f"> {z7_max_total_herbivore_population}"
            ),
        )

    return TerminationResult(terminated=False, reason="")
