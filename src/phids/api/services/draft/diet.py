# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Draft-state mutation module for diet compatibility matrix.

Provides pure functions to mutate herbivore-flora interaction policies within the
draft matrix representation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from phids.api.services.draft.helpers import is_truthy_flag

if TYPE_CHECKING:
    from phids.api.ui_state import DraftState


def set_diet_compatibility(
    draft: DraftState,
    herbivore_idx: int,
    flora_idx: int,
    compatible: str = "toggle",
) -> bool | None:
    """Toggle or assign one herbivore-flora edibility matrix cell.

    Args:
        draft: Draft state mutated in place.
        herbivore_idx: Herbivore row index.
        flora_idx: The integer column index representing the specific flora species.
        compatible: Requested boolean state or the literal ``"toggle"``.

    Returns:
        The updated boolean cell value, or ``None`` when the indices are out of range.

    """
    if herbivore_idx >= len(draft.diet_matrix) or herbivore_idx < 0:
        return None
    if flora_idx >= len(draft.diet_matrix[herbivore_idx]) or flora_idx < 0:
        return None

    if compatible == "toggle":
        draft.diet_matrix[herbivore_idx][flora_idx] = not draft.diet_matrix[herbivore_idx][flora_idx]
    else:
        draft.diet_matrix[herbivore_idx][flora_idx] = is_truthy_flag(compatible)
    return draft.diet_matrix[herbivore_idx][flora_idx]
