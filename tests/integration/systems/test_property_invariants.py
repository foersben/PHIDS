# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Integration tests for PHIDS property invariants.

Uses Hypothesis to verify that diet matrices reject configurations exceeding maximum species caps,
and asserts thermodynamic invariants during simulated digestion cycles.
"""

import hypothesis.strategies as st
import pytest
from hypothesis import given
from pydantic import ValidationError

from phids.api.schemas import (
    DietCompatibilityMatrix,
    FloraSpeciesParams,
    HerbivoreSpeciesParams,
    PassiveDefensesSchema,
)
from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.engine.systems.interaction import run_interaction
from phids.shared.constants import MAX_FLORA_SPECIES, MAX_HERBIVORE_SPECIES


@given(
    rows=st.lists(
        st.lists(st.booleans(), min_size=MAX_FLORA_SPECIES + 1, max_size=MAX_FLORA_SPECIES + 5),
        min_size=1,
        max_size=MAX_HERBIVORE_SPECIES,
    )
)
def test_diet_matrix_rejects_over_max_flora(rows) -> None:
    """Verify DietCompatibilityMatrix rejects rows exceeding max flora limit."""
    with pytest.raises(ValidationError):
        DietCompatibilityMatrix(rows=rows)


@given(
    rows=st.lists(
        st.lists(st.booleans(), min_size=1, max_size=MAX_FLORA_SPECIES),
        min_size=MAX_HERBIVORE_SPECIES + 1,
        max_size=MAX_HERBIVORE_SPECIES + 5,
    )
)
def test_diet_matrix_rejects_over_max_herbivores(rows) -> None:
    """Verify DietCompatibilityMatrix rejects cols exceeding max herbivores limit."""
    with pytest.raises(ValidationError):
        DietCompatibilityMatrix(rows=rows)


def test_thermodynamic_invariant_digestion() -> None:
    """Verify thermodynamic invariants hold during digestion simulation."""
    world = ECSWorld()
    env = GridEnvironment(width=10, height=10)

    plant_eid = world.create_entity()
    plant = PlantComponent(
        entity_id=plant_eid.entity_id,
        species_id=0,
        x=5,
        y=5,
        energy=100.0,
        max_energy=200.0,
        base_energy=10.0,
        growth_rate=0.0,
        survival_threshold=0.0,
        reproduction_interval=10,
        seed_min_dist=1,
        seed_max_dist=2,
        seed_energy_cost=5,
    )
    world.add_component(plant_eid.entity_id, plant)
    world.register_position(plant_eid.entity_id, 5, 5)

    swarm_eid = world.create_entity()
    swarm = SwarmComponent(
        entity_id=swarm_eid.entity_id,
        species_id=0,
        x=5,
        y=5,
        population=10,
        initial_population=10,
        energy=50.0,
        energy_min=1.0,
        velocity=1,
        consumption_rate=2.0,
        split_population_threshold=1000,
    )
    # prevent random walk dispersal
    swarm.repelled = False
    world.add_component(swarm_eid.entity_id, swarm)
    world.register_position(swarm_eid.entity_id, 5, 5)

    flora_params = [
        FloraSpeciesParams(
            species_id=0,
            name="F0",
            base_energy=10,
            max_energy=200,
            growth_rate=0,
            survival_threshold=0,
            reproduction_interval=10,
            passive_defenses=PassiveDefensesSchema(digestibility_modifier=0.5, mechanical_damage_per_bite=0.0),
        )
    ]
    herb_params = [
        HerbivoreSpeciesParams(
            species_id=0,
            name="H0",
            energy_min=1,
            velocity=1,
            consumption_rate=2.0,
            energy_upkeep_per_individual=0.0,
            resistances=dict(digestive_efficiency=1.0, morphological_adaptation=0.0),
        )
    ]

    diet = [[True]]

    run_interaction(world, env, diet, flora_params, herb_params, tick=0)
    assert plant.energy == 80.0
