# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Plants live cell details extraction."""

from __future__ import annotations

from typing import TYPE_CHECKING

from phids.api.presenters.dashboard.cell_details.live.mycorrhiza import _get_live_mycorrhizal_neighbours
from phids.api.presenters.dashboard.shared import (
    _coerce_int,
    calculate_structural_fragility_and_risk,
)
from phids.api.presenters.dashboard.substances import (
    _fallback_live_substance_payload,
    _is_live_substance_visible,
    _serialize_live_substance,
)

if TYPE_CHECKING:
    from phids.engine.components.plant import PlantComponent
    from phids.engine.components.substances import SubstanceComponent
    from phids.engine.core.biotope import GridEnvironment


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
    visible_substances.sort(
        key=lambda payload: (
            payload.get("kind") == "toxin",
            _coerce_int(payload.get("substance_id", -1), default=-1),
        )
    )
    return visible_substances


def _build_live_plant_payload(
    plant: PlantComponent,
    flora_names: dict[int, str],
    plant_lookup: dict[int, PlantComponent],
    owned_substances: dict[int, list[SubstanceComponent]],
    env: GridEnvironment,
    herbivore_names: dict[int, str],
    substance_names: dict[int, str],
) -> dict[str, object]:
    """Helper to construct the detailed live plant presentation structure.

    This function builds the presentation structure for a live plant, including
    its energy state, dual-proxy structural mass, fragility level, mycorrhizal connections,
    and active substances.

    Args:
        plant: The plant component.
        flora_names: The flora names.
        plant_lookup: The plant lookup.
        owned_substances: The owned substances.
        env: The grid environment.
        herbivore_names: The herbivore names.
        substance_names: The substance names.

    Returns:
        The presentation structure.
    """
    visible_substances = _get_live_substances(plant, owned_substances, env, herbivore_names, substance_names)
    mycorrhizal_neighbours = _get_live_mycorrhizal_neighbours(plant, plant_lookup, flora_names)

    struct_mass = plant.structural_mass
    max_struct = plant.max_structural_mass
    struct_ratio = struct_mass / max_struct if max_struct > 0.0 else 0.0
    struct_upkeep = plant.survival_threshold * 0.5 * min(1.0, struct_ratio) if max_struct > 0.0 else 0.0
    _fragility, fragility_pct, risk_level = calculate_structural_fragility_and_risk(struct_mass, max_struct)

    return {
        "entity_id": plant.entity_id,
        "species_id": plant.species_id,
        "name": flora_names.get(plant.species_id, f"Flora {plant.species_id}"),
        "energy": plant.energy,
        "max_energy": plant.max_energy,
        "base_energy": plant.base_energy,
        "growth_rate": plant.growth_rate,
        "energy_ratio": (plant.energy / plant.max_energy if plant.max_energy > 0.0 else 0.0),
        "energy_label": (
            f"{plant.energy:.1f} / {plant.max_energy:.1f} ({100.0 * plant.energy / plant.max_energy:.1f}%)"
            if plant.max_energy > 0.0
            else "N/A"
        ),
        "structural_mass": struct_mass,
        "max_structural_mass": max_struct,
        "structural_mass_pct": min(100.0, struct_ratio * 100.0),
        "growth_rate_structural": plant.growth_rate_structural,
        "structural_upkeep_fee": struct_upkeep,
        "fragility_pct": fragility_pct,
        "incidental_risk_level": risk_level,
        "is_woody_mature": max_struct > 0.0 and struct_mass >= max_struct,
        "camouflage": plant.camouflage,
        "camouflage_factor": plant.camouflage_factor,
        "mycorrhizal_connections": len(plant.mycorrhizal_connections),
        "mycorrhizal_neighbours": mycorrhizal_neighbours,
        "active_substances": visible_substances,
    }
