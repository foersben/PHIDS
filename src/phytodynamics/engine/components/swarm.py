"""Herbivore Swarm ECS component (data-only dataclass)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SwarmComponent:
    """Holds runtime state for a single herbivore swarm entity.

    Attributes
    ----------
    entity_id:
        ECS entity identifier.
    species_id:
        Predator species index.
    x, y:
        Current grid coordinates.
    population:
        Current swarm head-count n(t).
    initial_population:
        Head-count at spawn n(0); used to detect mitosis threshold.
    energy:
        Current energy reserve.
    energy_min:
        Minimum energy per individual E_min(e_h).
    velocity:
        Movement period v_h – ticks between spatial translations.
    consumption_rate:
        Per-tick consumption scalar η(C_i).
    starvation_ticks:
        Consecutive ticks without adequate caloric intake.
    repelled:
        True when a repellent toxin is active.
    repelled_ticks_remaining:
        Remaining ticks in random-walk / inverted gradient mode.
    target_plant_id:
        ECS entity id of the currently targeted plant (-1 = none).
    move_cooldown:
        Ticks remaining until next movement is permitted.
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
    starvation_ticks: int = 0
    repelled: bool = False
    repelled_ticks_remaining: int = 0
    target_plant_id: int = -1
    move_cooldown: int = 0
