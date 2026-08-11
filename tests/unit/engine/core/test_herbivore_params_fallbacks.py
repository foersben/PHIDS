# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for herbivore parameter lookup functions and fallback branches."""

from __future__ import annotations

import pytest

from phids.api.schemas.species import HerbivoreSpeciesParams
from phids.engine.core.herbivore_params import (
    get_herbivore_consumption_rate,
    get_herbivore_energy_min,
    get_herbivore_energy_upkeep,
    get_herbivore_evasion_duration,
    get_herbivore_reproduction_divisor,
    get_herbivore_split_threshold,
    get_herbivore_velocity,
)


@pytest.mark.unit
def test_herbivore_params_fallbacks_when_missing() -> None:
    """Verify default fallback values when species_id is missing from params_dict."""
    empty_params: dict[int, HerbivoreSpeciesParams] = {}

    assert get_herbivore_energy_min(empty_params, 99) == 1.0
    assert get_herbivore_velocity(empty_params, 99) == 1
    assert get_herbivore_consumption_rate(empty_params, 99) == 1.0
    assert get_herbivore_evasion_duration(empty_params, 99) == 5
    assert get_herbivore_reproduction_divisor(empty_params, 99) == 1.0
    assert get_herbivore_energy_upkeep(empty_params, 99) == 0.05
    assert get_herbivore_split_threshold(empty_params, 99) == 10


@pytest.mark.unit
def test_herbivore_params_lookups_when_present() -> None:
    """Verify configured values are returned when species_id is present."""
    herb_params = HerbivoreSpeciesParams(
        species_id=1,
        name="Rabbit",
        energy_min=12.5,
        velocity=2,
        consumption_rate=3.5,
        reproduction_energy_divisor=2.0,
        energy_upkeep_per_individual=0.1,
        split_population_threshold=25,
    )
    params_dict = {1: herb_params}

    assert get_herbivore_energy_min(params_dict, 1) == 12.5
    assert get_herbivore_velocity(params_dict, 1) == 2
    assert get_herbivore_consumption_rate(params_dict, 1) == 3.5
    assert get_herbivore_evasion_duration(params_dict, 1) == 5
    assert get_herbivore_reproduction_divisor(params_dict, 1) == 2.0
    assert get_herbivore_energy_upkeep(params_dict, 1) == 0.1
    assert get_herbivore_split_threshold(params_dict, 1) == 25
