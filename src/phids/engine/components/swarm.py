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
        energy_upkeep_per_individual: Metabolic upkeep scalar applied each tick.
        split_population_threshold: Explicit population threshold for mitosis (<=0 keeps legacy rule).
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
    energy_upkeep_per_individual: float = 0.05
    split_population_threshold: int = 0
    repelled: bool = False
    repelled_ticks_remaining: int = 0
    target_plant_id: int = -1
    move_cooldown: int = 0
