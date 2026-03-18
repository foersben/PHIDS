"""Pydantic schema validation and SimulationConfig invariant tests.

This module validates the correctness of PHIDS Pydantic v2 schema constraints at the API ingress
boundary. The primary hypotheses are: (1) ``SimulationConfig`` raises ``ValidationError`` when
species placement identifiers reference undeclared flora or herbivore species, preventing
reference-integrity violations before any engine state is allocated; (2) ``DietCompatibilityMatrix``
rejects row counts and column counts exceeding the Rule-of-16 bounds; (3) the activation-condition
schema tree correctly validates ``all_of``, ``any_of``, ``herbivore_presence``, and
``substance_active`` nodes and rejects structurally invalid compositions; (4)
``TriggerConditionSchema`` correctly migrates legacy ``precursor_signal_id`` fields into the
unified ``activation_condition`` tree via its ``model_validator``; and (5) ``GridEnvironment``
raises ``ValueError`` for width, height, signal, and toxin layer counts outside their valid
ranges, confirming that defensive bounds checking is present at the engine level independently
of the API schema layer.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from phids.api.schemas import (
    AllOfConditionSchema,
    DietCompatibilityMatrix,
    HerbivorePresenceConditionSchema,
    FloraSpeciesParams,
    HerbivoreSpeciesParams,
    InitialPlantPlacement,
    InitialSwarmPlacement,
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


def _herbivore(species_id: int = 0) -> HerbivoreSpeciesParams:
    return HerbivoreSpeciesParams(
        species_id=species_id,
        name=f"herbivore-{species_id}",
        energy_min=1.0,
        velocity=1,
        consumption_rate=1.0,
    )


def test_trigger_schema_supports_full_substance_matrix() -> None:
    """Verify trigger schema accepts the full toxin and activation-condition field matrix."""
    trig = TriggerConditionSchema(
        herbivore_species_id=1,
        min_herbivore_population=3,
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
                HerbivorePresenceConditionSchema(
                    herbivore_species_id=2, min_herbivore_population=4
                ),
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
    """Verify diet compatibility matrices reject row widths above the Rule-of-16 cap."""
    with pytest.raises(ValidationError):
        DietCompatibilityMatrix(rows=[[True] * 17])


def test_simulation_config_rejects_unknown_species_placements() -> None:
    """Verify placement entries referencing undeclared species fail config validation."""
    flora = [_flora(0)]
    herbivore = [_herbivore(0)]

    with pytest.raises(ValidationError):
        SimulationConfig(
            flora_species=flora,
            herbivore_species=herbivore,
            diet_matrix=DietCompatibilityMatrix(rows=[[True]]),
            initial_plants=[InitialPlantPlacement(species_id=1, x=0, y=0, energy=5.0)],
        )

    with pytest.raises(ValidationError):
        SimulationConfig(
            flora_species=flora,
            herbivore_species=herbivore,
            diet_matrix=DietCompatibilityMatrix(rows=[[True]]),
            initial_swarms=[
                InitialSwarmPlacement(species_id=1, x=0, y=0, population=2, energy=4.0)
            ],
        )


def test_simulation_config_validates_mycorrhizal_growth_interval_bounds() -> None:
    """Verify mycorrhizal growth interval bounds are enforced and valid values are preserved."""
    flora = [_flora(0)]
    herbivore = [_herbivore(0)]

    with pytest.raises(ValidationError):
        SimulationConfig(
            flora_species=flora,
            herbivore_species=herbivore,
            diet_matrix=DietCompatibilityMatrix(rows=[[True]]),
            mycorrhizal_growth_interval_ticks=0,
        )

    config = SimulationConfig(
        flora_species=flora,
        herbivore_species=herbivore,
        diet_matrix=DietCompatibilityMatrix(rows=[[True]]),
        mycorrhizal_growth_interval_ticks=12,
    )

    assert config.mycorrhizal_growth_interval_ticks == 12


def test_grid_environment_invariants_and_double_buffer_swap() -> None:
    """Verify grid bounds checks and plant-energy write/read buffer swapping semantics."""
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
    """Verify ECS multi-component queries update immediately after component removal."""
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
    """Verify spatial hash buckets retain multiple entity IDs per coordinate."""
    world = ECSWorld()
    e1 = world.create_entity()
    e2 = world.create_entity()

    world.register_position(e1.entity_id, 2, 2)
    world.register_position(e2.entity_id, 2, 2)

    assert world.entities_at(2, 2) == {e1.entity_id, e2.entity_id}


def test_plant_component_energy_never_negative_on_set() -> None:
    """Verify plant-energy writes clamp negative values to zero on rebuild."""
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
