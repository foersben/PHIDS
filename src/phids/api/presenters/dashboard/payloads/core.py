# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Core dashboard payload construction."""

from __future__ import annotations

from typing import Any

from phids.api.presenters.dashboard.mycorrhizal import _build_live_mycorrhizal_links_from_snapshot
from phids.api.presenters.dashboard.payloads.collections import (
    _collect_flora_species,
    _collect_live_plants,
    _collect_live_swarms,
)
from phids.api.presenters.dashboard.shared import _coerce_int


def build_live_dashboard_payload(
    snapshot: dict[str, Any],
    *,
    substance_names: dict[int, str],
) -> dict[str, Any]:
    """Assemble the full JSON payload streamed to the browser canvas over the UI WebSocket.

    This function constructs the authoritative rendering payload consumed by
    ``/ws/ui/stream``.  It collects and serialises data from a pre-extracted snapshot.

    Args:
        snapshot: The extracted thread-safe dictionary snapshot of the loop state.
        substance_names: Mapping from substance identifier to display name.

    Returns:
        A dictionary conforming to the full canvas payload schema.
    """
    _ = substance_names

    plant_energy_layer = snapshot["plant_energy_layer"]
    signal_layers = snapshot["signal_layers"]
    toxin_layers = snapshot["toxin_layers"]

    max_e = float(plant_energy_layer.max()) or 1.0
    signal_overlay = signal_layers.max(axis=0) if signal_layers is not None else None
    toxin_overlay = toxin_layers.max(axis=0) if toxin_layers is not None else None

    flora_names = {species.species_id: species.name for species in snapshot["flora_species"]}
    herbivore_names = {species.species_id: species.name for species in snapshot["herbivore_species"]}

    owned_substances: dict[int, list[dict[str, Any]]] = {}
    for sub in snapshot["substances"]:
        owned_substances.setdefault(sub["owner_plant_id"], []).append(sub)

    plants = _collect_live_plants(snapshot, flora_names, owned_substances)
    swarms = _collect_live_swarms(snapshot, herbivore_names)

    live_flora_species_ids = {
        sid for sid in (_coerce_int(species_id, default=-1) for species_id in plants["species_id"]) if sid >= 0
    }

    all_flora_species, species_energy = _collect_flora_species(
        snapshot["flora_species"],
        snapshot["plant_energy_by_species"],
        snapshot["width"],
        snapshot["height"],
        live_flora_species_ids,
    )

    return {
        "contract_version": 1,
        "tick": snapshot["tick"],
        "grid_width": snapshot["width"],
        "grid_height": snapshot["height"],
        "max_energy": max_e,
        "plant_energy": plant_energy_layer.tolist(),
        "species_energy": species_energy,
        "all_flora_species": all_flora_species,
        "signal_overlay": signal_overlay.tolist() if signal_overlay is not None else [],
        "toxin_overlay": toxin_overlay.tolist() if toxin_overlay is not None else [],
        "max_signal": float(signal_overlay.max()) if signal_overlay is not None else 0.0,
        "max_toxin": float(toxin_overlay.max()) if toxin_overlay is not None else 0.0,
        "plants": plants,
        "mycorrhizal_links": _build_live_mycorrhizal_links_from_snapshot(snapshot),
        "swarms": swarms,
        "terminated": snapshot["terminated"],
        "termination_reason": snapshot["termination_reason"],
        "running": snapshot["running"],
        "paused": snapshot["paused"],
    }
