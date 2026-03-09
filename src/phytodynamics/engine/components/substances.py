"""Substance ECS component dataclass.

Defines :class:`SubstanceComponent` for volatile signals and toxins emitted
by plants in response to herbivore presence.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SubstanceComponent:
    """Holds runtime state for a single substance entity.

    A substance represents either a volatile signal (VOC) or a toxin.

    Attributes:
        entity_id: ECS entity identifier.
        substance_id: Layer index into signal or toxin layers.
        owner_plant_id: Entity id of the producing plant.
        is_toxin: True for toxins, False for signals.
        synthesis_remaining: Ticks remaining before activation.
        active: Whether the substance is currently active.
        aftereffect_ticks: Remaining aftereffect duration after trigger removal.
        lethal: Whether the toxin is lethal.
        lethality_rate: Individuals eliminated per tick when lethal.
        repellent: Whether the toxin repels swarms.
        repellent_walk_ticks: Duration of repelled random-walk in ticks.
        precursor_signal_id: Required precursor signal id (-1 = none).
        energy_cost_per_tick: Energy drained from the owner plant per active tick.
    """

    entity_id: int
    substance_id: int
    owner_plant_id: int
    is_toxin: bool = False
    synthesis_remaining: int = 0
    active: bool = False
    aftereffect_ticks: int = 0
    lethal: bool = False
    lethality_rate: float = 0.0
    repellent: bool = False
    repellent_walk_ticks: int = 0
    precursor_signal_id: int = -1
    energy_cost_per_tick: float = 0.0
