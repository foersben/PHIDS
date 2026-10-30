# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Live substance presenters.

Helper functions for extracting environmental and plant-owned substances.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from phids.api.presenters.dashboard.shared import _coerce_int
from phids.api.presenters.dashboard.substances import (
    _fallback_live_substance_payload,
    _is_live_substance_visible,
    _serialize_live_substance,
)

if TYPE_CHECKING:
    from phids.engine.components.plant import PlantComponent
    from phids.engine.components.substances import SubstanceComponent
    from phids.engine.core.biotope import GridEnvironment


def _add_environmental_signals(
    env: GridEnvironment,
    plant: PlantComponent,
    visible_keys: set[tuple[int, bool]],
    visible_substances: list[dict[str, object]],
    substance_names: dict[int, str],
) -> None:
    """Helper to add environmental signals to visible substances.

    Args:
        env: The grid environment.
        plant: The plant component.
        visible_keys: A set of visible substance keys.
        visible_substances: A list of visible substance payloads.
        substance_names: A dictionary mapping substance IDs to names.
    """
    for signal_id in range(env.num_signals):
        if float(env.signal_layers[signal_id, plant.x, plant.y]) <= 0.0:
            continue
        substance_key = (signal_id, False)
        if substance_key in visible_keys:
            continue
        visible_substances.append(
            _fallback_live_substance_payload(signal_id, is_toxin=False, substance_names=substance_names)
        )
        visible_keys.add(substance_key)


def _add_environmental_toxins(
    env: GridEnvironment,
    plant: PlantComponent,
    visible_keys: set[tuple[int, bool]],
    visible_substances: list[dict[str, object]],
    substance_names: dict[int, str],
) -> None:
    """Helper to add environmental toxins to visible substances.

    Args:
        env: The grid environment.
        plant: The plant component.
        visible_keys: A set of visible substance keys.
        visible_substances: A list of visible substance payloads.
        substance_names: A dictionary mapping substance IDs to names.
    """
    for toxin_id in range(env.num_toxins):
        if float(env.toxin_layers[toxin_id, plant.x, plant.y]) <= 0.0:
            continue
        substance_key = (toxin_id, True)
        if substance_key in visible_keys:
            continue
        visible_substances.append(
            _fallback_live_substance_payload(toxin_id, is_toxin=True, substance_names=substance_names)
        )
        visible_keys.add(substance_key)


def _get_live_substances(
    plant: PlantComponent,
    owned_substances: dict[int, list[SubstanceComponent]],
    env: GridEnvironment,
    herbivore_names: dict[int, str],
    substance_names: dict[int, str],
) -> list[dict[str, object]]:
    """Helper to collect and serialize visible active substances on a plant.

    This function gathers and serializes all active substances located on a plant, including
    both those directly owned by the plant entity and those diffused into the environment at
    the plant's location. It filters out invisible substances (e.g., toxins below threshold)
    and ensures consistent payload formatting for the UI.

    Args:
        plant: The plant component.
        owned_substances: The owned substances.
        env: The grid environment.
        herbivore_names: The herbivore names.
        substance_names: The substance names.

    Returns:
        The list of visible active substances.
    """
    plant_substances = sorted(
        (substance for substance in owned_substances.get(plant.entity_id, []) if _is_live_substance_visible(substance)),
        key=lambda substance: (substance.is_toxin, substance.substance_id),
    )
    visible_substances = [
        _serialize_live_substance(
            substance,
            herbivore_names=herbivore_names,
            substance_names=substance_names,
        )
        for substance in plant_substances
    ]
    visible_keys = {
        (
            _coerce_int(payload.get("substance_id", -1), default=-1),
            payload.get("kind") == "toxin",
        )
        for payload in visible_substances
    }
    _add_environmental_signals(env, plant, visible_keys, visible_substances, substance_names)
    _add_environmental_toxins(env, plant, visible_keys, visible_substances, substance_names)

    visible_substances.sort(
        key=lambda payload: (
            payload.get("kind") == "toxin",
            _coerce_int(payload.get("substance_id", -1), default=-1),
        )
    )
    return visible_substances
