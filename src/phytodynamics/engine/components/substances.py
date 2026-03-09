"""Substance (signal / toxin) ECS component (data-only dataclass)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SubstanceComponent:
    """Holds runtime state for a single substance entity.

    A substance is either a volatile signal (VOC) or a toxin produced
    by a plant in response to herbivore attack.

    Attributes
    ----------
    entity_id:
        ECS entity identifier.
    substance_id:
        Layer index into signal_layers or toxin_layers.
    owner_plant_id:
        ECS entity id of the producing plant.
    is_toxin:
        True for toxins; False for signals.
    synthesis_remaining:
        Ticks of synthesis still required before the substance becomes active.
    active:
        Whether the substance is currently active / being emitted.
    aftereffect_ticks:
        Remaining ticks of aftereffect T_k after the trigger condition is gone.
    lethal:
        True if this toxin has a lethal effect.
    lethality_rate:
        Individuals eliminated per tick β(s_x, C_i).
    repellent:
        True if this toxin has a repellent effect.
    repellent_walk_ticks:
        Ticks of random-walk k triggered on a repel event.
    precursor_signal_id:
        substance_id of the signal that must be active before this toxin can
        be synthesised (-1 means no precursor required).
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
