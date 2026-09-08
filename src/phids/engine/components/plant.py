# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from phids.api.schemas.species import FloraSpeciesParams


@dataclass(slots=True)
class PlantComponent:
    """Holds runtime state for a single plant entity.

    Implements the Decoupled Dual-Proxy Architecture, where plant state is split across
    two orthogonal biological quantities:

    - ``energy`` (E_current): Short-term, volatile caloric health (leaves, accessible sugars,
      phloem). Increased by photosynthesis; reduced by herbivory, mycorrhizal taxes, and
      defense synthesis. A plant dies when this drops below ``survival_threshold``.
    - ``structural_mass`` (M_structural): Long-term, permanent structural growth (lignin,
      woodiness, root depth). Monotonically non-decreasing - it is never reduced by herbivory.
      Trampling vulnerability and morphological defenses are evaluated against this proxy, not
      against ``energy``, so a heavily grazed adult plant retains its structural resilience.

    Attributes:
        entity_id: ECS entity identifier.
        species_id: Flora species index.
        x, y: Current grid coordinates.
        energy: Current caloric energy reserve (E_current proxy). Alias for E_i,j(t).
        max_energy: Species-specific caloric capacity E_max.
        base_energy: Initial caloric energy used by growth formula.
        growth_rate: Per-tick photosynthetic growth rate in percent.
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
        apparent_nutrition_factor: Stress-induced nutrient discount modifier.
        withdrawal_ticks_remaining: Ticks until nutrition factor reverts to 1.0.
        structural_mass: Permanent structural mass accumulation (M_structural proxy).
            Represents lignin, woodiness, and root depth. Defaults to 0.0 (seed stage).
            Never reduced by herbivory. Written by the lifecycle system each slow-tick.
        max_structural_mass: Species-level ceiling for structural mass. Placeholder:
            defaults to ``max_energy`` until Plan 2 adds a dedicated DB column.

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
    mycorrhizal_tax_per_link: float = 0.0
    apparent_nutrition_factor: float = 1.0
    target_nutrition_factor: float = 1.0
    translocation_rate: float = 0.2
    withdrawal_ticks_remaining: int = 0
    # ------------------------------------------------------------------
    # Dual-Proxy Architecture fields (M_structural)
    # ------------------------------------------------------------------
    structural_mass: float = 0.0  # M_structural: permanent lignin/woodiness
    max_structural_mass: float = 0.0  # Species ceiling for M_structural (sourced from DB via FloraSpeciesParams)
    growth_rate_structural: float = 0.01  # Fractional M_structural growth per slow-loop gate

    @classmethod
    def from_params(
        cls,
        *,
        entity_id: int,
        species_id: int,
        x: int,
        y: int,
        params: FloraSpeciesParams,
        energy: float | None = None,
        structural_mass: float | None = None,
        last_reproduction_tick: int = 0,
    ) -> PlantComponent:
        """Construct a PlantComponent instance from species configuration parameters.

        Maps species-level allometric and kinematic parameters into the per-entity
        runtime state container, applying default fallback logic for structural mass
        and initial energy if not explicitly specified.

        Args:
            entity_id: Unique integer identifier assigned by the ECSWorld.
            species_id: Flora species index corresponding to the configuration parameters.
            x: Grid x-coordinate in [0, width - 1].
            y: Grid y-coordinate in [0, height - 1].
            params: Validated FloraSpeciesParams declaring allometric thresholds and kinetics.
            energy: Initial caloric energy reserve. Defaults to params.base_energy if None.
            structural_mass: Initial structural mass proxy. Defaults to 0.0 if None.
            last_reproduction_tick: Simulation tick of last reproduction event. Defaults to 0.

        Returns:
            PlantComponent: Initialized plant entity component instance.
        """
        effective_energy = energy if energy is not None else params.base_energy
        effective_max_struct = (
            params.structural_mass_max if getattr(params, "structural_mass_max", 0.0) > 0.0 else params.max_energy
        )
        effective_struct = structural_mass if structural_mass is not None else 0.0

        return cls(
            entity_id=entity_id,
            species_id=species_id,
            x=x,
            y=y,
            energy=effective_energy,
            max_energy=params.max_energy,
            base_energy=params.base_energy,
            growth_rate=params.growth_rate,
            survival_threshold=params.survival_threshold,
            reproduction_interval=params.reproduction_interval,
            seed_min_dist=params.seed_min_dist,
            seed_max_dist=params.seed_max_dist,
            seed_energy_cost=params.seed_energy_cost,
            seed_drop_height=params.seed_drop_height,
            seed_terminal_velocity=params.seed_terminal_velocity,
            camouflage=params.camouflage,
            camouflage_factor=params.camouflage_factor,
            last_reproduction_tick=last_reproduction_tick,
            translocation_rate=params.translocation_rate,
            mycorrhizal_tax_per_link=params.mycorrhizal_tax_per_link,
            structural_mass=effective_struct,
            max_structural_mass=effective_max_struct,
            growth_rate_structural=params.structural_growth_rate,
        )
