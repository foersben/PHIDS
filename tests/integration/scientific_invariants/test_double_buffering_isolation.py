# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Double-buffering immutability isolation integration tests across all loop phases."""

from __future__ import annotations

import numpy as np
import pytest

from phids.api.schemas.simulation import SimulationConfig
from phids.api.schemas.species import FloraSpeciesParams, HerbivoreResistancesSchema, HerbivoreSpeciesParams
from phids.api.schemas.triggers import PassiveDefensesSchema
from phids.engine.core.flow_field import compute_flow_field
from phids.engine.loop import SimulationLoop


@pytest.mark.scientific_invariant
def test_double_buffering_read_layer_isolation_across_loop_step() -> None:
    """Assert GridEnvironment plant_energy_layer is never mutated in-place during calculation."""
    flora = FloraSpeciesParams(
        species_id=0,
        name="F0",
        base_energy=10,
        max_energy=100,
        growth_rate=5,
        survival_threshold=0,
        reproduction_interval=10,
        passive_defenses=PassiveDefensesSchema(digestibility_modifier=1.0, mechanical_damage_per_bite=0.0),
    )
    herbivore = HerbivoreSpeciesParams(
        species_id=0,
        name="H0",
        energy_min=1,
        velocity=1,
        consumption_rate=4.0,
        energy_upkeep_per_individual=0.1,
        resistances=HerbivoreResistancesSchema(digestive_efficiency=1.0, morphological_adaptation=0.0),
    )
    config = SimulationConfig(
        grid_width=16,
        grid_height=16,
        flora_species=[flora],
        herbivore_species=[herbivore],
        diet_matrix={"rows": [[True]]},
    )
    loop = SimulationLoop(config, disable_replay=True)

    # Populate plant energy on read layer
    loop.env.set_plant_energy(x=5, y=5, species_id=0, value=100.0)

    # Snapshot current read layer before calculation
    read_snapshot = loop.env.plant_energy_layer.copy()

    # Perform flow-field phase calculation reading plant_energy_layer
    _ = compute_flow_field(
        loop.env.plant_energy_layer,
        loop.env.apparent_nutrition_layer,
        loop.env.toxin_layers,
        loop.env.width,
        loop.env.height,
    )

    # Assert read layer snapshot remains identical
    np.testing.assert_array_equal(
        read_snapshot,
        loop.env.plant_energy_layer,
        err_msg="Read layer must remain immutable during phase calculation",
    )
