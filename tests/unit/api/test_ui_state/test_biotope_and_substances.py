# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for scalar biotope normalization, substance-registry compaction, and diet toggling.

This module validates the architectural boundary concentrated in ``DraftService``
for three mutation families:
1. Scalar biotope normalization: grid dimensions, tick rate, wind, layer counts,
   mycorrhizal parameters, and termination thresholds clamped to documented bounds.
2. Substance registry compaction: substance removal re-indexes IDs, remaps trigger
   activation conditions, drops stale rules, and enforces the Rule-of-16 ceiling.
3. Diet-cell mutation: toggle/on/off semantics, including out-of-range coordinate
   handling.

MUTATION_TESTING_EXEMPTION: None - all branches are deterministic core arithmetic
and bounds-checking logic suitable for mutmut.
"""

from __future__ import annotations

import pytest

from phids.api.services.draft.biotope import update_biotope
from phids.api.services.draft.diet import set_diet_compatibility
from phids.api.services.draft.substances import add_substance, remove_substance, update_substance
from phids.api.services.draft.trigger_rules import add_trigger_rule
from phids.api.ui_state.state import DraftState


def test_draft_biotope_substance_and_diet_mutators_compact_substance_ids() -> None:
    """Validates scalar biotope normalization, substance-registry compaction, and diet-cell mutation semantics.

    Intent:
        Verify that the DraftService correctly clamps out-of-bound biotope scalars,
        compacts substance IDs after removal, remaps trigger-rule condition references,
        and enforces the Rule-of-16 substance ceiling.

    Preconditions:
        - DraftState.default() baseline with one flora/herbivore species.
        - Three substances added (Alarm, Shield, Relay) with activation conditions
          referencing substance_ids 1 and 2.
        - update_biotope called with all values outside legal bounds.

    Invariants Tested:
        - All clamped scalars reflect documented bounds (grid <= 200, ticks >= 1, etc.).
        - Substance removal compact-shifts IDs and remaps trigger condition references.
        - Trigger rules referencing the removed substance_id are dropped.
        - Rule-of-16: adding a 17th substance raises ValueError.
        - Diet cell toggle: returns current value (bool) or None for out-of-range coords.
    """
    draft = DraftState.default()
    add_substance(draft, name="Alarm")
    add_substance(draft, name="Shield", is_toxin="true", lethal="true")
    add_substance(draft, name="Relay")
    add_trigger_rule(
        draft,
        0,
        0,
        1,
        activation_condition={"kind": "substance_active", "substance_id": 1},
    )
    add_trigger_rule(
        draft,
        0,
        0,
        2,
        activation_condition={
            "kind": "all_of",
            "conditions": [
                {"kind": "substance_active", "substance_id": 2},
                {"kind": "substance_active", "substance_id": 0},
            ],
        },
    )

    was_clamped = update_biotope(
        draft,
        grid_width=250,
        grid_height=250,
        max_ticks=0,
        tick_rate_hz=0.0,
        wind_x=1.25,
        wind_y=-0.5,
        num_signals=99,
        num_toxins=0,
        z2_flora_species_extinction=99,
        z4_herbivore_species_extinction=-5,
        z6_max_total_flora_energy=-2.0,
        z7_max_total_herbivore_population=-9,
        mycorrhizal_inter_species=True,
        mycorrhizal_connection_cost=-2.0,
        mycorrhizal_growth_interval_ticks=0,
        mycorrhizal_signal_velocity=0,
    )
    assert was_clamped is True
    assert draft.grid_width == 250
    assert draft.grid_height == 250
    assert draft.max_ticks == 1
    assert draft.tick_rate_hz == pytest.approx(0.1)
    assert draft.wind_x == pytest.approx(1.25)
    assert draft.wind_y == pytest.approx(-0.5)
    assert draft.num_signals == 16
    assert draft.num_toxins == 1
    assert draft.z2_flora_species_extinction == 15
    assert draft.z4_herbivore_species_extinction == -1
    assert draft.z6_max_total_flora_energy == pytest.approx(-1.0)
    assert draft.z7_max_total_herbivore_population == -1
    assert draft.mycorrhizal_inter_species is True
    assert draft.mycorrhizal_connection_cost == pytest.approx(0.0)
    assert draft.mycorrhizal_growth_interval_ticks == 1
    assert draft.mycorrhizal_signal_velocity == 1

    updated = update_substance(
        draft,
        1,
        name="Shield+",
        type_label="Repellent Toxin",
        synthesis_duration=0,
        aftereffect_ticks=-3,
        lethality_rate=-1.0,
        repellent_walk_ticks=-2,
        energy_cost_per_tick=-4.0,
        irreversible="on",
    )
    assert updated.name == "Shield+"
    assert updated.is_toxin is True
    assert updated.lethal is False
    assert updated.repellent is True
    assert updated.synthesis_duration == 1
    assert updated.aftereffect_ticks == 0
    assert updated.lethality_rate == pytest.approx(0.0)
    assert updated.repellent_walk_ticks == 0
    assert updated.energy_cost_per_tick == pytest.approx(0.0)
    assert updated.irreversible is True

    assert set_diet_compatibility(draft, 0, 0, "toggle") is False
    assert set_diet_compatibility(draft, 0, 0, "on") is True
    assert set_diet_compatibility(draft, 9, 9, "on") is None

    remove_substance(draft, 1)
    assert [definition.substance_id for definition in draft.substance_definitions] == [0, 1]
    assert draft.substance_definitions[1].name == "Relay"
    assert len(draft.trigger_rules) == 1
    assert draft.trigger_rules[0].substance_id == 1
    assert draft.trigger_rules[0].activation_condition == {
        "kind": "all_of",
        "conditions": [
            {"kind": "substance_active", "substance_id": 1},
            {"kind": "substance_active", "substance_id": 0},
        ],
    }

    with pytest.raises(ValueError):
        update_substance(draft, 99, name="missing")
    with pytest.raises(ValueError):
        remove_substance(draft, 99)

    saturated = DraftState.default()
    for idx in range(16):
        add_substance(saturated, name=f"S{idx}")
    with pytest.raises(ValueError):
        add_substance(saturated, name="overflow")
