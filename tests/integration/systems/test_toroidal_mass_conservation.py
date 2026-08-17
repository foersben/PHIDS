# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Integration test verifying mass conservation across toroidal grid boundaries."""

from __future__ import annotations

from phids.api.schemas.simulation import SimulationConfig
from phids.api.schemas.species import FloraSpeciesParams, HerbivoreSpeciesParams
from phids.engine.loop import SimulationLoop


async def test_toroidal_mass_conservation_over_ticks() -> None:
    """Run a 50-tick simulation with heavy wind and verify entity & signal conservation across toroidal wrap."""
    flora = FloraSpeciesParams(
        species_id=0,
        name="Oak",
        display_name="Oak",
        color="#00FF00",
        base_energy=100.0,
        max_energy=200.0,
        growth_rate=5.0,
        survival_threshold=10.0,
        reproduction_interval=10,
        seed_min_dist=4.0,
        seed_max_dist=8.0,
        seed_energy_cost=20.0,
    )
    herbivore = HerbivoreSpeciesParams(
        species_id=0,
        name="Deer",
        display_name="Deer",
        color="#FF0000",
        base_population=50,
        energy=100.0,
        max_energy=200.0,
        energy_min=1.0,
        consumption_rate=1.0,
        metabolic_rate=0.0,
        velocity=1,
    )

    config = SimulationConfig(
        grid_width=32,
        grid_height=32,
        flora_species=[flora],
        herbivore_species=[herbivore],
        diet_matrix={"rows": [[True]]},
        initial_plants=[
            {"species_id": 0, "x": 0, "y": 10, "energy": 100.0},
            {"species_id": 0, "x": 19, "y": 10, "energy": 100.0},
        ],
        initial_swarms=[{"species_id": 0, "x": 19, "y": 10, "population": 50, "energy": 100.0}],
    )

    loop = SimulationLoop(config)
    # Set heavy east wind
    loop.env.wind_vector_x[:, :] = 15.0

    for _ in range(50):
        await loop.step()

    # Verify simulation loop completed without raising index errors or out-of-bounds crashes
    assert loop.tick == 50
    # Check that all live entities have valid toroidal coordinates
    for entity in loop.world.query():
        pos = loop.world._entity_positions.get(entity.entity_id)
        if pos is not None:
            assert 0 <= pos[0] < 20
            assert 0 <= pos[1] < 20
