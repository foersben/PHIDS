# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Shared base model and annotated species-id aliases.

All schema submodules import ``StrictBaseModel``, ``SpeciesId``, ``HerbivoreId``,
and ``SubstanceId`` from here to avoid repetition and ensure consistent Rule-of-16
bound application across the entire ingress boundary.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from phids.shared.constants import (
    MAX_FLORA_SPECIES,
    MAX_HERBIVORE_SPECIES,
    MAX_SUBSTANCE_TYPES,
)


class StrictBaseModel(BaseModel):
    """Base class enabling strict Pydantic v2 validation for all nested fields."""

    model_config = ConfigDict(strict=True)


# ---------------------------------------------------------------------------
# Shared annotated type aliases
# ---------------------------------------------------------------------------

SpeciesId = Annotated[int, Field(ge=0, lt=MAX_FLORA_SPECIES)]
HerbivoreId = Annotated[int, Field(ge=0, lt=MAX_HERBIVORE_SPECIES)]
SubstanceId = Annotated[int, Field(ge=0, lt=MAX_SUBSTANCE_TYPES)]
