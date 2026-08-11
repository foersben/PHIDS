# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Shared fixtures for the batch runner integration test sub-package.

Provides ``minimal_scenario`` - a pytest fixture that constructs a minimal
JSON-serialisable SimulationConfig dict for a 4x4 grid with one flora and
one herbivore. This scenario is the standard baseline for all batch runner tests.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def minimal_scenario() -> dict:
    """Construct a minimal JSON-serialisable SimulationConfig for batch runner tests.

    Returns:
        A dict produced by ``SimulationConfig.model_dump()`` with a 4x4 grid,
        one flora species, one herbivore species, one plant placement, and one
        swarm placement, suitable for headless batch execution in CI.
    """
    from phids.api.schemas.placement import (
        InitialPlantPlacement,
        InitialSwarmPlacement,
    )
    from phids.api.schemas.simulation import SimulationConfig
    from phids.api.schemas.species import (
        DietCompatibilityMatrix,
        FloraSpeciesParams,
        HerbivoreResistancesSchema,
        HerbivoreSpeciesParams,
    )
    from phids.api.schemas.triggers import PassiveDefensesSchema

    config = SimulationConfig(
        grid_width=4,
        grid_height=4,
        max_ticks=5,
        num_signals=1,
        num_toxins=1,
        flora_species=[
            FloraSpeciesParams(
                species_id=0,
                name="TestPlant",
                base_energy=10.0,
                max_energy=50.0,
                growth_rate=1.0,
                survival_threshold=1.0,
                reproduction_interval=20,
                passive_defenses=PassiveDefensesSchema(mechanical_damage_per_bite=0.0, digestibility_modifier=1.0),
            )
        ],
        herbivore_species=[
            HerbivoreSpeciesParams(
                species_id=0,
                name="TestBug",
                energy_min=1.0,
                velocity=1,
                consumption_rate=0.5,
                resistances=HerbivoreResistancesSchema(),
            )
        ],
        diet_matrix=DietCompatibilityMatrix(rows=[[True]]),
        initial_plants=[InitialPlantPlacement(species_id=0, x=1, y=1, energy=20.0)],
        initial_swarms=[InitialSwarmPlacement(species_id=0, x=2, y=2, population=3, energy=5.0)],
    )
    return config.model_dump()
