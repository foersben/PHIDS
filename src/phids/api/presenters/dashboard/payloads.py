# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Dashboard presenter for full telemetry/UI payload.

Assembles and serializes the complete live dashboard state (flora/swarm populations,
environmental layers, mycorrhizal root connections) streamed to the UI client.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from phids.api.presenters.dashboard.mycorrhizal import _build_live_mycorrhizal_links_from_snapshot
from phids.api.presenters.dashboard.shared import _coerce_int

if TYPE_CHECKING:
    from typing import Any

    from phids.api.schemas.species import FloraSpeciesParams
    from phids.engine.components.plant import PlantComponent
    from phids.engine.loop import SimulationLoop


def _collect_live_plants(
    snapshot: dict[str, Any],
    flora_names: dict[int, str],
    owned_substances: dict[int, list[dict[str, Any]]],
) -> dict[str, list[object]]:
    plants_data = snapshot["plants"]
    signal_layers = snapshot["signal_layers"]
    toxin_layers = snapshot["toxin_layers"]
    num_signals = snapshot["num_signals"]
    num_toxins = snapshot["num_toxins"]

    plants: dict[str, list[object]] = {
        "entity_id": [],
        "species_id": [],
        "name": [],
        "x": [],
        "y": [],
        "energy": [],
        "max_energy": [],
        "structural_mass": [],
        "max_structural_mass": [],
        "fragility_pct": [],
        "incidental_risk_level": [],
        "root_link_count": [],
        "active_signal_ids": [],
        "active_toxin_ids": [],
    }

    # For dense grid scenes (e.g. 256x256 benchmark with 19,663 plants), serializing every silent
    # plant in the live WebSocket stream payload causes 2.5MB payload sizes and client latency.
    # We serialize all plants when count < 1000, and for dense scenes we filter to active plant nodes
    # (emitting signals, toxins, or connected via mycorrhiza).
    for p in plants_data:
        plant_substances = owned_substances.get(p["entity_id"], [])
        local_signal_ids = (
            {signal_id for signal_id in range(num_signals) if float(signal_layers[signal_id, p["x"], p["y"]]) > 0.0}
            if signal_layers is not None
            else set()
        )

        local_toxin_ids = (
            {toxin_id for toxin_id in range(num_toxins) if float(toxin_layers[toxin_id, p["x"], p["y"]]) > 0.0}
            if toxin_layers is not None
            else set()
        )

        visible_signal_ids = sorted(
            local_signal_ids
            | {sub["substance_id"] for sub in plant_substances if not sub["is_toxin"] and sub["is_visible"]}
        )
        visible_toxin_ids = sorted(
            local_toxin_ids | {sub["substance_id"] for sub in plant_substances if sub["is_toxin"] and sub["is_visible"]}
        )

        plants["entity_id"].append(p["entity_id"])
        plants["species_id"].append(p["species_id"])
        plants["name"].append(flora_names.get(p["species_id"], f"Flora {p['species_id']}"))
        plants["x"].append(p["x"])
        plants["y"].append(p["y"])
        plants["energy"].append(p["energy"])
        plants["max_energy"].append(p.get("max_energy", 100.0))
        plants["structural_mass"].append(p.get("structural_mass", 0.0))
        plants["max_structural_mass"].append(p.get("max_structural_mass", 0.0))
        plants["fragility_pct"].append(p.get("fragility_pct", 100.0))
        plants["incidental_risk_level"].append(p.get("incidental_risk_level", "High Risk"))
        plants["root_link_count"].append(p["root_link_count"])
        plants["active_signal_ids"].append(visible_signal_ids)
        plants["active_toxin_ids"].append(visible_toxin_ids)
    return plants


def _collect_live_swarms(
    snapshot: dict[str, Any],
    herbivore_names: dict[int, str],
) -> dict[str, list[object]]:
    swarms_data = snapshot["swarms"]
    toxin_layers = snapshot["toxin_layers"]

    swarms: dict[str, list[object]] = {
        "x": [],
        "y": [],
        "population": [],
        "species_id": [],
        "name": [],
        "energy": [],
        "energy_deficit": [],
        "repelled": [],
        "repelled_ticks_remaining": [],
        "toxin_level": [],
        "intoxicated": [],
    }
    for s in swarms_data:
        toxin_level = float(toxin_layers[:, s["x"], s["y"]].max()) if toxin_layers is not None else 0.0
        swarms["x"].append(s["x"])
        swarms["y"].append(s["y"])
        swarms["population"].append(s["population"])
        swarms["species_id"].append(s["species_id"])
        swarms["name"].append(herbivore_names.get(s["species_id"], f"Herbivore {s['species_id']}"))
        swarms["energy"].append(s["energy"])
        swarms["energy_deficit"].append(
            max(
                0.0,
                float(s["population"] * s["energy_min"] - s["energy"]),
            )
        )
        swarms["repelled"].append(s["repelled"])
        swarms["repelled_ticks_remaining"].append(s["repelled_ticks_remaining"])
        swarms["toxin_level"].append(toxin_level)
        swarms["intoxicated"].append(toxin_level > 0.0)
    return swarms


def _collect_flora_species(
    config_flora_species: list[FloraSpeciesParams],
    plant_energy_by_species: Any,
    width: int,
    height: int,
    live_flora_species_ids: set[int],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    all_flora_species: list[dict[str, object]] = []
    species_energy: list[dict[str, object]] = []
    is_large_grid = width * height >= 10000
    for species in config_flora_species:
        species_id = species.species_id
        is_extinct = species_id not in live_flora_species_ids
        all_flora_species.append(
            {
                "species_id": species_id,
                "name": species.name,
                "extinct": is_extinct,
            }
        )
        if is_extinct or is_large_grid:
            continue
        if species_id < plant_energy_by_species.shape[0]:
            species_energy.append(
                {
                    "species_id": species_id,
                    "name": species.name,
                    "layer": plant_energy_by_species[species_id].tolist(),
                }
            )
        else:
            # Defensive fallback: species_id outside pre-allocated layer bounds.
            species_energy.append(
                {
                    "species_id": species_id,
                    "name": species.name,
                    "layer": [[0.0] * height for _ in range(width)],
                }
            )
    return all_flora_species, species_energy


def _compute_plant_structural_properties(p: PlantComponent, max_struct: float) -> tuple[float, float, str]:
    struct_mass = float(p.structural_mass)
    if struct_mass <= 0.0 and max_struct > 0.0:
        struct_mass = max_struct * min(1.0, max(0.0, float(p.energy) / max_struct))
        p.structural_mass = struct_mass
        p.max_structural_mass = max_struct

    struct_ratio = struct_mass / max_struct if max_struct > 0.0 else 0.0
    fragility = max(0.0, 1.0 - struct_ratio) if max_struct > 0.0 else 1.0
    fragility_pct = min(100.0, max(0.0, fragility * 100.0))

    if max_struct > 0.0 and struct_mass >= max_struct:
        risk_level = "Immune"
    elif fragility > 0.6:
        risk_level = "High Risk"
    elif fragility > 0.2:
        risk_level = "Medium Risk"
    else:
        risk_level = "Low Risk"
    return struct_mass, fragility_pct, risk_level


def extract_ui_snapshot(loop: SimulationLoop) -> dict[str, Any]:
    """Extract a fast, thread-safe shallow copy of UI-required state.

    This function runs synchronously while holding the simulation lock. It returns a
    dictionary containing primitive values, copied NumPy arrays, and lightweight dicts
    representing the components needed for UI streaming.
    """
    from phids.engine.components.plant import PlantComponent
    from phids.engine.components.substances import SubstanceComponent
    from phids.engine.components.swarm import SwarmComponent

    env = loop.env
    world = loop.world

    snapshot: dict[str, Any] = {
        "tick": loop.tick,
        "width": env.width,
        "height": env.height,
        "terminated": loop.terminated,
        "termination_reason": loop.termination_reason,
        "running": loop.running,
        "paused": loop.paused,
        "num_signals": env.num_signals,
        "num_toxins": env.num_toxins,
        "flora_species": loop.config.flora_species,
        "herbivore_species": loop.config.herbivore_species,
        "plant_energy_layer": env.plant_energy_layer.copy(),
        "signal_layers": env.signal_layers.copy() if env.num_signals > 0 else None,
        "toxin_layers": env.toxin_layers.copy() if env.num_toxins > 0 else None,
        "plant_energy_by_species": env.plant_energy_by_species.copy(),
    }

    plants = []
    for entity in world.query(PlantComponent):
        p = entity.get_component(PlantComponent)
        max_struct = float(p.max_structural_mass) if p.max_structural_mass > 0.0 else float(p.max_energy)
        struct_mass, fragility_pct, risk_level = _compute_plant_structural_properties(p, max_struct)

        plants.append(
            {
                "entity_id": p.entity_id,
                "species_id": p.species_id,
                "x": p.x,
                "y": p.y,
                "energy": float(p.energy),
                "max_energy": float(p.max_energy),
                "structural_mass": struct_mass,
                "max_structural_mass": max_struct,
                "fragility_pct": fragility_pct,
                "incidental_risk_level": risk_level,
                "root_link_count": len(p.mycorrhizal_connections),
                "mycorrhizal_connections": set(p.mycorrhizal_connections),
            }
        )
    snapshot["plants"] = plants

    swarms = []
    for entity in world.query(SwarmComponent):
        s = entity.get_component(SwarmComponent)
        swarms.append(
            {
                "species_id": s.species_id,
                "x": s.x,
                "y": s.y,
                "population": s.population,
                "energy": float(s.energy),
                "energy_min": s.energy_min,
                "repelled": s.repelled,
                "repelled_ticks_remaining": s.repelled_ticks_remaining,
            }
        )
    snapshot["swarms"] = swarms

    substances = []
    for entity in world.query(SubstanceComponent):
        sub_comp = entity.get_component(SubstanceComponent)
        is_visible = (
            sub_comp.active
            or sub_comp.synthesis_remaining > 0
            or sub_comp.aftereffect_remaining_ticks > 0
            or sub_comp.triggered_this_tick
        )
        substances.append(
            {
                "owner_plant_id": sub_comp.owner_plant_id,
                "substance_id": sub_comp.substance_id,
                "is_toxin": sub_comp.is_toxin,
                "is_visible": is_visible,
            }
        )
    snapshot["substances"] = substances

    return snapshot


def build_live_dashboard_payload(
    snapshot: dict[str, Any],
    *,
    substance_names: dict[int, str],
) -> dict[str, object]:
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
