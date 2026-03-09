"""Plant ECS component (data-only dataclass)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class PlantComponent:
    """Holds runtime state for a single plant entity.

    Attributes
    ----------
    entity_id:
        ECS entity identifier.
    species_id:
        Flora species index.
    x, y:
        Current grid coordinates.
    energy:
        Current energy reserve E_i,j(t).
    max_energy:
        Species-specific energy capacity E_max.
    base_energy:
        Initial energy E_i,j(0) used in the growth formula.
    growth_rate:
        Per-tick growth rate r_i,j (%).
    survival_threshold:
        Minimum energy B_i,j; death occurs below this.
    reproduction_interval:
        Ticks between reproduction attempts T_i.
    seed_min_dist:
        Minimum Euclidean seed dispersal distance d_min.
    seed_max_dist:
        Maximum Euclidean seed dispersal distance d_max.
    seed_energy_cost:
        Energy deducted from parent on each reproduction event.
    camouflage:
        True if constitutive camouflage is active.
    camouflage_factor:
        Flow-field gradient multiplier when camouflaged.
    last_reproduction_tick:
        Tick number of the most recent reproduction.
    mycorrhizal_connections:
        Set of entity ids of connected plant neighbours.
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
    mycorrhizal_connections: set[int] = field(default_factory=set)
