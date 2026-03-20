"""Bounded Hypothesis pilot for signaling activation-condition Boolean semantics."""

from __future__ import annotations

import pytest

from phids.engine.components.plant import PlantComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.systems.signaling import _check_activation_condition

try:
    from hypothesis import given, settings, strategies as st
except ModuleNotFoundError:
    pytest.skip("Install hypothesis to run optional property pilots.", allow_module_level=True)


def _plant_at(x: int, y: int) -> PlantComponent:
    """Return a minimal plant component located at a specific grid coordinate."""
    return PlantComponent(
        entity_id=7,
        species_id=0,
        x=x,
        y=y,
        energy=10.0,
        max_energy=20.0,
        base_energy=10.0,
        growth_rate=1.0,
        survival_threshold=1.0,
        reproduction_interval=2,
        seed_min_dist=1.0,
        seed_max_dist=2.0,
        seed_energy_cost=1.0,
    )


@pytest.mark.hypothesis_pilot
@settings(max_examples=96, deadline=None, derandomize=True)
@given(
    left_true=st.booleans(),
    right_true=st.booleans(),
    combinator_kind=st.sampled_from(("all_of", "any_of")),
)
def test_composite_activation_conditions_follow_boolean_truth_tables(
    left_true: bool,
    right_true: bool,
    combinator_kind: str,
) -> None:
    """Composite activation nodes evaluate exactly like all/any over their child predicates."""
    env = GridEnvironment(width=3, height=3, num_signals=1, num_toxins=1)
    plant = _plant_at(1, 1)

    env.signal_layers[0, 1, 1] = 0.2 if right_true else 0.0
    swarm_index = {(1, 1, 0): 1 if left_true else 0}

    condition = {
        "kind": combinator_kind,
        "conditions": [
            {
                "kind": "herbivore_presence",
                "herbivore_species_id": 0,
                "min_herbivore_population": 1,
            },
            {
                "kind": "environmental_signal",
                "signal_id": 0,
                "min_concentration": 0.1,
            },
        ],
    }

    result = _check_activation_condition(
        plant,
        owner_plant_id=plant.entity_id,
        activation_condition=condition,
        env=env,
        swarm_population_by_cell_species=swarm_index,
        active_substance_ids_by_owner={},
    )

    expected = (
        (left_true and right_true) if combinator_kind == "all_of" else (left_true or right_true)
    )
    assert result is expected
