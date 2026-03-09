"""Pydantic schemas for ECS components, configuration payloads, and REST API models.

This module defines payload and response models used by the REST API as well
as schemata representing ECS components and species parameters.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, model_validator

from phytodynamics.shared.constants import (
    MAX_FLORA_SPECIES,
    MAX_PREDATOR_SPECIES,
    MAX_SUBSTANCE_TYPES,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
SpeciesId = Annotated[int, Field(ge=0, lt=MAX_FLORA_SPECIES)]
PredatorId = Annotated[int, Field(ge=0, lt=MAX_PREDATOR_SPECIES)]
SubstanceId = Annotated[int, Field(ge=0, lt=MAX_SUBSTANCE_TYPES)]


# ---------------------------------------------------------------------------
# ECS Component schemata
# ---------------------------------------------------------------------------


class PlantComponentSchema(BaseModel):
    """Pydantic schema for the Plant ECS component."""

    entity_id: int = Field(..., description="Unique ECS entity identifier.")
    species_id: SpeciesId = Field(..., description="Flora species index [0, MAX_FLORA_SPECIES).")
    x: int = Field(..., ge=0, description="Grid x-coordinate.")
    y: int = Field(..., ge=0, description="Grid y-coordinate.")
    energy: float = Field(..., ge=0.0, description="Current energy reserve (E_i,j).")
    max_energy: float = Field(..., gt=0.0, description="Species-specific energy capacity (E_max).")
    base_energy: float = Field(..., gt=0.0, description="Initial energy E_i,j(0).")
    growth_rate: float = Field(..., ge=0.0, description="Per-tick growth rate r_i,j (%).")
    survival_threshold: float = Field(
        ..., ge=0.0, description="Minimum energy B_i,j before death."
    )
    reproduction_interval: int = Field(
        ..., gt=0, description="Ticks between reproduction attempts (T_i)."
    )
    seed_min_dist: float = Field(..., ge=0.0, description="Minimum seed dispersal distance d_min.")
    seed_max_dist: float = Field(
        ..., gt=0.0, description="Maximum seed dispersal distance d_max."
    )
    seed_energy_cost: float = Field(..., ge=0.0, description="Energy cost per reproduction event.")
    camouflage: bool = Field(default=False, description="Constitutive gradient attenuation flag.")
    camouflage_factor: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Gradient multiplier when camouflaged."
    )
    last_reproduction_tick: int = Field(default=0, description="Last tick of reproduction.")


class SwarmComponentSchema(BaseModel):
    """Pydantic schema for the Herbivore Swarm ECS component."""

    entity_id: int = Field(..., description="Unique ECS entity identifier.")
    species_id: PredatorId = Field(
        ..., description="Predator species index [0, MAX_PREDATOR_SPECIES)."
    )
    x: int = Field(..., ge=0, description="Grid x-coordinate.")
    y: int = Field(..., ge=0, description="Grid y-coordinate.")
    population: int = Field(..., gt=0, description="Current swarm head-count n(t).")
    initial_population: int = Field(..., gt=0, description="Initial population n(0) for mitosis.")
    energy: float = Field(..., ge=0.0, description="Current energy reserve.")
    energy_min: float = Field(
        ..., gt=0.0, description="Minimum energy per individual E_min(e_h)."
    )
    velocity: int = Field(..., gt=0, description="Movement period v_h (ticks between moves).")
    consumption_rate: float = Field(
        ..., gt=0.0, description="Per-tick consumption scalar η(C_i)."
    )
    starvation_ticks: int = Field(
        default=0, description="Consecutive ticks without adequate feeding."
    )
    repelled: bool = Field(default=False, description="Currently repelled by toxin.")
    repelled_ticks_remaining: int = Field(
        default=0, description="Ticks remaining in repelled random-walk."
    )
    target_plant_id: int = Field(default=-1, description="ECS id of targeted plant entity.")


class SubstanceComponentSchema(BaseModel):
    """Pydantic schema for a Substance (signal or toxin) ECS component."""

    entity_id: int = Field(..., description="Unique ECS entity identifier.")
    substance_id: SubstanceId = Field(..., description="Substance layer index.")
    owner_plant_id: int = Field(..., description="ECS entity id of the producing plant.")
    is_toxin: bool = Field(default=False, description="True for toxins, False for signals.")
    synthesis_remaining: int = Field(
        default=0, ge=0, description="Ticks before substance becomes active."
    )
    active: bool = Field(default=False, description="Whether the substance is currently active.")
    aftereffect_ticks: int = Field(
        default=0, ge=0, description="Remaining aftereffect duration T_k."
    )
    lethal: bool = Field(default=False, description="Lethal toxin flag.")
    lethality_rate: float = Field(
        default=0.0, ge=0.0, description="Individuals eliminated per tick β(s_x, C_i)."
    )
    repellent: bool = Field(default=False, description="Repellent toxin flag.")
    repellent_walk_ticks: int = Field(
        default=0, ge=0, description="Random-walk duration k on repel trigger."
    )
    precursor_signal_id: int = Field(
        default=-1, description="Signal substance_id required before toxin activation (-1 = none)."
    )


# ---------------------------------------------------------------------------
# Trigger / interaction matrix entry
# ---------------------------------------------------------------------------


class TriggerConditionSchema(BaseModel):
    """Trigger condition for substance synthesis (Interaction Matrix entry)."""

    predator_species_id: PredatorId
    min_predator_population: int = Field(
        ..., gt=0, description="Minimum swarm size n_i,min to trigger synthesis."
    )
    substance_id: SubstanceId = Field(..., description="Substance to synthesise.")
    synthesis_duration: int = Field(..., gt=0, description="Ticks to synthesise T(s_x).")


# ---------------------------------------------------------------------------
# Species parameter schemas
# ---------------------------------------------------------------------------


class FloraSpeciesParams(BaseModel):
    """Per-species parameters for flora."""

    species_id: SpeciesId
    name: str
    base_energy: float = Field(..., gt=0.0)
    max_energy: float = Field(..., gt=0.0)
    growth_rate: float = Field(..., ge=0.0)
    survival_threshold: float = Field(..., ge=0.0)
    reproduction_interval: int = Field(..., gt=0)
    seed_min_dist: float = Field(default=1.0, ge=0.0)
    seed_max_dist: float = Field(default=3.0, gt=0.0)
    seed_energy_cost: float = Field(default=5.0, ge=0.0)
    camouflage: bool = False
    camouflage_factor: float = Field(default=1.0, ge=0.0, le=1.0)
    # Trigger matrix: list of trigger conditions associated with this species
    triggers: list[TriggerConditionSchema] = Field(default_factory=list)


class PredatorSpeciesParams(BaseModel):
    """Per-species parameters for predators (herbivore swarms)."""

    species_id: PredatorId
    name: str
    energy_min: float = Field(..., gt=0.0)
    velocity: int = Field(..., gt=0)
    consumption_rate: float = Field(..., gt=0.0)
    reproduction_energy_divisor: float = Field(
        default=1.0,
        gt=0.0,
        description="Denominator for φ(e_h,t) = floor(R(C_i,t) / E_min(e_h)).",
    )


# ---------------------------------------------------------------------------
# Diet Compatibility Matrix
# ---------------------------------------------------------------------------


class DietCompatibilityMatrix(BaseModel):
    """Boolean matrix [predator_species, flora_species] indicating edibility."""

    rows: list[list[bool]] = Field(
        ...,
        description=(
            "Outer index = predator species id, inner index = flora species id. "
            "True means the predator can consume that flora species."
        ),
    )

    @model_validator(mode="after")
    def _validate_shape(self) -> DietCompatibilityMatrix:
        n_pred = len(self.rows)
        if n_pred > MAX_PREDATOR_SPECIES:
            raise ValueError(
                f"DietCompatibilityMatrix has {n_pred} rows, max is {MAX_PREDATOR_SPECIES}."
            )
        for row in self.rows:
            if len(row) > MAX_FLORA_SPECIES:
                raise ValueError(
                    f"DietCompatibilityMatrix row length {len(row)} exceeds {MAX_FLORA_SPECIES}."
                )
        return self


# ---------------------------------------------------------------------------
# Initial placement
# ---------------------------------------------------------------------------


class InitialPlantPlacement(BaseModel):
    """Single plant to place at simulation start."""

    species_id: SpeciesId
    x: int = Field(..., ge=0)
    y: int = Field(..., ge=0)
    energy: float = Field(..., gt=0.0)


class InitialSwarmPlacement(BaseModel):
    """Single swarm to place at simulation start."""

    species_id: PredatorId
    x: int = Field(..., ge=0)
    y: int = Field(..., ge=0)
    population: int = Field(..., gt=0)
    energy: float = Field(..., gt=0.0)


# ---------------------------------------------------------------------------
# Global Configuration Payload
# ---------------------------------------------------------------------------


class SimulationConfig(BaseModel):
    """Complete simulation configuration payload (REST /api/scenario/load body)."""

    grid_width: int = Field(default=40, ge=1, le=80)
    grid_height: int = Field(default=40, ge=1, le=80)
    max_ticks: int = Field(default=1000, gt=0)
    tick_rate_hz: float = Field(default=10.0, gt=0.0, description="WebSocket stream tick rate.")

    num_signals: int = Field(default=4, ge=1, le=MAX_SUBSTANCE_TYPES)
    num_toxins: int = Field(default=4, ge=1, le=MAX_SUBSTANCE_TYPES)

    wind_x: float = Field(default=0.0, description="Initial wind vector x-component.")
    wind_y: float = Field(default=0.0, description="Initial wind vector y-component.")

    flora_species: list[FloraSpeciesParams] = Field(
        ..., min_length=1, max_length=MAX_FLORA_SPECIES
    )
    predator_species: list[PredatorSpeciesParams] = Field(
        ..., min_length=1, max_length=MAX_PREDATOR_SPECIES
    )
    diet_matrix: DietCompatibilityMatrix

    initial_plants: list[InitialPlantPlacement] = Field(default_factory=list)
    initial_swarms: list[InitialSwarmPlacement] = Field(default_factory=list)

    # Symbiotic network settings
    mycorrhizal_inter_species: bool = Field(
        default=False, description="Allow inter-species root connections."
    )
    mycorrhizal_connection_cost: float = Field(
        default=1.0, ge=0.0, description="Energy cost to establish a root link."
    )
    mycorrhizal_signal_velocity: int = Field(
        default=1, gt=0, description="Signal transfer speed t_g (ticks per hop)."
    )

    # Termination conditions
    z2_flora_species_extinction: int = Field(
        default=-1, description="Halt when this flora species id goes extinct (-1 = disabled)."
    )
    z4_predator_species_extinction: int = Field(
        default=-1,
        description="Halt when this predator species id goes extinct (-1 = disabled).",
    )
    z6_max_total_flora_energy: float = Field(
        default=-1.0, description="Halt when total flora energy exceeds this value (-1 = disabled)."
    )
    z7_max_total_predator_population: int = Field(
        default=-1,
        description="Halt when total predator population exceeds this value (-1 = disabled).",
    )

    @model_validator(mode="after")
    def _validate_species_ids(self) -> SimulationConfig:
        flora_ids = {s.species_id for s in self.flora_species}
        predator_ids = {s.species_id for s in self.predator_species}
        for placement in self.initial_plants:
            if placement.species_id not in flora_ids:
                raise ValueError(
                    f"InitialPlantPlacement references unknown "
                    f"flora species {placement.species_id}."
                )
        for placement in self.initial_swarms:
            if placement.species_id not in predator_ids:
                raise ValueError(
                    f"InitialSwarmPlacement references unknown predator species "
                    f"{placement.species_id}."
                )
        return self


# ---------------------------------------------------------------------------
# REST API response models
# ---------------------------------------------------------------------------


class SimulationStatusResponse(BaseModel):
    """Response model for simulation state queries."""

    tick: int
    running: bool
    paused: bool
    terminated: bool
    termination_reason: str | None = None


class WindUpdatePayload(BaseModel):
    """REST payload for dynamically updating wind vectors."""

    wind_x: float
    wind_y: float
