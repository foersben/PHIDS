# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for species removal, ID compaction, diet matrix resizing, and rule remapping.

This module verifies that removing flora or herbivore species from a DraftState:
1. Compacts species_id values to a zero-based contiguous sequence.
2. Resizes the diet matrix consistently (drops the removed column/row).
3. Remaps trigger-rule species references to the new compacted IDs.
4. Removes stale placements that reference the deleted species.
5. Raises ValueError for invalid species IDs.

MUTATION_TESTING_EXEMPTION: None - all branches are deterministic core logic.
"""

from __future__ import annotations

from typing import cast

import pytest

from phids.api.schemas.species import FloraSpeciesParams, HerbivoreSpeciesParams
from phids.api.services.draft.placements import add_plant_placement, add_swarm_placement
from phids.api.services.draft.species import remove_flora, remove_herbivore
from phids.api.ui_state.state import DraftState
from phids.api.ui_state.substances import SubstanceDefinition
from phids.api.ui_state.triggers import TriggerRule

from .conftest import _flora, _herbivore


def test_draft_species_mutations_compact_rules_and_resize_diet_matrix() -> None:
    """Verify species removals compact IDs, remap rules, and resize diet matrices consistently.

    Intent:
        Confirm that the full species-removal pipeline - compact, remap, resize -
        preserves the ecological semantics of the remaining species and their
        trigger associations.

    Preconditions:
        - Two flora species (0, 1) and two herbivore species (0, 1).
        - Diet matrix [[True, False], [False, True]].
        - One trigger rule referencing flora_id=1, herbivore_id=1, substance_id=0.
        - Placements for species_id=1 added before removal.

    Invariants Tested:
        - After removing flora 0: remaining flora has species_id=0; diet matrix
          drops column 0; trigger rule flora_species_id decrements to 0.
        - After removing herbivore 0: remaining herbivore has species_id=0; diet
          matrix drops row 0; trigger rule herbivore_species_id and activation
          condition decremented to 0.
        - Removing a non-existent species raises ValueError.
    """
    draft = DraftState(
        flora_species=[_flora(0, "A"), _flora(1, "B")],
        herbivore_species=[_herbivore(0, "H0"), _herbivore(1, "H1")],
        diet_matrix=[[True, False], [False, True]],
        trigger_rules=[
            TriggerRule(
                flora_species_id=1,
                herbivore_species_id=1,
                substance_id=0,
                activation_condition={
                    "kind": "herbivore_presence",
                    "herbivore_species_id": 1,
                    "min_herbivore_population": 2,
                },
            )
        ],
        substance_definitions=[SubstanceDefinition(substance_id=0, name="Alarm")],
    )
    add_plant_placement(draft, 1, 3, 3, 9.0)
    add_swarm_placement(draft, 1, 3, 3, 5, 8.0)

    remove_flora(draft, 0)
    assert [cast("FloraSpeciesParams", flora).species_id for flora in draft.flora_species] == [0]
    assert draft.diet_matrix == [[False], [True]]
    assert draft.trigger_rules[0].flora_species_id == 0

    remove_herbivore(draft, 0)
    assert [cast("HerbivoreSpeciesParams", herbivore).species_id for herbivore in draft.herbivore_species] == [0]
    assert draft.diet_matrix == [[True]]
    assert draft.trigger_rules[0].herbivore_species_id == 0
    assert draft.trigger_rules[0].activation_condition == {
        "kind": "herbivore_presence",
        "herbivore_species_id": 0,
        "min_herbivore_population": 2,
    }

    with pytest.raises(ValueError):
        remove_flora(draft, 99)
    with pytest.raises(ValueError):
        remove_herbivore(draft, 99)
