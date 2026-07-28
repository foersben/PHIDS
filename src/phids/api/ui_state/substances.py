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

# Substance definition (independent of any trigger coupling)
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class SubstanceDefinition:
    """Named substance with physical/biological properties.

    A substance definition captures how a chemical behaves once produced.
    The trigger matrix separately records *which* (flora, herbivore) pair
    activates synthesis.

    Args:
        substance_id: Layer index in ``GridEnvironment.signal_layers`` or
            ``toxin_layers`` (0 ≤ id < MAX_SUBSTANCE_TYPES).
        name: Human-readable label shown in the UI.
        is_toxin: ``True`` for toxins; ``False`` for airborne signals.
        lethal: Lethal-toxin flag (ignored if ``is_toxin`` is ``False``).
        repellent: Repellent-toxin flag.
        synthesis_duration: Ticks to complete synthesis (production time).
        aftereffect_ticks: Ticks the substance lingers after emission ceases.
        lethality_rate: Population units eliminated per tick (β).
        repellent_walk_ticks: Random-walk duration on repel trigger.
        energy_cost_per_tick: Energy drained from the plant per active tick.
        irreversible: Keep the substance active permanently once activated.
        min_herbivore_population: Minimum swarm size to trigger synthesis.

    """

    substance_id: int
    name: str = "Signal"
    is_toxin: bool = False
    lethal: bool = False
    repellent: bool = False
    synthesis_duration: int = 3
    aftereffect_ticks: int = 0
    lethality_rate: float = 0.0
    repellent_walk_ticks: int = 3
    energy_cost_per_tick: float = 1.0
    irreversible: bool = False
    min_herbivore_population: int = 5

    @property
    def type_label(self) -> str:
        """Human-readable substance type.

        Returns:
            str: One of ``"Signal"``, ``"Lethal Toxin"``,
                ``"Repellent Toxin"``, or ``"Toxin"``.

        """
        if not self.is_toxin:
            return "Signal"
        if self.lethal:
            return "Lethal Toxin"
        if self.repellent:
            return "Repellent Toxin"
        return "Toxin"
