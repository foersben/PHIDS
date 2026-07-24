# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Pydantic schemata mirroring ECS component state for REST and WebSocket serialisation.

These models support inspection endpoints and state queries. They are never used
to parameterise engine construction - see ``phids.api.schemas.simulation`` for that.
"""

from __future__ import annotations

from pydantic import Field

from phids.api.schemas.base import HerbivoreId, SpeciesId, StrictBaseModel, SubstanceId


class PlantComponentSchema(StrictBaseModel):
    """Pydantic schema for the Plant ECS component."""

    entity_id: int = Field(..., description="Unique ECS entity identifier.")
    species_id: SpeciesId = Field(..., description="Flora species index [0, MAX_FLORA_SPECIES).")
    x: int = Field(..., ge=0, description="Grid x-coordinate.")
    y: int = Field(..., ge=0, description="Grid y-coordinate.")
    energy: float = Field(..., ge=0.0, description="[Absolute] Current energy reserve (E_i,j).")
    max_energy: float = Field(..., gt=0.0, description="[Absolute] Species-specific energy capacity (E_max).")
    base_energy: float = Field(..., gt=0.0, description="[Absolute] Initial energy E_i,j(0).")
    growth_rate: float = Field(
        ..., ge=0.0, description="[% Rate] Per-tick growth rate r_i,j. Expressed as a fraction (e.g. 0.05 = 5%)."
    )
    survival_threshold: float = Field(..., ge=0.0, description="[Absolute] Minimum energy B_i,j before death.")
    reproduction_interval: int = Field(..., gt=0, description="[Ticks] Ticks between reproduction attempts (T_i).")
    seed_min_dist: float = Field(..., ge=0.0, description="[Absolute] Minimum seed dispersal distance d_min.")
    seed_max_dist: float = Field(..., gt=0.0, description="[Absolute] Maximum seed dispersal distance d_max.")
    seed_energy_cost: float = Field(..., ge=0.0, description="[Absolute] Energy cost per reproduction event.")
    camouflage: bool = Field(default=False, description="[Flag] Constitutive gradient attenuation flag.")
    camouflage_factor: float = Field(default=1.0, ge=0.0, le=1.0, description="[%] Gradient multiplier (0.0 to 1.0).")
    last_reproduction_tick: int = Field(default=0, description="[Ticks] Last tick of reproduction.")
    apparent_nutrition_factor: float = Field(
        default=1.0, ge=0.0, le=1.0, description="[%] Current stress-induced nutrient discount (0.0 to 1.0)."
    )
    withdrawal_ticks_remaining: int = Field(
        default=0, ge=0, description="[Ticks] Ticks until apparent_nutrition_factor resets to 1.0."
    )


class SwarmComponentSchema(StrictBaseModel):
    """Pydantic schema for the Herbivore Swarm ECS component."""

    entity_id: int = Field(..., description="Unique ECS entity identifier.")
    species_id: HerbivoreId = Field(..., description="Herbivore species index [0, MAX_HERBIVORE_SPECIES).")
    x: int = Field(..., ge=0, description="Grid x-coordinate.")
    y: int = Field(..., ge=0, description="Grid y-coordinate.")
    population: int = Field(..., gt=0, description="[Absolute] Current swarm head-count n(t).")
    initial_population: int = Field(..., gt=0, description="[Absolute] Initial population n(0) for mitosis.")
    energy: float = Field(..., ge=0.0, description="[Absolute] Current energy reserve.")
    energy_min: float = Field(..., gt=0.0, description="[Absolute] Minimum energy per individual E_min(e_h).")
    velocity: int = Field(..., gt=0, description="[Ticks] Ticks between moves. Higher is slower.")
    consumption_rate: float = Field(..., gt=0.0, description="[Absolute] Per-tick consumption scalar η(C_i).")
    energy_upkeep_per_individual: float = Field(
        default=0.05,
        ge=0.0,
        description="[Absolute] Per-individual metabolic upkeep scalar applied each tick.",
    )
    split_population_threshold: int = Field(
        default=10,
        gt=0,
        description="[Absolute] Explicit mitosis population threshold.",
    )
    repelled: bool = Field(default=False, description="Currently repelled by toxin.")
    repelled_ticks_remaining: int = Field(default=0, description="Ticks remaining in repelled random-walk.")


class SubstanceComponentSchema(StrictBaseModel):
    """Pydantic schema for a Substance (signal or toxin) ECS component."""

    entity_id: int = Field(..., description="Unique ECS entity identifier.")
    substance_id: SubstanceId = Field(..., description="Substance layer index.")
    owner_plant_id: int = Field(..., description="[ID] ECS entity id of the producing plant.")
    is_toxin: bool = Field(default=False, description="[Flag] True for toxins, False for signals.")
    synthesis_remaining: int = Field(default=0, ge=0, description="[Ticks] Ticks before substance becomes active.")
    active: bool = Field(default=False, description="[Flag] Whether the substance is currently active.")
    aftereffect_ticks: int = Field(default=0, ge=0, description="[Ticks] Remaining aftereffect duration T_k.")
    lethal: bool = Field(default=False, description="[Flag] Lethal toxin flag.")
    lethality_rate: float = Field(default=0.0, ge=0.0, description="[Absolute] Individuals eliminated per tick.")
    repellent: bool = Field(default=False, description="[Flag] Repellent toxin flag.")
    repellent_walk_ticks: int = Field(default=0, ge=0, description="[Ticks] Random-walk duration k on repel trigger.")
    energy_cost_per_tick: float = Field(
        default=0.0, ge=0.0, description="[Absolute] Energy cost drained from the owner plant per active tick."
    )
    irreversible: bool = Field(
        default=False,
        description="Whether activation is irreversible once the substance becomes active.",
    )
