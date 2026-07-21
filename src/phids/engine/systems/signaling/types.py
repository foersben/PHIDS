# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Type definitions for the signaling system."""

from __future__ import annotations

from typing import TypedDict

type ActivationNode = dict[str, object]


class _ActiveToxinProps(TypedDict):
    """Merged toxin properties for one active toxin layer during the current signaling pass."""

    lethal: bool
    lethality_rate: float
    repellent: bool
    repellent_walk_ticks: int
