# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for placement mutation, SimulationConfig building, and draft-singleton helpers.

This module verifies the correct behavior of placement CRUD operations,
the final config-building step that translates DraftState to SimulationConfig,
and the three draft-singleton functions: get_draft, set_draft, and reset_draft.

MUTATION_TESTING_EXEMPTION: None - all paths are deterministic core logic.
"""

from __future__ import annotations

from typing import cast

import pytest

from phids.api.schemas.simulation import SimulationConfig
from phids.api.services.draft.placements import (
    add_plant_placement,
    add_swarm_placement,
    clear_placements,
    remove_plant_placement,
    remove_swarm_placement,
)
from phids.api.services.draft.trigger_rules import add_trigger_rule
from phids.api.ui_state.state import DraftState, get_draft, reset_draft, set_draft
from phids.api.ui_state.substances import SubstanceDefinition
from phids.api.ui_state.triggers import TriggerRule


def test_draft_placements_build_config_and_singleton_helpers() -> None:
    """Verify placement mutators, config building, and draft singleton helpers stay consistent.

    Intent:
        Validate the complete placement lifecycle (add, remove, clear), the final
        config-build step with all non-default scalar overrides, and the three
        singleton functions that expose the global DraftState.

    Preconditions:
        - DraftState.default() baseline.
        - Two placements added then removed; fresh pair added before build.
        - One valid trigger rule and one rule with invalid substance_id (99).

    Invariants Tested:
        - build_sim_config() raises ValueError for an empty species list.
        - Persisted placements appear at the correct coordinates in the built config.
        - mycorrhizal_growth_interval_ticks and all Z-thresholds are passed through.
        - Invalid trigger rule (substance_id=99) is silently dropped from config.
        - clear_placements resets both lists to empty.
        - set_draft/get_draft/reset_draft cycle operates correctly on the singleton.
    """
    empty_draft = DraftState(flora_species=[], herbivore_species=[])
    with pytest.raises(ValueError):
        empty_draft.build_sim_config()

    draft = DraftState.default()
    draft.substance_definitions = [SubstanceDefinition(substance_id=0, name="Alarm")]
    add_trigger_rule(
        draft,
        0,
        0,
        0,
        min_herbivore_population=5,
        activation_condition={
            "kind": "herbivore_presence",
            "herbivore_species_id": 0,
            "min_herbivore_population": 5,
        },
    )
    draft.trigger_rules.append(TriggerRule(flora_species_id=0, herbivore_species_id=0, substance_id=99))
    draft.mycorrhizal_growth_interval_ticks = 11
    draft.z2_flora_species_extinction = 0
    draft.z4_herbivore_species_extinction = 0
    draft.z6_max_total_flora_energy = 123.0
    draft.z7_max_total_herbivore_population = 77

    add_plant_placement(draft, 0, 1, 2, 7.5)
    add_swarm_placement(draft, 0, 3, 4, 6, 12.0)
    remove_plant_placement(draft, 0)
    remove_swarm_placement(draft, 0)
    add_plant_placement(draft, 0, 2, 2, 8.5)
    add_swarm_placement(draft, 0, 2, 2, 4, 9.0)

    config = cast("SimulationConfig", draft.build_sim_config())
    assert config.mycorrhizal_growth_interval_ticks == 11
    assert config.z2_flora_species_extinction == 0
    assert config.z4_herbivore_species_extinction == 0
    assert config.z6_max_total_flora_energy == pytest.approx(123.0)
    assert config.z7_max_total_herbivore_population == 77
    assert len(config.flora_species[0].triggers) == 1
    assert config.initial_plants[0].x == 2
    assert config.initial_swarms[0].population == 4

    clear_placements(draft)
    assert draft.initial_plants == []
    assert draft.initial_swarms == []

    replacement = DraftState.default()
    replacement.scenario_name = "Custom"
    set_draft(replacement)
    assert get_draft().scenario_name == "Custom"
    reset_draft()
    assert get_draft().scenario_name == "Default Scenario"
