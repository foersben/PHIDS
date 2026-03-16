"""Plant ECS component dataclass encoding per-entity flora runtime state.

This module defines :class:`PlantComponent`, the data container attached to every flora entity in
the PHIDS Entity-Component-System world. Each plant entity carries its own independent energy
reserve, spatial grid coordinates, species-level growth and reproduction parameters, camouflage
properties, and the set of identifiers of currently connected mycorrhizal partners. The strict
separation between species-level parameters (which reside in the scenario configuration) and
per-entity mutable state (which resides in ``PlantComponent``) is central to the data-oriented
design: the lifecycle and signaling systems iterate over ``PlantComponent`` instances via the ECS
query interface without requiring access to the configuration layer.

The ``energy`` field encodes the biological fitness proxy E_i,j(t); its dynamics are governed by
the growth term applied each lifecycle tick, the seed dispersal cost deducted at reproduction,
the connection cost subtracted when a new mycorrhizal link is established, the herbivory loss
inflicted by co-located swarms in the interaction phase, and the defense maintenance cost imposed
by active ``SubstanceComponent`` entities in the signaling phase. A plant entity is culled when
``energy < survival_threshold``, with the cause of terminal energy loss attributed via
``last_energy_loss_cause`` for per-category death diagnostics.
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
        seed_drop_height: Effective release height used to estimate airborne seed flight time.
        seed_terminal_velocity: Effective terminal velocity used in wind-shift estimation.
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
    seed_drop_height: float = 1.25
    seed_terminal_velocity: float = 0.8
    camouflage: bool = False
    camouflage_factor: float = 1.0
    last_reproduction_tick: int = 0
    last_energy_loss_cause: str | None = None
    mycorrhizal_connections: set[int] = field(default_factory=set)
