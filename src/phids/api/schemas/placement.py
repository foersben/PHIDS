# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Initial placement and procedural placement strategy schemas.

``InitialPlantPlacement`` and ``InitialSwarmPlacement`` define manually positioned
entities at simulation start. ``PlacementStrategy`` is a discriminated union of
three procedural seeding algorithms used when ``placement_mode = "procedural"``.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from phids.api.schemas.base import HerbivoreId, SpeciesId, StrictBaseModel


class InitialPlantPlacement(StrictBaseModel):
    """Single plant to place at simulation start."""

    species_id: SpeciesId
    x: int = Field(..., ge=0)
    y: int = Field(..., ge=0)
    energy: float = Field(..., gt=0.0)


class InitialSwarmPlacement(StrictBaseModel):
    """Single swarm to place at simulation start."""

    species_id: HerbivoreId
    x: int = Field(..., ge=0)
    y: int = Field(..., ge=0)
    population: int = Field(..., gt=0)
    energy: float = Field(..., gt=0.0)


class UniformPlacement(StrictBaseModel):
    """Randomly scattered entities."""

    type: Literal["uniform"] = "uniform"
    density: float = Field(..., ge=0.0, le=1.0)


class ClusteredPlacement(StrictBaseModel):
    """Groups of entities clustered around random centroids."""

    type: Literal["clustered"] = "clustered"
    cluster_count: int = Field(..., ge=1)
    variance: float = Field(..., gt=0.0)


class BandedPlacement(StrictBaseModel):
    """Entities placed in dense lines/stripes."""

    type: Literal["banded"] = "banded"
    band_count: int = Field(..., ge=1)
    orientation: Literal["horizontal", "vertical"] = "horizontal"


PlacementStrategy = Annotated[
    UniformPlacement | ClusteredPlacement | BandedPlacement,
    Field(discriminator="type"),
]
