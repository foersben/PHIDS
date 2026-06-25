"""Herbivore swarm ECS component dataclass encoding per-entity herbivore runtime state.

This module defines :class:`SwarmComponent`, the data container attached to every herbivore
swarm entity in the PHIDS Entity-Component-System world. Each swarm entity represents a
spatially co-located cohort of individual herbivores sharing a common species identity, energy
pool, and movement state. The ``population`` field tracks the integer head-count of the cohort;
it is decremented by metabolic attrition when the swarm's energy reserve falls below the
individual-level minimum (``energy_min``) and incremented by reproduction when sufficient surplus
energy accumulates. When ``population`` reaches the ``split_population_threshold``, the swarm
undergoes mitosis: the cohort is divided into two halves and a new entity carrying the offspring
half is registered in the ECS world and spatial hash.

The ``velocity`` field encodes the movement period in ticks between grid-cell relocations;
together with ``move_cooldown``, it implements a discrete movement-frequency mechanism that
decouples slow-moving species from the per-tick grid update cycle. Movement decisions are
mediated by the scalar flow-field gradient, which encodes plant energy attractors and toxin
repellers computed by the Numba-accelerated flow-field kernel. When a swarm encounters a
repellent toxin, ``repelled`` is set and ``repelled_ticks_remaining`` governs the duration of the
subsequent random-walk dispersal phase that overrides gradient navigation.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SwarmComponent:
    """Holds runtime state for a single herbivore swarm entity.

    Attributes:
        entity_id: ECS entity identifier.
        species_id: Herbivore species index.
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
        move_cooldown: Ticks remaining until the next movement.
        last_dx: Last movement delta on the x-axis (-1, 0, 1).
        last_dy: Last movement delta on the y-axis (-1, 0, 1).
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
    move_cooldown: int = 0
    last_dx: int = 0
    last_dy: int = 0
