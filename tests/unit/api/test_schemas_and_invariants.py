# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Test API schemas and invariants.

Validates the Pydantic REST schema boundaries, specifically the "Rule of 16" constants,
which guarantee safe static matrix allocations in the Numba JIT engines.
"""

import pytest
from pydantic import ValidationError

from phids.api.schemas.simulation import SimulationConfig
from phids.api.schemas.species import DietCompatibilityMatrix, FloraSpeciesParams, HerbivoreSpeciesParams
from phids.shared.constants import MAX_FLORA_SPECIES, MAX_HERBIVORE_SPECIES, MAX_SUBSTANCE_TYPES


def _create_dummy_herbivore(species_id: int) -> HerbivoreSpeciesParams:
    return HerbivoreSpeciesParams(
        species_id=species_id,
        name=f"Herbivore {species_id}",
        energy_min=5.0,
        velocity=1,
        consumption_rate=2.0,
    )


def _create_dummy_flora(species_id: int, num_triggers: int = 0) -> FloraSpeciesParams:
    triggers = [
        {
            "herbivore_species_id": 0,
            "min_herbivore_population": 5,
            "action": {
                "type": "synthesize_substance",
                "substance_id": i,
                "synthesis_duration": 10,
            },
        }
        for i in range(num_triggers)
    ]
    return FloraSpeciesParams(
        species_id=species_id,
        name=f"Flora {species_id}",
        base_energy=10.0,
        max_energy=50.0,
        growth_rate=1.0,
        survival_threshold=5.0,
        reproduction_interval=100,
        triggers=triggers,
    )


def test_trigger_schema_enforces_rule_of_16_bounds() -> None:
    """Assert that a single flora species rejects > MAX_SUBSTANCE_TYPES triggers."""
    with pytest.raises(ValidationError, match="List should have at most 16 items"):
        _create_dummy_flora(species_id=0, num_triggers=MAX_SUBSTANCE_TYPES + 1)


def test_flora_species_enforces_rule_of_16_bounds() -> None:
    """Assert that the SimulationConfig rejects > MAX_FLORA_SPECIES."""
    # We must construct MAX_FLORA_SPECIES + 1 elements, but species_id max limit is 15.
    # We'll just set them all to 0. Pydantic list limit is checked regardless of duplicate ids.
    flora = [_create_dummy_flora(0) for _ in range(MAX_FLORA_SPECIES + 1)]
    herbivores = [_create_dummy_herbivore(0)]
    diet_rows = [[True] * MAX_FLORA_SPECIES]

    with pytest.raises(ValidationError, match="List should have at most 16 items"):
        SimulationConfig(
            grid_width=64,
            grid_height=64,
            max_ticks=1000,
            flora_species=flora,
            herbivore_species=herbivores,
            diet_matrix=DietCompatibilityMatrix(rows=diet_rows),
        )


def test_trigger_schema_supports_full_substance_matrix() -> None:
    """Prove that a fully saturated 16x16 matrix (16 species * 16 triggers each) is accepted."""
    flora = [_create_dummy_flora(i, num_triggers=MAX_SUBSTANCE_TYPES) for i in range(MAX_FLORA_SPECIES)]
    herbivores = [_create_dummy_herbivore(i) for i in range(MAX_HERBIVORE_SPECIES)]
    diet_rows = [[True] * MAX_FLORA_SPECIES for _ in range(MAX_HERBIVORE_SPECIES)]

    config = SimulationConfig(
        grid_width=64,
        grid_height=64,
        max_ticks=1000,
        num_signals=MAX_SUBSTANCE_TYPES,
        num_toxins=MAX_SUBSTANCE_TYPES,
        flora_species=flora,
        herbivore_species=herbivores,
        diet_matrix=DietCompatibilityMatrix(rows=diet_rows),
    )

    # If we made it here without ValidationError, the schema accepted the payload.
    assert len(config.flora_species) == MAX_FLORA_SPECIES
    for f in config.flora_species:
        assert len(f.triggers) == MAX_SUBSTANCE_TYPES
