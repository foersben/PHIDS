# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Server-side draft state model for the HTMX scenario-builder UI in PHIDS.

This module implements :class:`DraftState`, a server-side configuration accumulator for the PHIDS
scenario-builder UI. ``DraftState`` stores all operator choices made through the web interface,
including species definitions, substance properties, trigger rules, diet-matrix entries, and
initial placements, before committing them to the simulation engine via
``POST /api/scenario/load-draft``. Imperative mutation procedures are executed by
the ``phids.api.services.draft`` functions against ``DraftState`` instances, while
this module retains data structures, condition-tree utilities, schema export logic, and singleton
draft lifecycle management. No concurrency-safe locking is applied, as the server is designed for
single-operator workbench usage.
"""

from __future__ import annotations

import dataclasses
import logging

logger = logging.getLogger(__name__)

# Placement dataclasses
# ---------------------------------------------------------------------------


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
