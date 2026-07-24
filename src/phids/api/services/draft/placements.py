# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Draft-state mutation module for initial spatial placements.

Provides pure functions to add, remove, and clear initial plant and swarm placements
within the draft scenario grid.
"""

from __future__ import annotations

import logging

from phids.api.ui_state import DraftState, PlacedPlant, PlacedSwarm

logger = logging.getLogger(__name__)


def add_plant_placement(
    draft: DraftState,
    species_id: int,
    x: int,
    y: int,
    energy: float,
) -> None:
    """Append one plant placement to the draft placement ledger.

    Args:
        draft: Draft state mutated in place.
        species_id: Flora species identifier.
        x: The X-axis spatial grid coordinate.
        y: The Y-axis spatial grid coordinate.
        energy: Initial plant energy reserve.

    """
    draft.initial_plants.append(PlacedPlant(species_id=species_id, x=x, y=y, energy=energy))
    logger.debug(
        "Draft plant placement added (species_id=%d, x=%d, y=%d, total_plants=%d)",
        species_id,
        x,
        y,
        len(draft.initial_plants),
    )


def add_swarm_placement(
    draft: DraftState,
    species_id: int,
    x: int,
    y: int,
    population: int,
    energy: float,
) -> None:
    """Append one swarm placement to the draft placement ledger.

    Args:
        draft: Draft state mutated in place.
        species_id: Herbivore species identifier.
        x: The X-axis spatial grid coordinate.
        y: The Y-axis spatial grid coordinate.
        population: Initial swarm population.
        energy: Initial swarm energy reserve.

    """
    draft.initial_swarms.append(
        PlacedSwarm(
            species_id=species_id,
            x=x,
            y=y,
            population=population,
            energy=energy,
        )
    )
    logger.debug(
        "Draft swarm placement added (species_id=%d, x=%d, y=%d, population=%d, total_swarms=%d)",
        species_id,
        x,
        y,
        population,
        len(draft.initial_swarms),
    )


def remove_plant_placement(draft: DraftState, index: int) -> None:
    """Remove one plant placement by list index.

    Args:
        draft: Draft state mutated in place.
        index: Placement index to remove.

    Raises:
        IndexError: The plant placement index is out of range.

    """
    removed = draft.initial_plants[index]
    del draft.initial_plants[index]
    logger.debug(
        "Draft plant placement removed (index=%d, species_id=%d, x=%d, y=%d, total_plants=%d)",
        index,
        removed.species_id,
        removed.x,
        removed.y,
        len(draft.initial_plants),
    )


def remove_swarm_placement(draft: DraftState, index: int) -> None:
    """Remove one swarm placement by list index.

    Args:
        draft: Draft state mutated in place.
        index: Placement index to remove.

    Raises:
        IndexError: The swarm placement index is out of range.

    """
    removed = draft.initial_swarms[index]
    del draft.initial_swarms[index]
    logger.debug(
        "Draft swarm placement removed (index=%d, species_id=%d, x=%d, y=%d, total_swarms=%d)",
        index,
        removed.species_id,
        removed.x,
        removed.y,
        len(draft.initial_swarms),
    )


def clear_placements(draft: DraftState) -> None:
    """Clear all plant and swarm placements from the draft.

    Args:
        draft: Draft state mutated in place.

    """
    cleared_plants = len(draft.initial_plants)
    cleared_swarms = len(draft.initial_swarms)
    draft.initial_plants.clear()
    draft.initial_swarms.clear()
    logger.debug(
        "Draft placements cleared (plants=%d, swarms=%d)",
        cleared_plants,
        cleared_swarms,
    )
