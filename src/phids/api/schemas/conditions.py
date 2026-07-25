# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Activation condition schemas for the compound chemical-defense trigger tree.

This module defines a recursive algebraic type tree composed of five node types,
discriminated by their ``kind`` literal field. The ``ConditionNode`` union is a
PEP 695 ``type`` alias that references both ``AllOfConditionSchema`` and
``AnyOfConditionSchema`` - both of which in turn reference ``ConditionNode`` in
their ``conditions`` fields. This forward-reference cycle requires all five schemas
and the alias to live in the same module, and the two composite schemas must call
``model_rebuild()`` after the alias is defined.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from phids.api.schemas.base import HerbivoreId, StrictBaseModel, SubstanceId


class HerbivorePresenceConditionSchema(StrictBaseModel):
    """Leaf predicate requiring a herbivore species at the owner's cell."""

    kind: Literal["herbivore_presence"] = "herbivore_presence"
    herbivore_species_id: HerbivoreId
    min_herbivore_population: int = Field(
        default=1,
        gt=0,
        description="Minimum co-located herbivore population required for this predicate.",
    )


class SubstanceActiveConditionSchema(StrictBaseModel):
    """Leaf predicate requiring another substance to already be active."""

    kind: Literal["substance_active"] = "substance_active"
    substance_id: SubstanceId = Field(..., description="Active substance required for this predicate.")


class EnvironmentalSignalConditionSchema(StrictBaseModel):
    """Leaf predicate requiring a minimum ambient signal concentration at the owner's cell."""

    kind: Literal["environmental_signal"] = "environmental_signal"
    signal_id: SubstanceId = Field(..., description="Signal layer identifier to read from the environment.")
    min_concentration: float = Field(
        default=0.01,
        ge=0.0,
        description="Minimum concentration required for this predicate.",
    )


class AllOfConditionSchema(StrictBaseModel):
    """Boolean AND over nested activation predicates."""

    kind: Literal["all_of"] = "all_of"
    conditions: list[ConditionNode] = Field(
        ...,
        min_length=1,
        description="All child predicates must evaluate to true.",
    )


class AnyOfConditionSchema(StrictBaseModel):
    """Boolean OR over nested activation predicates."""

    kind: Literal["any_of"] = "any_of"
    conditions: list[ConditionNode] = Field(
        ...,
        min_length=1,
        description="At least one child predicate must evaluate to true.",
    )


type ConditionNode = Annotated[
    HerbivorePresenceConditionSchema
    | SubstanceActiveConditionSchema
    | EnvironmentalSignalConditionSchema
    | AllOfConditionSchema
    | AnyOfConditionSchema,
    Field(discriminator="kind"),
]

# Resolve forward references introduced by the recursive ConditionNode alias.
AllOfConditionSchema.model_rebuild()
AnyOfConditionSchema.model_rebuild()
