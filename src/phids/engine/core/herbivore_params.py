# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Pure functional utilities for herbivore species parameter lookups.

This module provides safe dictionary lookups for :class:`~phids.api.schemas.species.HerbivoreSpeciesParams`
with sensible fallback defaults to ensure deterministic fallback behaviour when parameters are missing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from phids.api.schemas.species import HerbivoreSpeciesParams


def get_herbivore_energy_min(params_dict: dict[int, HerbivoreSpeciesParams], species_id: int) -> float:
    """Return the configured minimum energy for a herbivore species.

    Args:
        params_dict: Dictionary mapping species IDs to their parameters.
        species_id: Herbivore species identifier to look up.

    Returns:
        Configured minimum energy if found, otherwise a sensible default of 1.0.
    """
    params = params_dict.get(species_id)
    if params is not None:
        return params.energy_min
    return 1.0


def get_herbivore_velocity(params_dict: dict[int, HerbivoreSpeciesParams], species_id: int) -> int:
    """Return the configured movement period (velocity) for a herbivore.

    Args:
        params_dict: Dictionary mapping species IDs to their parameters.
        species_id: Herbivore species identifier to look up.

    Returns:
        int: Movement period in ticks; defaults to 1 when not found.
    """
    params = params_dict.get(species_id)
    if params is not None:
        return params.velocity
    return 1


def get_herbivore_consumption_rate(params_dict: dict[int, HerbivoreSpeciesParams], species_id: int) -> float:
    """Return the per-tick consumption rate for a herbivore species.

    Args:
        params_dict: Dictionary mapping species IDs to their parameters.
        species_id: Herbivore species identifier to look up.

    Returns:
        float: Consumption rate if present, otherwise 1.0 by default.
    """
    params = params_dict.get(species_id)
    if params is not None:
        return params.consumption_rate
    return 1.0


def get_herbivore_reproduction_divisor(params_dict: dict[int, HerbivoreSpeciesParams], species_id: int) -> float:
    """Return the configured reproduction divisor for a herbivore species.

    Args:
        params_dict: Dictionary mapping species IDs to their parameters.
        species_id: Herbivore species identifier to look up.

    Returns:
        float: Reproduction divisor if present, otherwise 1.0.
    """
    params = params_dict.get(species_id)
    if params is not None:
        return params.reproduction_energy_divisor
    return 1.0


def get_herbivore_energy_upkeep(params_dict: dict[int, HerbivoreSpeciesParams], species_id: int) -> float:
    """Return the configured per-individual metabolic upkeep scalar for a herbivore species.

    Args:
        params_dict: Dictionary mapping species IDs to their parameters.
        species_id: Herbivore species identifier to look up.

    Returns:
        Configured upkeep scalar if found; otherwise 0.05 as a sensible default.
    """
    params = params_dict.get(species_id)
    if params is not None:
        return params.energy_upkeep_per_individual
    return 0.05


def get_herbivore_split_threshold(params_dict: dict[int, HerbivoreSpeciesParams], species_id: int) -> int:
    """Return the configured explicit mitosis population threshold for a herbivore species.

    Args:
        params_dict: Dictionary mapping species IDs to their parameters.
        species_id: Herbivore species identifier to look up.

    Returns:
        Configured split threshold if found; otherwise 10.
    """
    params = params_dict.get(species_id)
    if params is not None:
        return params.split_population_threshold
    return 10
