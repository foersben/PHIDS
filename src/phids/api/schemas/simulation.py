# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Authoritative simulation configuration schema.

``SimulationConfig`` is the single validated ingress container for all data that
parameterises ``SimulationLoop`` construction. Its ``model_validator`` enforces
cross-field reference integrity between placement species identifiers and the
declared species lists before any engine state is allocated.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from phids.api.schemas.base import StrictBaseModel
from phids.api.schemas.placement import (
    InitialPlantPlacement,
    InitialSwarmPlacement,
    PlacementStrategy,
)
from phids.api.schemas.species import DietCompatibilityMatrix, FloraSpeciesParams, HerbivoreSpeciesParams
from phids.shared.constants import MAX_FLORA_SPECIES, MAX_HERBIVORE_SPECIES, MAX_SUBSTANCE_TYPES


class SimulationConfig(StrictBaseModel):
    """Complete simulation configuration payload (REST /api/scenario/load body)."""

    grid_width: int = Field(default=40, ge=1, le=200)
    grid_height: int = Field(default=40, ge=1, le=200)
    max_ticks: int = Field(default=1000, gt=0)
    tick_rate_hz: float = Field(default=10.0, gt=0.0, description="WebSocket stream tick rate.")

    num_signals: int = Field(default=4, ge=1, le=MAX_SUBSTANCE_TYPES)
    num_toxins: int = Field(default=4, ge=1, le=MAX_SUBSTANCE_TYPES)

    wind_x: float = Field(default=0.0, description="Initial wind vector x-component.")
    wind_y: float = Field(default=0.0, description="Initial wind vector y-component.")

    flora_species: list[FloraSpeciesParams] = Field(..., min_length=1, max_length=MAX_FLORA_SPECIES)
    herbivore_species: list[HerbivoreSpeciesParams] = Field(..., min_length=1, max_length=MAX_HERBIVORE_SPECIES)
    diet_matrix: DietCompatibilityMatrix

    placement_mode: Literal["manual", "procedural"] = "manual"
    flora_placement_strategy: PlacementStrategy | None = None
    herbivore_placement_strategy: PlacementStrategy | None = None

    initial_plants: list[InitialPlantPlacement] = Field(default_factory=list)
    initial_swarms: list[InitialSwarmPlacement] = Field(default_factory=list)

    # Symbiotic network settings
    mycorrhizal_inter_species: bool = Field(default=False, description="Allow inter-species root connections.")
    mycorrhizal_connection_cost: float = Field(default=1.0, ge=0.0, description="Energy cost to establish a root link.")
    mycorrhizal_growth_interval_ticks: int = Field(
        default=8,
        ge=1,
        le=256,
        description=("Ticks between mycorrhizal growth attempts. At most one new root link is formed per interval."),
    )
    mycorrhizal_signal_velocity: int = Field(default=1, gt=0, description="Signal transfer speed t_g (ticks per hop).")

    # Termination conditions
    z2_flora_species_extinction: int = Field(
        default=-1, description="Halt when this flora species id goes extinct (-1 = disabled)."
    )
    z4_herbivore_species_extinction: int = Field(
        default=-1,
        description="Halt when this herbivore species id goes extinct (-1 = disabled).",
    )
    z6_max_total_flora_energy: float = Field(
        default=-1.0, description="Halt when total flora energy exceeds this value (-1 = disabled)."
    )
    z7_max_total_herbivore_population: int = Field(
        default=-1,
        description="Halt when total herbivore population exceeds this value (-1 = disabled).",
    )

    # Configurable Chemotaxis and Navigation Parameters
    chemotaxis_alpha: float = Field(
        default=1.0,
        ge=0.0,
        description="Weighting coefficient for botanical attractants.",
        json_schema_extra={
            "ui_category": "Chemotaxis & Navigation",
            "sensitivity": "High Impact",
            "effects": ("Increasing this makes swarms more desperate to reach food, potentially ignoring toxins."),
        },
    )
    chemotaxis_beta: float = Field(
        default=1.0,
        ge=0.0,
        description="Weighting coefficient for toxic repellents.",
        json_schema_extra={
            "ui_category": "Chemotaxis & Navigation",
            "sensitivity": "High Impact",
            "effects": (
                "Increasing this makes swarms extremely averse to toxins, "
                "potentially starving before crossing a defensive perimeter."
            ),
        },
    )
    chemotaxis_decay: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Propagation decay factor for the flow field.",
        json_schema_extra={
            "ui_category": "Chemotaxis & Navigation",
            "sensitivity": "Advanced Tuning",
            "effects": (
                "Higher values allow the chemotaxis gradient to propagate further distances, "
                "effectively increasing the sensory horizon of swarms."
            ),
        },
    )
    chemotaxis_truncate_threshold: float = Field(
        default=1e-4,
        ge=0.0,
        description="Subnormal truncation threshold.",
        json_schema_extra={
            "ui_category": "Chemotaxis & Navigation",
            "sensitivity": "Advanced Math Tuning",
            "effects": (
                "Prevents float denormalization slowdowns in the Numba JIT solver "
                "by zeroing out infinitesimal gradients."
            ),
        },
    )

    # Configurable diffusion / emission constants (runtime-overridable via DSE)
    signal_decay_factor: float = Field(
        default=0.85,
        gt=0.0,
        le=1.0,
        description=(
            "Per-tick airborne signal retention after Gaussian diffusion (0.0-1.0). "
            "1.0 = no decay; values closer to 0.0 cause total dissipation each tick. "
            "Exposed in the UI as Signal Decay (%)."
        ),
    )
    substance_emit_rate: float = Field(
        default=0.1,
        gt=0.0,
        le=1.0,
        description=(
            "Concentration increment added to a signal or toxin layer per tick "
            "when an active SubstanceComponent emits into the environment. "
            "Exposed in the UI as Substance Emit Rate (%)."
        ),
    )

    # Replay backend selection
    replay_backend: str = Field(
        default="zarr",
        description="Replay storage backend.",
        pattern="^zarr$",
    )

    @model_validator(mode="after")
    def _validate_species_ids(self) -> SimulationConfig:
        flora_ids = {s.species_id for s in self.flora_species}
        herbivore_ids = {s.species_id for s in self.herbivore_species}
        for plant_placement in self.initial_plants:
            if plant_placement.species_id not in flora_ids:
                raise ValueError(
                    f"InitialPlantPlacement references unknown flora species {plant_placement.species_id}."
                )
        for swarm_placement in self.initial_swarms:
            if swarm_placement.species_id not in herbivore_ids:
                raise ValueError(
                    f"InitialSwarmPlacement references unknown herbivore species {swarm_placement.species_id}."
                )
        return self
