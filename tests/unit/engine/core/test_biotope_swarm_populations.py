# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests verifying herbivore census dimensions exceed signal count bounds."""

from __future__ import annotations

import asyncio

import numpy as np

from phids.api.schemas.placement import InitialPlantPlacement, InitialSwarmPlacement
from phids.api.schemas.simulation import SimulationConfig
from phids.api.schemas.species import (
    DietCompatibilityMatrix,
    FloraSpeciesParams,
    HerbivoreSpeciesParams,
)
from phids.api.schemas.triggers import (
    HerbivoreAttackInitiator,
    SynthesizeSubstanceAction,
    TriggerConditionSchema,
)
from phids.engine.components.substances import SubstanceComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.loop import SimulationLoop
from phids.shared.constants import MAX_HERBIVORE_SPECIES


def test_biotope_swarm_populations_uses_max_herbivore_species() -> None:
    """Verify GridEnvironment sizes swarm_populations by MAX_HERBIVORE_SPECIES, not num_signals."""
    env = GridEnvironment(width=16, height=16, num_signals=3, num_toxins=4)
    assert env.swarm_populations.shape == (MAX_HERBIVORE_SPECIES, 16, 16)
    assert env.swarm_populations.dtype == np.int32


def _make_five_guild_config(*, swarm_x: int, swarm_y: int) -> SimulationConfig:
    """Build a minimal 5-herbivore / 3-signal SimulationConfig."""
    return SimulationConfig(
        grid_width=16,
        grid_height=16,
        max_ticks=5,
        num_signals=3,
        num_toxins=1,
        wind_x=0.0,
        wind_y=0.0,
        flora_species=[
            FloraSpeciesParams(
                species_id=0,
                name="P0",
                base_energy=10.0,
                max_energy=100.0,
                growth_rate=0.0,
                survival_threshold=1.0,
                reproduction_interval=100,
                seed_min_energy=50.0,
                seed_energy_cost=5.0,
                triggers=[
                    TriggerConditionSchema(
                        initiator=HerbivoreAttackInitiator(herbivore_species_id=4, min_herbivore_population=2),
                        action=SynthesizeSubstanceAction(substance_id=0, synthesis_duration=2),
                    )
                ],
            ),
        ],
        herbivore_species=[
            HerbivoreSpeciesParams(
                species_id=sid,
                name=f"H{sid}",
                energy_min=1.0,
                velocity=1,
                consumption_rate=0.1,
                reproduction_energy_divisor=10.0,
                split_population_threshold=100,
            )
            for sid in range(5)
        ],
        diet_matrix=DietCompatibilityMatrix(rows=[[True], [True], [True], [True], [True]]),
        initial_plants=[InitialPlantPlacement(species_id=0, x=2, y=2, energy=20.0)],
        initial_swarms=[InitialSwarmPlacement(species_id=4, x=swarm_x, y=swarm_y, population=5, energy=20.0)],
    )


def test_simulation_supports_more_herbivore_guilds_than_signal_channels() -> None:
    """Verify 5 herbivore guilds with num_signals=3 never clip or spuriously fire triggers."""
    unoccupied_loop = SimulationLoop(_make_five_guild_config(swarm_x=10, swarm_y=10), disable_replay=True)
    asyncio.run(unoccupied_loop.step())
    assert unoccupied_loop.env.swarm_populations.shape == (MAX_HERBIVORE_SPECIES, 16, 16)
    assert int(unoccupied_loop.env.swarm_populations[4].sum()) >= 5
    assert sum(1 for _ in unoccupied_loop.world.query(SubstanceComponent)) == 0

    colocated_loop = SimulationLoop(_make_five_guild_config(swarm_x=2, swarm_y=2), disable_replay=True)
    asyncio.run(colocated_loop.step())
    assert int(colocated_loop.env.swarm_populations[4].sum()) >= 5
    assert sum(1 for _ in colocated_loop.world.query(SubstanceComponent)) >= 1
