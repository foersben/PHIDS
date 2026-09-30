# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Pure functional utilities for herbivore species parameter lookups.

This module provides safe dictionary lookups for :class:`~phids.api.schemas.species.HerbivoreSpeciesParams`
mapping directly without fallback logic.
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
        Configured minimum energy.
    """
    return params_dict[species_id].energy_min


def get_herbivore_velocity(params_dict: dict[int, HerbivoreSpeciesParams], species_id: int) -> int:
    """Return the configured movement period (velocity) for a herbivore.

    Args:
        params_dict: Dictionary mapping species IDs to their parameters.
        species_id: Herbivore species identifier to look up.

    Returns:
        int: Movement period in ticks.
    """
    return params_dict[species_id].velocity


def get_herbivore_consumption_rate(params_dict: dict[int, HerbivoreSpeciesParams], species_id: int) -> float:
    """Return the per-tick consumption rate for a herbivore species.

    Args:
        params_dict: Dictionary mapping species IDs to their parameters.
        species_id: Herbivore species identifier to look up.

    Returns:
        float: Consumption rate.
    """
    return params_dict[species_id].consumption_rate


def get_herbivore_evasion_duration(params_dict: dict[int, HerbivoreSpeciesParams], species_id: int) -> int:
    """Return the configured evasion duration ticks for a herbivore.

    Args:
        params_dict: Dictionary mapping species IDs to their parameters.
        species_id: Herbivore species identifier to look up.

    Returns:
        Configured evasion duration.
    """
    return params_dict[species_id].evasion_duration_ticks


def get_herbivore_reproduction_divisor(params_dict: dict[int, HerbivoreSpeciesParams], species_id: int) -> float:
    """Return the configured reproduction divisor for a herbivore species.

    Args:
        params_dict: Dictionary mapping species IDs to their parameters.
        species_id: Herbivore species identifier to look up.

    Returns:
        float: Reproduction divisor.
    """
    return params_dict[species_id].reproduction_energy_divisor


def get_herbivore_energy_upkeep(params_dict: dict[int, HerbivoreSpeciesParams], species_id: int) -> float:
    """Return the configured per-individual metabolic upkeep scalar for a herbivore species.

    Args:
        params_dict: Dictionary mapping species IDs to their parameters.
        species_id: Herbivore species identifier to look up.

    Returns:
        Configured upkeep scalar.
    """
    return params_dict[species_id].energy_upkeep_per_individual


def get_herbivore_softmax_temperature(params_dict: dict[int, HerbivoreSpeciesParams], species_id: int) -> float:
    """Return the configured softmax temperature for stochastic foraging.

    Args:
        params_dict: Dictionary mapping species IDs to their parameters.
        species_id: Herbivore species identifier to look up.

    Returns:
        Configured softmax temperature.
    """
    return params_dict[species_id].softmax_temperature


def get_herbivore_split_threshold(params_dict: dict[int, HerbivoreSpeciesParams], species_id: int) -> int:
    """Return the configured explicit mitosis population threshold for a herbivore species.

    Args:
        params_dict: Dictionary mapping species IDs to their parameters.
        species_id: Herbivore species identifier to look up.

    Returns:
        Configured split threshold.
    """
    return params_dict[species_id].split_population_threshold
