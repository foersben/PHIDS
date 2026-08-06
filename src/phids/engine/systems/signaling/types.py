# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Type definitions for the signaling system."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from phids.api.schemas.triggers import TriggerConditionSchema

type ActivationNode = dict[str, object]


@dataclass(slots=True)
class CompiledTrigger:
    """Pre-evaluated trigger rule caching its JSON-serialised condition structure."""

    schema: TriggerConditionSchema
    activation_condition_dump: dict[str, object] | None


class _ActiveToxinProps(TypedDict):
    """Merged toxin properties for one active toxin layer during the current signaling pass."""

    lethal: bool
    lethality_rate: float
    repellent: bool
    repellent_walk_ticks: int
