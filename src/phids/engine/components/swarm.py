"""Herbivore Swarm ECS component dataclass.

Defines :class:`SwarmComponent` storing runtime state for a herbivore
swarm entity used by interaction and telemetry subsystems.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SwarmComponent:
    """Holds runtime state for a single herbivore swarm entity.

    Attributes:
        entity_id: ECS entity identifier.
        species_id: Predator species index.
        x, y: Current grid coordinates.
        population: Current swarm head-count.
        initial_population: Head-count at spawn; used for mitosis checks.
        energy: Current energy reserve.
        energy_min: Minimum energy per individual.
        velocity: Movement period in ticks between moves.
        consumption_rate: Per-tick consumption scalar.
        reproduction_energy_divisor: Species-level growth throttle.
        starvation_ticks: Consecutive ticks without feeding.
        repelled: Whether the swarm is currently repelled by toxin.
        repelled_ticks_remaining: Remaining ticks of repelled behavior.
        target_plant_id: Entity id of the targeted plant (-1 = none).
        move_cooldown: Ticks remaining until the next movement.
    """

    entity_id: int
    species_id: int
    x: int
    y: int
    population: int
    initial_population: int
    energy: float
    energy_min: float
    velocity: int
    consumption_rate: float
    reproduction_energy_divisor: float = 1.0
    starvation_ticks: int = 0
    repelled: bool = False
    repelled_ticks_remaining: int = 0
    target_plant_id: int = -1
    move_cooldown: int = 0
