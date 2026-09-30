# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Data models for the server-side draft state."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from phids.api.schemas.placement import PlacementStrategy
    from phids.api.schemas.responses import BatchJobState
    from phids.api.schemas.species import (
        FloraSpeciesParams,
        HerbivoreSpeciesParams,
    )
    from phids.api.ui_state.placements import PlacedPlant, PlacedSwarm
    from phids.api.ui_state.substances import SubstanceDefinition
    from phids.api.ui_state.triggers import TriggerRule


@dataclasses.dataclass
class DraftState:
    """Server-side draft configuration accumulator for the builder UI.

    Attributes:
        scenario_name: Human-readable label used in the UI header.
        grid_width: Biotope width in cells (ge=1).
        grid_height: Biotope height in cells (ge=1).
        max_ticks: Simulation tick budget.
        tick_rate_hz: WebSocket streaming rate in ticks per second.
        wind_x: Initial uniform wind x-component.
        wind_y: Initial uniform wind y-component.
        num_signals: Number of airborne signal layers.
        num_toxins: Number of toxin layers.
        z2_flora_species_extinction: Halt when this flora species goes extinct (-1 disables).
        z4_herbivore_species_extinction: Halt when this herbivore species goes extinct (-1 disables).
        z6_max_total_flora_energy: Halt when total flora energy exceeds this threshold (-1 disables).
        z7_max_total_herbivore_population: Halt when herbivore population exceeds this threshold
            (-1 disables).
        signal_decay_factor: Per-tick airborne signal retention after Gaussian diffusion (0.0-1.0).
        substance_emit_rate: Concentration increment added per tick when an active substance emits.
        mycorrhizal_inter_species: Allow root connections across species.
        mycorrhizal_connection_cost: Energy to establish a root link.
        mycorrhizal_growth_interval_ticks: Ticks between root-growth attempts.
        mycorrhizal_signal_velocity: Signal hops per tick through roots.
        flora_species: Flora species parameter list (species_id == index).
        herbivore_species: Herbivore species parameter list (species_id == index).
        diet_matrix: Boolean matrix ``[herbivore_idx][flora_idx]`` for edibility.
        trigger_rules: List of explicit chemical-defense trigger rules.
            Multiple rules per (flora, herbivore) pair are allowed.
        substance_definitions: Named substance registry indexed by substance_id.
        initial_plants: Plants placed on the grid before simulation start.
        initial_swarms: Swarms placed on the grid before simulation start.
        active_batch_jobs: Registry of batch simulation jobs keyed by job_id.

    """

    scenario_name: str = "Default Scenario"
    grid_width: int = 64
    grid_height: int = 64
    max_ticks: int = 1000
    tick_rate_hz: float = 10.0
    wind_x: float = 0.0
    wind_y: float = 0.0
    num_signals: int = 4
    num_toxins: int = 4
    z2_flora_species_extinction: int = -1
    z4_herbivore_species_extinction: int = -1
    z6_max_total_flora_energy: float = -1.0
    z7_max_total_herbivore_population: int = -1
    signal_decay_factor: float = 0.85
    substance_emit_rate: float = 0.1
    mycorrhizal_inter_species: bool = False
    mycorrhizal_connection_cost: float = 1.0
    mycorrhizal_growth_interval_ticks: int = 8
    mycorrhizal_signal_velocity: int = 1
    flora_species: list[FloraSpeciesParams] = dataclasses.field(default_factory=list)
    herbivore_species: list[HerbivoreSpeciesParams] = dataclasses.field(default_factory=list)
    diet_matrix: list[list[bool]] = dataclasses.field(default_factory=list)
    trigger_rules: list[TriggerRule] = dataclasses.field(default_factory=list)
    substance_definitions: list[SubstanceDefinition] = dataclasses.field(default_factory=list)
    placement_mode: Literal["manual", "procedural"] = "manual"
    flora_placement_strategy: PlacementStrategy | None = None
    herbivore_placement_strategy: PlacementStrategy | None = None
    initial_plants: list[PlacedPlant] = dataclasses.field(default_factory=list)
    initial_swarms: list[PlacedSwarm] = dataclasses.field(default_factory=list)
    active_batch_jobs: dict[str, BatchJobState] = dataclasses.field(default_factory=dict)

    @classmethod
    def default(cls) -> DraftState:
        """Create the built-in default draft state.

        Returns:
            DraftState: The default draft state.
        """
        from phids.api.schemas.species import (
            FloraSpeciesParams,
            HerbivoreSpeciesParams,
        )

        state = cls(
            flora_species=[
                FloraSpeciesParams(
                    species_id=0,
                    name="Grass",
                    base_energy=10.0,
                    max_energy=100.0,
                    growth_rate=5.0,
                    survival_threshold=1.0,
                    reproduction_interval=10,
                    seed_min_dist=1.0,
                    seed_max_dist=3.0,
                    seed_energy_cost=5.0,
                    triggers=[],
                )
            ],
            herbivore_species=[
                HerbivoreSpeciesParams(
                    species_id=0,
                    name="Herbivore",
                    energy_min=5.0,
                    velocity=2,
                    consumption_rate=10.0,
                )
            ],
            diet_matrix=[[True]],
            trigger_rules=[],
            substance_definitions=[],
            initial_plants=[],
            initial_swarms=[],
        )
        return state
