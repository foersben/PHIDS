# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Shared fixtures and builder helpers for DraftState unit tests.

Provides:
- ``_flora``: Construct a FloraSpeciesParams with minimal required fields.
- ``_herbivore``: Construct a HerbivoreSpeciesParams with minimal required fields.
- ``reset_draft_state``: autouse fixture that resets the DraftState singleton
  between tests to prevent cross-test pollution.
"""

from __future__ import annotations

from phids.api.schemas.species import (
    FloraSpeciesParams,
    HerbivoreResistancesSchema,
    HerbivoreSpeciesParams,
)
from phids.api.schemas.triggers import PassiveDefensesSchema


def _flora(species_id: int, name: str | None = None) -> FloraSpeciesParams:
    """Construct a minimal FloraSpeciesParams for test scenarios.

    Args:
        species_id: Numeric species identifier.
        name: Optional display name; defaults to ``"flora-{species_id}"``.

    Returns:
        A fully populated FloraSpeciesParams with sensible test defaults.
    """
    return FloraSpeciesParams(
        species_id=species_id,
        name=name or f"flora-{species_id}",
        base_energy=10.0,
        max_energy=25.0,
        growth_rate=3.0,
        survival_threshold=1.0,
        reproduction_interval=4,
        seed_min_dist=1.0,
        seed_max_dist=2.0,
        seed_energy_cost=1.0,
        triggers=[],
        passive_defenses=PassiveDefensesSchema(mechanical_damage_per_bite=0.0, digestibility_modifier=1.0),
    )


def _herbivore(species_id: int, name: str | None = None) -> HerbivoreSpeciesParams:
    """Construct a minimal HerbivoreSpeciesParams for test scenarios.

    Args:
        species_id: Numeric species identifier.
        name: Optional display name; defaults to ``"herbivore-{species_id}"``.

    Returns:
        A fully populated HerbivoreSpeciesParams with sensible test defaults.
    """
    return HerbivoreSpeciesParams(
        species_id=species_id,
        name=name or f"herbivore-{species_id}",
        energy_min=1.0,
        velocity=1,
        consumption_rate=1.5,
        reproduction_energy_divisor=1.0,
        resistances=HerbivoreResistancesSchema(),
    )
