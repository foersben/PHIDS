# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Scientific Invariant Tests for First Law of Thermodynamics Energy Conservation in Feeding.

This module validates that energy transfers during herbivory interactions strictly conserve mass and energy
according to the First Law of Thermodynamics: Delta E_herbivore + E_digestive_loss = Delta E_plant_consumed.
"""

from __future__ import annotations

import math

import pytest

from phids.api.schemas.species import FloraSpeciesParams, HerbivoreSpeciesParams
from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.systems.interaction.feeding import _feed_on_single_plant


@pytest.mark.scientific_invariant
def test_feeding_thermodynamic_first_law_conservation() -> None:
    """Verify First Law of Thermodynamics: energy gain + digestive loss == plant energy consumed.

    During a herbivory feeding event, energy extracted from a plant target is converted into
    metabolized energy for the swarm and unassimilated digestive waste. The sum of metabolized
    energy and digestive loss must equal the exact plant energy reduction to floating-point
    precision (rel_tol <= 1e-6).

    Raises:
        AssertionError: If total energy after feeding differs from initial energy.
    """
    env = GridEnvironment(16, 16)
    plant = PlantComponent(
        entity_id=1,
        species_id=0,
        x=5,
        y=5,
        energy=100.0,
        max_energy=200.0,
        base_energy=50.0,
        growth_rate=0.05,
        survival_threshold=5.0,
        reproduction_interval=50,
        seed_min_dist=1.0,
        seed_max_dist=5.0,
        seed_energy_cost=20.0,
    )
    swarm = SwarmComponent(
        entity_id=2,
        species_id=0,
        x=5,
        y=5,
        population=10,
        initial_population=10,
        energy=50.0,
        energy_min=5.0,
        velocity=1,
        consumption_rate=5.0,
    )
    flora_params = [
        FloraSpeciesParams(
            species_id=0,
            name="Grass",
            base_energy=50.0,
            max_energy=200.0,
            growth_rate=0.05,
            survival_threshold=5.0,
            reproduction_interval=50,
        )
    ]
    herb_params = [
        HerbivoreSpeciesParams(
            species_id=0,
            name="Deer",
            energy_min=5.0,
            velocity=1,
            consumption_rate=5.0,
            handling_time=0.1,
        )
    ]

    # Digestibility = 0.8, Digestive Efficiency = 0.9 -> Net Digestibility = 0.72
    flora_params[0].passive_defenses.digestibility_modifier = 0.8
    herb_params[0].resistances.digestive_efficiency = 0.9

    initial_plant_energy = plant.energy
    tile_pops = [0] * (16 * 16)

    metabolized_energy, _ = _feed_on_single_plant(
        swarm=swarm,
        target_plant=plant,
        flora_species_params=flora_params,
        herbivore_species_params=herb_params,
        env=env,
        tile_populations=tile_pops,
        plant_death_causes=None,
    )

    energy_extracted = initial_plant_energy - plant.energy
    digestive_loss = energy_extracted * (1.0 - 0.72)

    assert math.isclose(metabolized_energy + digestive_loss, energy_extracted, rel_tol=1e-6)
