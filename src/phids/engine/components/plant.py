"""Plant ECS component dataclass.

This module defines the :class:`PlantComponent` dataclass which stores the
runtime state for a plant entity used by lifecycle and signaling systems.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class PlantComponent:
    """Holds runtime state for a single plant entity.

    Attributes:
        entity_id: ECS entity identifier.
        species_id: Flora species index.
        x, y: Current grid coordinates.
        energy: Current energy reserve E_i,j(t).
        max_energy: Species-specific energy capacity E_max.
        base_energy: Initial energy used by growth formula.
        growth_rate: Per-tick growth rate in percent.
        survival_threshold: Energy threshold below which the plant dies.
        reproduction_interval: Ticks between reproduction attempts.
        seed_min_dist: Minimum seed dispersal distance.
        seed_max_dist: Maximum seed dispersal distance.
        seed_energy_cost: Energy cost paid for reproduction.
        camouflage: Whether constitutive camouflage is active.
        camouflage_factor: Gradient multiplier when camouflaged.
        last_reproduction_tick: Tick of the most recent reproduction.
        last_energy_loss_cause: Most recent energetically relevant action label
            used for death diagnostics attribution.
        mycorrhizal_connections: Set of connected plant entity ids.
    """

    entity_id: int
    species_id: int
    x: int
    y: int
    energy: float
    max_energy: float
    base_energy: float
    growth_rate: float
    survival_threshold: float
    reproduction_interval: int
    seed_min_dist: float
    seed_max_dist: float
    seed_energy_cost: float
    camouflage: bool = False
    camouflage_factor: float = 1.0
    last_reproduction_tick: int = 0
    last_energy_loss_cause: str | None = None
    mycorrhizal_connections: set[int] = field(default_factory=set)
