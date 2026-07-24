# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Placement definitions for the draft scenario UI."""

from __future__ import annotations

import dataclasses


@dataclasses.dataclass
class PlacedPlant:
    """A plant placed on the grid before the simulation starts.

    Args:
        species_id: Flora species index.
        x: The X-axis spatial grid coordinate.
        y: The Y-axis spatial grid coordinate.
        energy: Initial energy reserve.

    """

    species_id: int
    x: int
    y: int
    energy: float


@dataclasses.dataclass
class PlacedSwarm:
    """A herbivore swarm placed on the grid before the simulation starts.

    Args:
        species_id: Herbivore species index.
        x: The X-axis spatial grid coordinate.
        y: The Y-axis spatial grid coordinate.
        population: Initial swarm population.
        energy: Initial energy reserve.

    """

    species_id: int
    x: int
    y: int
    population: int
    energy: float
