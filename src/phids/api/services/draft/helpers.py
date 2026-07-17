# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Shared helper functions for draft state mutations.

These pure functions provide utility operations for the draft-state services, including
truthy flag interpretation, substance lookup, diet matrix resizing, and species index
compaction. They are decoupled from the routing layer to support deterministic scenario
editing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from phids.api.ui_state import DraftState


def is_truthy_flag(value: str | bool) -> bool:
    """Interpret HTML-form boolean payloads as deterministic Python truth values.

    Args:
        value: Raw route payload representing a checkbox or toggle state.

    Returns:
        True when the submitted value represents the affirmative state.

    """
    if isinstance(value, bool):
        return value
    return value.lower() in ("true", "1", "yes", "on")


def find_substance_index(draft: DraftState, substance_id: int) -> int | None:
    """Locate the list index for one substance identifier.

    Args:
        draft: Draft state whose substance registry is searched.
        substance_id: Substance identifier to resolve.

    Returns:
        The list index of the matching substance definition, or ``None`` if absent.

    """
    return next(
        (i for i, substance in enumerate(draft.substance_definitions) if substance.substance_id == substance_id),
        None,
    )


def resize_diet_matrix(draft: DraftState) -> None:
    """Resize the diet matrix to match current herbivore and flora list lengths.

    Args:
        draft: Draft state whose matrix dimensions are compacted or extended.

    """
    n_herbivore = len(draft.herbivore_species)
    n_flora = len(draft.flora_species)

    while len(draft.diet_matrix) < n_herbivore:
        draft.diet_matrix.append([False] * n_flora)
    draft.diet_matrix = draft.diet_matrix[:n_herbivore]
    for row in draft.diet_matrix:
        while len(row) < n_flora:
            row.append(False)
        del row[n_flora:]


def rebuild_species_ids(draft: DraftState) -> None:
    """Reassign sequential species identifiers after species-list mutations.

    Args:
        draft: Draft state whose species collections require index compaction.

    """
    from phids.api.schemas import FloraSpeciesParams, HerbivoreSpeciesParams

    draft.flora_species = [
        fp.model_copy(update={"species_id": i})
        for i, fp in enumerate(draft.flora_species)
        if isinstance(fp, FloraSpeciesParams)
    ]
    draft.herbivore_species = [
        pp.model_copy(update={"species_id": i})
        for i, pp in enumerate(draft.herbivore_species)
        if isinstance(pp, HerbivoreSpeciesParams)
    ]
