# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Draft-state mutation module for species configurations.

Provides pure functions to add or remove flora and herbivore species definitions within the draft.
Species removal automatically compacts dependencies such as the diet matrix, trigger rules,
and initial placements to maintain a consistent state.
"""

from __future__ import annotations

import dataclasses
import logging
from copy import deepcopy
from typing import TYPE_CHECKING

from phids.api.services.draft.helpers import rebuild_species_ids, resize_diet_matrix
from phids.api.ui_state import DraftState, TriggerRule, _remap_condition_references

if TYPE_CHECKING:
    from phids.api.schemas.species import (
        FloraSpeciesParams,
        HerbivoreSpeciesParams,
    )

logger = logging.getLogger(__name__)


def add_flora(draft: DraftState, params: FloraSpeciesParams) -> None:
    """Append one flora species and expand dependent matrix state.

    Args:
        draft: Draft state mutated in place.
        params: Flora species parameter object.

    """
    draft.flora_species.append(params)
    rebuild_species_ids(draft)
    resize_diet_matrix(draft)
    logger.debug(
        "Draft flora added (species_id=%s, total_flora=%d)",
        getattr(params, "species_id", "?"),
        len(draft.flora_species),
    )


def remove_flora(draft: DraftState, species_id: int) -> None:
    """Remove one flora species and compact all dependent references.

    Args:
        draft: Draft state mutated in place.
        species_id: Flora species identifier to remove.

    Raises:
        ValueError: No flora species with the requested identifier exists.

    """
    from phids.api.schemas.species import FloraSpeciesParams

    idx = next(
        (
            i
            for i, fp in enumerate(draft.flora_species)
            if isinstance(fp, FloraSpeciesParams) and fp.species_id == species_id
        ),
        None,
    )
    if idx is None:
        raise ValueError(f"Flora species_id {species_id} not found.")

    del draft.flora_species[idx]
    for row in draft.diet_matrix:
        if idx < len(row):
            del row[idx]

    new_rules: list[TriggerRule] = []
    for rule in draft.trigger_rules:
        if rule.flora_species_id == species_id:
            continue
        new_rule = dataclasses.replace(rule)
        if new_rule.flora_species_id > species_id:
            new_rule.flora_species_id -= 1
        new_rules.append(new_rule)
    draft.trigger_rules = new_rules

    draft.initial_plants = [p for p in draft.initial_plants if p.species_id != species_id]
    rebuild_species_ids(draft)
    resize_diet_matrix(draft)
    logger.debug(
        "Draft flora removed (species_id=%d, total_flora=%d, remaining_trigger_rules=%d)",
        species_id,
        len(draft.flora_species),
        len(draft.trigger_rules),
    )


def add_herbivore(draft: DraftState, params: HerbivoreSpeciesParams) -> None:
    """Append one herbivore species and expand dependent matrix state.

    Args:
        draft: Draft state mutated in place.
        params: Herbivore species parameter object.

    """
    draft.herbivore_species.append(params)
    rebuild_species_ids(draft)
    resize_diet_matrix(draft)
    logger.debug(
        "Draft herbivore added (species_id=%s, total_herbivores=%d)",
        getattr(params, "species_id", "?"),
        len(draft.herbivore_species),
    )


def remove_herbivore(draft: DraftState, species_id: int) -> None:
    """Remove one herbivore species and compact all dependent references.

    Args:
        draft: Draft state mutated in place.
        species_id: Herbivore species identifier to remove.

    Raises:
        ValueError: No herbivore species with the requested identifier exists.

    """
    from phids.api.schemas.species import HerbivoreSpeciesParams

    idx = next(
        (
            i
            for i, pp in enumerate(draft.herbivore_species)
            if isinstance(pp, HerbivoreSpeciesParams) and pp.species_id == species_id
        ),
        None,
    )
    if idx is None:
        raise ValueError(f"Herbivore species_id {species_id} not found.")

    del draft.herbivore_species[idx]
    if idx < len(draft.diet_matrix):
        del draft.diet_matrix[idx]

    new_rules: list[TriggerRule] = []
    for rule in draft.trigger_rules:
        if rule.herbivore_species_id == species_id:
            continue
        new_rule = dataclasses.replace(rule)
        if new_rule.herbivore_species_id > species_id:
            new_rule.herbivore_species_id -= 1
        new_rule.activation_condition = _remap_condition_references(
            deepcopy(new_rule.activation_condition),
            removed_herbivore_id=species_id,
        )
        new_rules.append(new_rule)
    draft.trigger_rules = new_rules

    draft.initial_swarms = [s for s in draft.initial_swarms if s.species_id != species_id]
    rebuild_species_ids(draft)
    resize_diet_matrix(draft)
    logger.debug(
        "Draft herbivore removed (species_id=%d, total_herbivores=%d, remaining_trigger_rules=%d)",
        species_id,
        len(draft.herbivore_species),
        len(draft.trigger_rules),
    )
