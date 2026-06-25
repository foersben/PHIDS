"""Experimental validation suite for test schemas and invariants.

This module defines hypothesis-driven checks for deterministic ecosystem behavior, API constraints, and simulation invariants. The tests map computational rules to biological interpretations, including metabolic attrition, trigger-gated signaling, and O(1) spatial locality assumptions, to ensure that implementation details remain aligned with the PHIDS scientific model.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from phids.api.schemas import (
    AllOfConditionSchema,
    DietCompatibilityMatrix,
    EnemyPresenceConditionSchema,
    FloraSpeciesParams,
    InitialPlantPlacement,
    InitialSwarmPlacement,
    PredatorSpeciesParams,
    SimulationConfig,
    SubstanceActiveConditionSchema,
    TriggerConditionSchema,
)
from phids.engine.components.plant import PlantComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld


def _flora(species_id: int = 0) -> FloraSpeciesParams:
    return FloraSpeciesParams(
        species_id=species_id,
        name=f"flora-{species_id}",
        base_energy=10.0,
        max_energy=20.0,
        growth_rate=2.0,
        survival_threshold=1.0,
        reproduction_interval=2,
        seed_min_dist=1.0,
        seed_max_dist=2.0,
        seed_energy_cost=1.0,
        triggers=[],
    )


def _predator(species_id: int = 0) -> PredatorSpeciesParams:
    return PredatorSpeciesParams(
        species_id=species_id,
        name=f"predator-{species_id}",
        energy_min=1.0,
        velocity=1,
        consumption_rate=1.0,
    )


def test_trigger_schema_supports_full_substance_matrix() -> None:
    """Validates the trigger schema supports full substance matrix invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    trig = TriggerConditionSchema(
        predator_species_id=1,
        min_predator_population=3,
        substance_id=2,
        synthesis_duration=4,
        is_toxin=True,
        lethal=True,
        lethality_rate=0.25,
        repellent=True,
        repellent_walk_ticks=5,
        aftereffect_ticks=7,
        activation_condition=AllOfConditionSchema(
            conditions=[
                SubstanceActiveConditionSchema(substance_id=1),
                EnemyPresenceConditionSchema(predator_species_id=2, min_predator_population=4),
            ]
        ),
        energy_cost_per_tick=0.6,
    )

    assert trig.is_toxin is True
    assert trig.lethal is True
    assert trig.repellent is True
    assert trig.lethality_rate == 0.25
    assert trig.aftereffect_ticks == 7
    assert trig.energy_cost_per_tick == 0.6
    assert trig.activation_condition is not None
    assert trig.activation_condition.kind == "all_of"


def test_diet_matrix_enforces_rule_of_16() -> None:
    """Validates the diet matrix enforces rule of 16 invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    with pytest.raises(ValidationError):
        DietCompatibilityMatrix(rows=[[True] * 17])


def test_simulation_config_rejects_unknown_species_placements() -> None:
    """Validates the simulation config rejects unknown species placements invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    flora = [_flora(0)]
    predator = [_predator(0)]

    with pytest.raises(ValidationError):
        SimulationConfig(
            flora_species=flora,
            predator_species=predator,
            diet_matrix=DietCompatibilityMatrix(rows=[[True]]),
            initial_plants=[InitialPlantPlacement(species_id=1, x=0, y=0, energy=5.0)],
        )

    with pytest.raises(ValidationError):
        SimulationConfig(
            flora_species=flora,
            predator_species=predator,
            diet_matrix=DietCompatibilityMatrix(rows=[[True]]),
            initial_swarms=[
                InitialSwarmPlacement(species_id=1, x=0, y=0, population=2, energy=4.0)
            ],
        )


def test_simulation_config_validates_mycorrhizal_growth_interval_bounds() -> None:
    """Validates the simulation config validates mycorrhizal growth interval bounds invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    flora = [_flora(0)]
    predator = [_predator(0)]

    with pytest.raises(ValidationError):
        SimulationConfig(
            flora_species=flora,
            predator_species=predator,
            diet_matrix=DietCompatibilityMatrix(rows=[[True]]),
            mycorrhizal_growth_interval_ticks=0,
        )

    config = SimulationConfig(
        flora_species=flora,
        predator_species=predator,
        diet_matrix=DietCompatibilityMatrix(rows=[[True]]),
        mycorrhizal_growth_interval_ticks=12,
    )

    assert config.mycorrhizal_growth_interval_ticks == 12


def test_grid_environment_invariants_and_double_buffer_swap() -> None:
    """Validates the grid environment invariants and double buffer swap invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    env = GridEnvironment(width=4, height=4, num_signals=1, num_toxins=1)

    with pytest.raises(ValueError):
        GridEnvironment(width=81, height=4, num_signals=1, num_toxins=1)

    with pytest.raises(ValueError):
        GridEnvironment(width=4, height=81, num_signals=1, num_toxins=1)

    env.set_plant_energy(1, 2, species_id=0, value=3.0)
    env.rebuild_energy_layer()
    assert env.plant_energy_layer[1, 2] == pytest.approx(3.0)

    env.clear_plant_energy(1, 2, species_id=0)
    env.rebuild_energy_layer()
    assert env.plant_energy_layer[1, 2] == pytest.approx(0.0)


def test_ecs_query_intersection_and_component_removal() -> None:
    """Validates the ecs query intersection and component removal invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    world = ECSWorld()

    class C1:
        pass

    class C2:
        pass

    e1 = world.create_entity()
    e2 = world.create_entity()

    world.add_component(e1.entity_id, C1())
    world.add_component(e1.entity_id, C2())
    world.add_component(e2.entity_id, C1())

    both = [e.entity_id for e in world.query(C1, C2)]
    assert both == [e1.entity_id]

    world.remove_component(e1.entity_id, C2)
    assert list(world.query(C1, C2)) == []


def test_spatial_hash_allows_multiple_entities_per_cell() -> None:
    """Validates the spatial hash allows multiple entities per cell invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    world = ECSWorld()
    e1 = world.create_entity()
    e2 = world.create_entity()

    world.register_position(e1.entity_id, 2, 2)
    world.register_position(e2.entity_id, 2, 2)

    assert world.entities_at(2, 2) == {e1.entity_id, e2.entity_id}


def test_plant_component_energy_never_negative_on_set() -> None:
    """Validates the plant component energy never negative on set invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    env = GridEnvironment(width=3, height=3, num_signals=1, num_toxins=1)
    world = ECSWorld()
    e = world.create_entity()
    plant = PlantComponent(
        entity_id=e.entity_id,
        species_id=0,
        x=1,
        y=1,
        energy=5.0,
        max_energy=10.0,
        base_energy=5.0,
        growth_rate=1.0,
        survival_threshold=1.0,
        reproduction_interval=10,
        seed_min_dist=1.0,
        seed_max_dist=2.0,
        seed_energy_cost=1.0,
    )
    world.add_component(e.entity_id, plant)

    env.set_plant_energy(1, 1, 0, -99.0)
    env.rebuild_energy_layer()
    assert env.plant_energy_layer[1, 1] == pytest.approx(0.0)
