# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Per-species parameter schemas for flora and herbivore species, plus the diet matrix.

``FloraSpeciesParams`` and ``HerbivoreSpeciesParams`` parameterise ``SimulationLoop``
construction. ``DietCompatibilityMatrix`` enforces Rule-of-16 shape bounds on both
dimensions of the herbivore-flora edibility matrix.
"""

from __future__ import annotations

from pydantic import AliasChoices, Field, model_validator

from phids.api.schemas.base import HerbivoreId, SpeciesId, StrictBaseModel
from phids.api.schemas.triggers import PassiveDefensesSchema, TriggerConditionSchema
from phids.shared.constants import (
    MAX_FLORA_SPECIES,
    MAX_HERBIVORE_SPECIES,
    MAX_SUBSTANCE_TYPES,
    SEED_DROP_HEIGHT_DEFAULT,
    SEED_TERMINAL_VELOCITY_DEFAULT,
)


class FloraSpeciesParams(StrictBaseModel):
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
    seed_drop_height: float = Field(
        default=SEED_DROP_HEIGHT_DEFAULT,
        gt=0.0,
        description=("Approximate seed release height used for wind-flight-time estimation in anemochorous dispersal."),
    )
    seed_terminal_velocity: float = Field(
        default=SEED_TERMINAL_VELOCITY_DEFAULT,
        gt=0.0,
        description=("Approximate seed terminal fall velocity used for wind-driven downwind shift estimation."),
    )
    camouflage: bool = False
    camouflage_factor: float = Field(default=1.0, ge=0.0, le=1.0)
    passive_defenses: PassiveDefensesSchema = Field(default_factory=PassiveDefensesSchema)
    triggers: list[TriggerConditionSchema] = Field(default_factory=list, max_length=MAX_SUBSTANCE_TYPES)


class HerbivoreResistancesSchema(StrictBaseModel):
    """Herbivore resistances to passive plant defenses."""

    morphological_adaptation: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="[%] Resistance to physical plant defenses like thorns or spines (0.0 to 1.0).",
    )
    chemical_neutralization: float = Field(
        default=0.0, ge=0.0, le=1.0, description="[%] Metabolic ability to neutralize ingested toxins (0.0 to 1.0)."
    )
    digestive_efficiency: float = Field(
        default=1.0,
        ge=0.0,
        description="[%] Ability to extract calories from tough plant matter (0.0+ multiplier).",
    )


class HerbivoreSpeciesParams(StrictBaseModel):
    """Per-species parameters for herbivore swarms."""

    species_id: HerbivoreId
    name: str
    energy_min: float = Field(..., gt=0.0)
    velocity: int = Field(..., gt=0)
    consumption_rate: float = Field(..., gt=0.0)
    reproduction_energy_divisor: float = Field(
        default=1.0,
        gt=0.0,
        validation_alias=AliasChoices("reproduction_energy_divisor", "reproduction_divisor"),
        description="Denominator for φ(e_h,t) = floor(R(C_i,t) / E_min(e_h)).",
    )
    energy_upkeep_per_individual: float = Field(
        default=0.05,
        ge=0.0,
        description="Per-individual metabolic upkeep scalar applied every interaction tick.",
    )
    resistances: HerbivoreResistancesSchema = Field(default_factory=HerbivoreResistancesSchema)
    split_population_threshold: int = Field(
        default=10,
        gt=0,
        description="Explicit population threshold for mitosis.",
    )


class DietCompatibilityMatrix(StrictBaseModel):
    """Boolean matrix [herbivore_species, flora_species] indicating edibility."""

    rows: list[list[bool]] = Field(
        ...,
        description=(
            "Outer index = herbivore species id, inner index = flora species id. "
            "True means the herbivore can consume that flora species."
        ),
    )

    @model_validator(mode="after")
    def _validate_shape(self) -> DietCompatibilityMatrix:
        n_herbivore = len(self.rows)
        if n_herbivore > MAX_HERBIVORE_SPECIES:
            raise ValueError(f"DietCompatibilityMatrix has {n_herbivore} rows, max is {MAX_HERBIVORE_SPECIES}.")
        for row in self.rows:
            if len(row) > MAX_FLORA_SPECIES:
                raise ValueError(f"DietCompatibilityMatrix row length {len(row)} exceeds {MAX_FLORA_SPECIES}.")
        return self
