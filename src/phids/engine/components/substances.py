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
        synthesis_duration: Configured synthesis duration in ticks.
        synthesis_remaining: Ticks remaining before activation.
        active: Whether the substance is currently active.
        aftereffect_ticks: Configured aftereffect duration after trigger removal.
        aftereffect_remaining_ticks: Remaining aftereffect duration at runtime.
        lethal: Whether the toxin is lethal.
        lethality_rate: Individuals eliminated per tick when lethal.
        repellent: Whether the toxin repels swarms.
        repellent_walk_ticks: Duration of repelled random-walk in ticks.
        precursor_signal_id: Single required precursor signal id (-1 = none). Legacy.
        precursor_signal_ids: All signal ids that must ALL be active before this
            substance activates (AND logic).  Empty tuple = no precursor required.
        activation_condition: Optional nested activation predicate tree stored
            in JSON-serialisable form for runtime evaluation and tooltip display.
        energy_cost_per_tick: Energy drained from the owner plant per active tick.
        irreversible: Whether activation remains permanently on once active.
        triggered_this_tick: Whether the trigger condition was satisfied in the
            current signaling pass.
    """

    entity_id: int
    substance_id: int
    owner_plant_id: int
    is_toxin: bool = False
    synthesis_duration: int = 0
    synthesis_remaining: int = 0
    active: bool = False
    aftereffect_ticks: int = 0
    aftereffect_remaining_ticks: int = 0
    lethal: bool = False
    lethality_rate: float = 0.0
    repellent: bool = False
    repellent_walk_ticks: int = 0
    precursor_signal_id: int = -1
    precursor_signal_ids: tuple[int, ...] = ()
    activation_condition: dict[str, object] | None = None
    energy_cost_per_tick: float = 0.0
    irreversible: bool = False
    trigger_predator_species_id: int = -1
    trigger_min_predator_population: int = 0
    triggered_this_tick: bool = False
