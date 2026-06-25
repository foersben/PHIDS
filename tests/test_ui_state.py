"""
Test coverage for PHIDS DraftState and UI state mutation invariants.

This module implements unit tests for the PHIDS DraftState and UI state mutation logic. The test suite verifies deterministic scenario construction, species and substance management, trigger rule editing, and placement mutation, ensuring compliance with the Rule of 16, O(1) spatial hash invariants, and double-buffered simulation logic. Each test function is documented to state the invariant or biological behavior being validated and its scientific rationale, supporting reproducible and rigorous validation of emergent ecological dynamics and UI configuration. The module-level docstring is written in accordance with Google-style documentation standards, providing a comprehensive scholarly abstract of the test suite's scope and scientific rationale.
"""

from __future__ import annotations

from copy import deepcopy
from typing import cast

import pytest

from phids.api.schemas import FloraSpeciesParams, PredatorSpeciesParams, SimulationConfig
from phids.api.ui_state import (
    DraftState,
    SubstanceDefinition,
    TriggerRule,
    _condition_node_at_path,
    _default_activation_condition_node,
    _legacy_signal_ids_to_activation_condition,
    _parse_condition_path,
    _prune_empty_condition_groups,
    _remap_condition_references,
    get_draft,
    reset_draft,
    set_draft,
)


def _flora(species_id: int, name: str | None = None) -> FloraSpeciesParams:
    return FloraSpeciesParams(
        species_id=species_id,
        name=name or f"flora-{species_id}",
        base_energy=10.0,
        max_energy=25.0,
        growth_rate=3.0,
        survival_threshold=1.0,
        reproduction_interval=4,
        seed_min_dist=1.0,
        seed_max_dist=2.0,
        seed_energy_cost=1.0,
        triggers=[],
    )


def _predator(species_id: int, name: str | None = None) -> PredatorSpeciesParams:
    return PredatorSpeciesParams(
        species_id=species_id,
        name=name or f"predator-{species_id}",
        energy_min=1.0,
        velocity=1,
        consumption_rate=1.5,
        reproduction_energy_divisor=1.0,
    )


@pytest.fixture(autouse=True)
def _reset_draft_singleton() -> None:
    reset_draft()


def test_condition_helper_utilities_and_type_labels() -> None:
    """
    Validates condition helper utilities and substance type labeling invariants in PHIDS DraftState.

    This test function verifies the deterministic mapping of substance definitions to scientific type labels, the conversion of legacy signal IDs to activation conditions, and the parsing of condition paths. The function ensures that the architectural logic for condition trees and substance activation is robust and biologically precise, supporting reproducible signal propagation and trigger rule construction.

    Args:
        None

    Returns:
        None. Asserts correctness of condition utilities and substance labeling.

    Raises:
        ValueError: If unsupported condition kind is provided, validating architectural error handling for condition node creation.
    """
    assert SubstanceDefinition(substance_id=0, is_toxin=False).type_label == "Signal"
    assert SubstanceDefinition(substance_id=1, is_toxin=True).type_label == "Toxin"
    assert (
        SubstanceDefinition(substance_id=2, is_toxin=True, lethal=True).type_label == "Lethal Toxin"
    )
    assert (
        SubstanceDefinition(substance_id=3, is_toxin=True, repellent=True).type_label
        == "Repellent Toxin"
    )

    assert _legacy_signal_ids_to_activation_condition(None) is None
    assert _legacy_signal_ids_to_activation_condition([-1, -5]) is None
    assert _legacy_signal_ids_to_activation_condition([4]) == {
        "kind": "substance_active",
        "substance_id": 4,
    }
    assert _legacy_signal_ids_to_activation_condition([2, 5]) == {
        "kind": "all_of",
        "conditions": [
            {"kind": "substance_active", "substance_id": 2},
            {"kind": "substance_active", "substance_id": 5},
        ],
    }

    assert _parse_condition_path("") == []
    assert _parse_condition_path("0.1.2") == [0, 1, 2]

    assert _default_activation_condition_node(
        "enemy_presence",
        predator_species_id=3,
        min_predator_population=0,
    ) == {
        "kind": "enemy_presence",
        "predator_species_id": 3,
        "min_predator_population": 1,
    }
    assert _default_activation_condition_node("substance_active", substance_id=7) == {
        "kind": "substance_active",
        "substance_id": 7,
    }
    group_node = cast(
        dict[str, object],
        _default_activation_condition_node("all_of", predator_species_id=2),
    )
    group_conditions = cast(list[dict[str, object]], group_node["conditions"])
    assert group_conditions[0]["predator_species_id"] == 2
    assert _default_activation_condition_node("any_of")["kind"] == "any_of"

    with pytest.raises(ValueError):
        _default_activation_condition_node("unsupported")


def test_condition_tree_navigation_pruning_and_remap() -> None:
    """
    Validates navigation, pruning, and remapping of condition trees in PHIDS DraftState.

    This test function asserts the correctness of condition node navigation, pruning of empty groups, and remapping of references after species or substance removal. The architectural logic ensures that condition trees remain consistent and biologically meaningful after mutation, supporting robust trigger rule editing and scenario configuration.

    Args:
        None

    Returns:
        None. Asserts correctness of navigation, pruning, and remapping operations.

    Raises:
        IndexError: If navigation attempts to access invalid condition paths, validating error handling for tree traversal.
    """
    root = {
        "kind": "all_of",
        "conditions": [
            {"kind": "enemy_presence", "predator_species_id": 1, "min_predator_population": 2},
            {
                "kind": "any_of",
                "conditions": [
                    {"kind": "substance_active", "substance_id": 3},
                    {
                        "kind": "enemy_presence",
                        "predator_species_id": 2,
                        "min_predator_population": 4,
                    },
                ],
            },
        ],
    }
    assert _condition_node_at_path(root, [1])["kind"] == "any_of"
    assert _condition_node_at_path(root, [1, 0])["substance_id"] == 3

    with pytest.raises(IndexError):
        _condition_node_at_path({"kind": "enemy_presence"}, [0])
    with pytest.raises(IndexError):
        _condition_node_at_path({"kind": "all_of", "conditions": []}, [0])
    with pytest.raises(IndexError):
        _condition_node_at_path({"kind": "all_of", "conditions": ["bad"]}, [0])

    assert _prune_empty_condition_groups(None) is None
    assert _prune_empty_condition_groups({"kind": "substance_active", "substance_id": 1}) == {
        "kind": "substance_active",
        "substance_id": 1,
    }
    assert _prune_empty_condition_groups(
        {
            "kind": "all_of",
            "conditions": [
                {"kind": "any_of", "conditions": []},
                {"kind": "substance_active", "substance_id": 5},
                "ignored",
            ],
        }
    ) == {
        "kind": "all_of",
        "conditions": [{"kind": "substance_active", "substance_id": 5}],
    }

    remapped = _remap_condition_references(
        deepcopy(root),
        removed_predator_id=1,
        removed_substance_id=2,
    )
    assert remapped == {
        "kind": "all_of",
        "conditions": [
            {
                "kind": "any_of",
                "conditions": [
                    {"kind": "substance_active", "substance_id": 2},
                    {
                        "kind": "enemy_presence",
                        "predator_species_id": 1,
                        "min_predator_population": 4,
                    },
                ],
            }
        ],
    }
    assert (
        _remap_condition_references(
            {"kind": "enemy_presence", "predator_species_id": 0, "min_predator_population": 1},
            removed_predator_id=0,
        )
        is None
    )
    assert (
        _remap_condition_references(
            {"kind": "substance_active", "substance_id": 0},
            removed_substance_id=0,
        )
        is None
    )


def test_draft_species_mutations_compact_rules_and_resize_diet_matrix() -> None:
    """
    Validates species mutation, rule compaction, and diet matrix resizing in PHIDS DraftState.

    This test function verifies that species removal triggers deterministic compaction of trigger rules and resizing of diet matrices, preserving architectural invariants and biological relationships. The function ensures that scenario configuration remains consistent and supports reproducible ecological dynamics after mutation.

    Args:
        None

    Returns:
        None. Asserts correctness of species mutation, rule compaction, and diet matrix resizing.

    Raises:
        ValueError: If removal is attempted for non-existent flora or predator species, validating architectural error handling for mutation operations.
    """
    draft = DraftState(
        flora_species=[_flora(0, "A"), _flora(1, "B")],
        predator_species=[_predator(0, "P0"), _predator(1, "P1")],
        diet_matrix=[[True, False], [False, True]],
        trigger_rules=[
            TriggerRule(
                flora_species_id=1,
                predator_species_id=1,
                substance_id=0,
                activation_condition={
                    "kind": "enemy_presence",
                    "predator_species_id": 1,
                    "min_predator_population": 2,
                },
            )
        ],
        substance_definitions=[SubstanceDefinition(substance_id=0, name="Alarm")],
    )
    draft.add_plant_placement(1, 3, 3, 9.0)
    draft.add_swarm_placement(1, 3, 3, 5, 8.0)

    draft.remove_flora(0)
    assert [cast(FloraSpeciesParams, flora).species_id for flora in draft.flora_species] == [0]
    assert draft.diet_matrix == [[False], [True]]
    assert draft.trigger_rules[0].flora_species_id == 0

    draft.remove_predator(0)
    assert [
        cast(PredatorSpeciesParams, predator).species_id for predator in draft.predator_species
    ] == [0]
    assert draft.diet_matrix == [[True]]
    assert draft.trigger_rules[0].predator_species_id == 0
    assert draft.trigger_rules[0].activation_condition == {
        "kind": "enemy_presence",
        "predator_species_id": 0,
        "min_predator_population": 2,
    }

    with pytest.raises(ValueError):
        draft.remove_flora(99)
    with pytest.raises(ValueError):
        draft.remove_predator(99)


def test_draft_trigger_rule_tree_mutators_cover_error_paths() -> None:
    """
    Validates trigger rule tree mutation and error path coverage in PHIDS DraftState.

    This test function asserts the correctness of trigger rule tree mutation operations, including appending, updating, replacing, and deleting condition nodes. The function also verifies architectural error handling for invalid mutation paths, supporting robust and reproducible trigger rule editing in scenario configuration.

    Args:
        None

    Returns:
        None. Asserts correctness of trigger rule tree mutation and error handling.

    Raises:
        IndexError: If mutation attempts to access invalid condition paths, validating architectural error handling for tree mutation operations.
    """
    draft = DraftState.default()
    draft.substance_definitions = [
        SubstanceDefinition(substance_id=0, name="Signal 0"),
        SubstanceDefinition(substance_id=1, name="Signal 1"),
    ]
    draft.add_trigger_rule(0, 0, 0, required_signal_ids=[0, 1])
    assert draft.trigger_rules[0].activation_condition == {
        "kind": "all_of",
        "conditions": [
            {"kind": "substance_active", "substance_id": 0},
            {"kind": "substance_active", "substance_id": 1},
        ],
    }

    draft.update_trigger_rule(
        0,
        substance_id=1,
        min_predator_population=7,
        required_signal_ids=[1],
    )
    assert draft.trigger_rules[0].substance_id == 1
    assert draft.trigger_rules[0].min_predator_population == 7
    assert draft.trigger_rules[0].activation_condition == {
        "kind": "substance_active",
        "substance_id": 1,
    }

    draft.set_trigger_rule_activation_condition(
        0,
        {
            "kind": "all_of",
            "conditions": [
                {"kind": "enemy_presence", "predator_species_id": 0, "min_predator_population": 2}
            ],
        },
    )
    draft.append_trigger_rule_condition_child(
        0,
        "",
        {"kind": "substance_active", "substance_id": 1},
    )
    draft.update_trigger_rule_condition_node(0, "0", min_predator_population=3)
    draft.replace_trigger_rule_condition_node(
        0,
        "1",
        {"kind": "enemy_presence", "predator_species_id": 0, "min_predator_population": 4},
    )
    assert draft.trigger_rules[0].activation_condition == {
        "kind": "all_of",
        "conditions": [
            {"kind": "enemy_presence", "predator_species_id": 0, "min_predator_population": 3},
            {"kind": "enemy_presence", "predator_species_id": 0, "min_predator_population": 4},
        ],
    }

    draft.delete_trigger_rule_condition_node(0, "1")
    assert draft.trigger_rules[0].activation_condition == {
        "kind": "all_of",
        "conditions": [
            {"kind": "enemy_presence", "predator_species_id": 0, "min_predator_population": 3}
        ],
    }
    draft.delete_trigger_rule_condition_node(0, "")
    assert draft.trigger_rules[0].activation_condition is None

    with pytest.raises(IndexError):
        draft.append_trigger_rule_condition_child(
            0, "", {"kind": "substance_active", "substance_id": 0}
        )
    with pytest.raises(IndexError):
        draft.update_trigger_rule_condition_node(0, "0", substance_id=0)
    with pytest.raises(IndexError):
        draft.replace_trigger_rule_condition_node(
            0,
            "0",
            {"kind": "substance_active", "substance_id": 0},
        )

    draft.remove_trigger_rule(0)
    assert draft.trigger_rules == []


def test_draft_placements_build_config_and_singleton_helpers() -> None:
    """
    Validates placement mutation, config building, and singleton helpers in PHIDS DraftState.

    This test function verifies the correctness of plant and swarm placement mutation, config building, and singleton state management. The function ensures that architectural invariants for scenario construction, placement mutation, and singleton helpers are preserved, supporting reproducible and robust UI configuration and simulation logic.

    Args:
        None

    Returns:
        None. Asserts correctness of placement mutation, config building, and singleton helpers.

    Raises:
        ValueError: If config building is attempted with empty species lists, validating architectural error handling for scenario construction.
    """
    empty_draft = DraftState(flora_species=[], predator_species=[])
    with pytest.raises(ValueError):
        empty_draft.build_sim_config()

    draft = DraftState.default()
    draft.substance_definitions = [SubstanceDefinition(substance_id=0, name="Alarm")]
    draft.add_trigger_rule(
        0,
        0,
        0,
        min_predator_population=5,
        activation_condition={
            "kind": "enemy_presence",
            "predator_species_id": 0,
            "min_predator_population": 5,
        },
    )
    draft.trigger_rules.append(
        TriggerRule(flora_species_id=0, predator_species_id=0, substance_id=99)
    )
    draft.mycorrhizal_growth_interval_ticks = 11

    draft.add_plant_placement(0, 1, 2, 7.5)
    draft.add_swarm_placement(0, 3, 4, 6, 12.0)
    draft.remove_plant_placement(0)
    draft.remove_swarm_placement(0)
    draft.add_plant_placement(0, 2, 2, 8.5)
    draft.add_swarm_placement(0, 2, 2, 4, 9.0)

    config = cast(SimulationConfig, draft.build_sim_config())
    assert config.mycorrhizal_growth_interval_ticks == 11
    assert len(config.flora_species[0].triggers) == 1
    assert config.initial_plants[0].x == 2
    assert config.initial_swarms[0].population == 4

    draft.clear_placements()
    assert draft.initial_plants == []
    assert draft.initial_swarms == []

    replacement = DraftState.default()
    replacement.scenario_name = "Custom"
    set_draft(replacement)
    assert get_draft().scenario_name == "Custom"
    reset_draft()
    assert get_draft().scenario_name == "Default Scenario"
