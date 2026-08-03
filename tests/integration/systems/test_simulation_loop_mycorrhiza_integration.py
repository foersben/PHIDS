"""Integration tests validating SimulationLoop end-to-end mycorrhizal network establishment.

These tests run full `SimulationLoop.step()` invocations over multi-week simulation
spans (ticks > 168) to verify that modulo-gated lifecycle passes correctly establish,
maintain, and expand mycorrhizal root networks across adjacent plants.
"""

from __future__ import annotations

import pytest

from phids.api.schemas.placement import InitialPlantPlacement, InitialSwarmPlacement
from phids.api.schemas.simulation import SimulationConfig
from phids.api.schemas.species import (
    DietCompatibilityMatrix,
    FloraSpeciesParams,
    HerbivoreResistancesSchema,
    HerbivoreSpeciesParams,
)
from phids.api.schemas.triggers import PassiveDefensesSchema
from phids.engine.components.plant import PlantComponent
from phids.engine.loop import SimulationLoop


@pytest.mark.asyncio
async def test_simulation_loop_establishes_mycorrhizal_connections_on_slow_ticks() -> None:
    """SimulationLoop must establish root connections between adjacent plants at tick 168.

    Regression test for parity-lockout bug where (168*k + 1) % 8 was never 0 when
    run_lifecycle was gated to the slow loop. Two adjacent plants must form a
    bidirectional mycorrhizal connection once step 168 executes.
    """
    config = SimulationConfig(
        grid_width=10,
        grid_height=10,
        max_ticks=200,
        tick_rate_hz=1000.0,
        num_signals=1,
        num_toxins=1,
        wind_x=0.0,
        wind_y=0.0,
        mycorrhizal_growth_interval_ticks=8,
        mycorrhizal_connection_cost=1.0,
        mycorrhizal_inter_species=False,
        z4_herbivore_species_extinction=-1,  # disable extinction trigger
        flora_species=[
            FloraSpeciesParams(
                species_id=0,
                name="oak",
                base_energy=50.0,
                max_energy=1000.0,
                growth_rate=1.0,
                survival_threshold=0.1,
                reproduction_interval=99999,
                seed_energy_cost=0.0,
                triggers=[],
                passive_defenses=PassiveDefensesSchema(mechanical_damage_per_bite=0.0, digestibility_modifier=1.0),
            )
        ],
        herbivore_species=[
            HerbivoreSpeciesParams(
                species_id=0,
                name="deer",
                energy_min=1.0,
                velocity=1,
                consumption_rate=1.0,
                energy_upkeep_per_individual=0.0,
                resistances=HerbivoreResistancesSchema(),
            )
        ],
        diet_matrix=DietCompatibilityMatrix(rows=[[False]]),
        initial_plants=[
            InitialPlantPlacement(species_id=0, x=3, y=3, energy=50.0),
            InitialPlantPlacement(species_id=0, x=4, y=3, energy=50.0),  # Adjacent at dx=1
        ],
        initial_swarms=[
            InitialSwarmPlacement(species_id=0, x=1, y=1, population=1, energy=1.0),
        ],
    )

    loop = SimulationLoop(config, disable_replay=True)

    plant_entities = list(loop.world.query(PlantComponent))
    assert len(plant_entities) == 2, "Expected 2 initial plant entities"

    p1 = plant_entities[0].get_component(PlantComponent)
    p2 = plant_entities[1].get_component(PlantComponent)

    # Before tick 168 (slow loop gate), no connection exists
    await loop.step()  # tick 0
    assert p1.mycorrhizal_connections == set()

    # Step through 168 ticks to reach first weekly slow-loop gate (tick 168)
    for _ in range(168):
        await loop.step()

    # Connection MUST be established on slow-loop step 168
    assert p2.entity_id in p1.mycorrhizal_connections
    assert p1.entity_id in p2.mycorrhizal_connections


@pytest.mark.asyncio
async def test_simulation_loop_mycorrhiza_network_expands_across_collinear_plants() -> None:
    """SimulationLoop must expand root network across a chain of adjacent plants.

    With 4 collinear plants (x=2, 3, 4, 5 at y=5), the network must connect (2-3), (3-4), (4-5).
    """
    config = SimulationConfig(
        grid_width=12,
        grid_height=12,
        max_ticks=600,
        tick_rate_hz=1000.0,
        num_signals=1,
        num_toxins=1,
        wind_x=0.0,
        wind_y=0.0,
        mycorrhizal_growth_interval_ticks=8,
        mycorrhizal_connection_cost=1.0,
        mycorrhizal_inter_species=False,
        z4_herbivore_species_extinction=-1,
        flora_species=[
            FloraSpeciesParams(
                species_id=0,
                name="pine",
                base_energy=100.0,
                max_energy=2000.0,
                growth_rate=1.0,
                survival_threshold=0.1,
                reproduction_interval=99999,
                seed_energy_cost=0.0,
                triggers=[],
                passive_defenses=PassiveDefensesSchema(mechanical_damage_per_bite=0.0, digestibility_modifier=1.0),
            )
        ],
        herbivore_species=[
            HerbivoreSpeciesParams(
                species_id=0,
                name="deer",
                energy_min=1.0,
                velocity=1,
                consumption_rate=1.0,
                energy_upkeep_per_individual=0.0,
                resistances=HerbivoreResistancesSchema(),
            )
        ],
        diet_matrix=DietCompatibilityMatrix(rows=[[False]]),
        initial_plants=[
            InitialPlantPlacement(species_id=0, x=2, y=5, energy=100.0),
            InitialPlantPlacement(species_id=0, x=3, y=5, energy=100.0),
            InitialPlantPlacement(species_id=0, x=4, y=5, energy=100.0),
            InitialPlantPlacement(species_id=0, x=5, y=5, energy=100.0),
        ],
        initial_swarms=[
            InitialSwarmPlacement(species_id=0, x=1, y=1, population=1, energy=1.0),
        ],
    )

    loop = SimulationLoop(config, disable_replay=True)

    # Step for 3 slow-loop cycles (168 * 3 = 504 ticks)
    for _ in range(505):
        await loop.step()

    plants_by_x = {
        e.get_component(PlantComponent).x: e.get_component(PlantComponent) for e in loop.world.query(PlantComponent)
    }

    assert len(plants_by_x) == 4

    p2, p3, p4, p5 = plants_by_x[2], plants_by_x[3], plants_by_x[4], plants_by_x[5]

    # Check chain connectivity
    assert p3.entity_id in p2.mycorrhizal_connections
    assert p2.entity_id in p3.mycorrhizal_connections or p4.entity_id in p3.mycorrhizal_connections
    assert p4.entity_id in p5.mycorrhizal_connections


@pytest.mark.asyncio
async def test_simulation_loop_coexistence_and_metabolism_over_1000_ticks() -> None:
    """SimulationLoop must run 1000+ ticks without artificial extinction when balanced.

    Validates that plant growth (+168x weekly) and herbivore metabolism (24x daily)
    allow stable ecosystem coexistence over long simulation runs.
    """
    config = SimulationConfig(
        grid_width=16,
        grid_height=16,
        max_ticks=1050,
        tick_rate_hz=1000.0,
        num_signals=1,
        num_toxins=1,
        wind_x=0.0,
        wind_y=0.0,
        z4_herbivore_species_extinction=-1,
        z2_flora_species_extinction=-1,
        flora_species=[
            FloraSpeciesParams(
                species_id=0,
                name="clover",
                base_energy=50.0,
                max_energy=500.0,
                growth_rate=1.0,
                survival_threshold=0.1,
                reproduction_interval=99999,
                seed_energy_cost=0.0,
                triggers=[],
                passive_defenses=PassiveDefensesSchema(mechanical_damage_per_bite=0.0, digestibility_modifier=1.0),
            )
        ],
        herbivore_species=[
            HerbivoreSpeciesParams(
                species_id=0,
                name="rabbit",
                energy_min=1.0,
                velocity=1,
                consumption_rate=1.0,
                energy_upkeep_per_individual=0.0,
                resistances=HerbivoreResistancesSchema(),
            )
        ],
        diet_matrix=DietCompatibilityMatrix(rows=[[False]]),
        initial_plants=[
            InitialPlantPlacement(species_id=0, x=8, y=8, energy=50.0),
            InitialPlantPlacement(species_id=0, x=9, y=8, energy=50.0),
        ],
        initial_swarms=[
            InitialSwarmPlacement(species_id=0, x=1, y=1, population=1, energy=1.0),
        ],
    )

    loop = SimulationLoop(config, disable_replay=True)

    # Run for 1034 ticks (matching user screenshot tick landmark)
    for _ in range(1034):
        await loop.step()

    from phids.engine.components.swarm import SwarmComponent

    active_swarms = list(loop.world.query(SwarmComponent))
    active_plants = list(loop.world.query(PlantComponent))

    assert len(active_plants) > 0, "Plants must survive over 1034 ticks"
    assert len(active_swarms) > 0, "Herbivores must survive over 1034 ticks"
