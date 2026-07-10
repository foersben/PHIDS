from __future__ import annotations

from typing import TYPE_CHECKING

from phids.api.presenters.dashboard.helpers import _coerce_int
from phids.api.presenters.dashboard.mycorrhizal import _build_live_mycorrhizal_links
from phids.api.presenters.dashboard.substances import _is_live_substance_visible

if TYPE_CHECKING:
    from phids.engine.loop import SimulationLoop


def build_live_dashboard_payload(
    loop: SimulationLoop,
    *,
    substance_names: dict[int, str],
) -> dict[str, object]:
    """Generate the comprehensive dashboard JSON payload for a live simulation.

    This endpoint supplies the primary data stream consumed by the browser's
    three.js / HTMX dashboard. It transforms the flattened SoA (Structure of Arrays)
    Numba grids and ECS component lists into a hierarchical, object-oriented JSON schema
    optimised for frontend rendering and data-binding.

    Args:
        loop: The active :class:`~phids.engine.loop.SimulationLoop` instance.
        substance_names: A mapping from numeric substance IDs to human-readable names.

    Returns:
        A structured dictionary representing the global simulation state, including
        environmental flow fields, topological entity lists, chemical concentrations,
        and current tick status.
    """
    from phids.engine.components.plant import PlantComponent
    from phids.engine.components.substances import SubstanceComponent
    from phids.engine.components.swarm import SwarmComponent

    _ = substance_names
    env = loop.env
    world = loop.world
    max_e = float(env.plant_energy_layer.max()) or 1.0
    signal_overlay = env.signal_layers.max(axis=0) if env.num_signals > 0 else None
    toxin_overlay = env.toxin_layers.max(axis=0) if env.num_toxins > 0 else None

    flora_names = {species.species_id: species.name for species in loop.config.flora_species}
    herbivore_names = {species.species_id: species.name for species in loop.config.herbivore_species}

    owned_substances: dict[int, list[SubstanceComponent]] = {}
    for entity in world.query(SubstanceComponent):
        substance = entity.get_component(SubstanceComponent)
        owned_substances.setdefault(substance.owner_plant_id, []).append(substance)

    plants: dict[str, list[object]] = {
        "entity_id": [],
        "species_id": [],
        "name": [],
        "x": [],
        "y": [],
        "energy": [],
        "root_link_count": [],
        "active_signal_ids": [],
        "active_toxin_ids": [],
    }
    for entity in world.query(PlantComponent):
        plant = entity.get_component(PlantComponent)
        plant_substances = owned_substances.get(plant.entity_id, [])
        local_signal_ids = {
            signal_id
            for signal_id in range(env.num_signals)
            if float(env.signal_layers[signal_id, plant.x, plant.y]) > 0.0
        }
        local_toxin_ids = {
            toxin_id for toxin_id in range(env.num_toxins) if float(env.toxin_layers[toxin_id, plant.x, plant.y]) > 0.0
        }
        visible_signal_ids = sorted(
            local_signal_ids
            | {
                substance.substance_id
                for substance in plant_substances
                if not substance.is_toxin and _is_live_substance_visible(substance)
            }
        )
        visible_toxin_ids = sorted(
            local_toxin_ids
            | {
                substance.substance_id
                for substance in plant_substances
                if substance.is_toxin and _is_live_substance_visible(substance)
            }
        )
        plants["entity_id"].append(plant.entity_id)
        plants["species_id"].append(plant.species_id)
        plants["name"].append(flora_names.get(plant.species_id, f"Flora {plant.species_id}"))
        plants["x"].append(plant.x)
        plants["y"].append(plant.y)
        plants["energy"].append(float(plant.energy))
        plants["root_link_count"].append(len(plant.mycorrhizal_connections))
        plants["active_signal_ids"].append(visible_signal_ids)
        plants["active_toxin_ids"].append(visible_toxin_ids)

    swarms: dict[str, list[object]] = {
        "entity_id": [],
        "species_id": [],
        "name": [],
        "x": [],
        "y": [],
        "population": [],
        "energy": [],
        "repelled": [],
        "local_toxin_exposure": [],
    }
    for entity in world.query(SwarmComponent):
        swarm = entity.get_component(SwarmComponent)
        swarms["entity_id"].append(swarm.entity_id)
        swarms["species_id"].append(swarm.species_id)
        swarms["name"].append(herbivore_names.get(swarm.species_id, f"Herbivore {swarm.species_id}"))
        swarms["x"].append(swarm.x)
        swarms["y"].append(swarm.y)
        swarms["population"].append(swarm.population)
        swarms["energy"].append(float(swarm.energy))
        swarms["repelled"].append(swarm.repelled)
        swarms["local_toxin_exposure"].append(
            float(env.toxin_layers[:, swarm.x, swarm.y].max()) if env.num_toxins > 0 else 0.0
        )

    live_species_ids = set(
        sid for sid in (_coerce_int(species_id, default=-1) for species_id in plants["species_id"]) if sid >= 0
    )

    return {
        "tick": loop.tick,
        "grid_width": env.width,
        "grid_height": env.height,
        "max_energy": max_e,
        "species_energy": [
            {
                "species_id": species_id,
                "layer": env.plant_energy_layer[species_id].tolist(),
            }
            for species_id in sorted(live_species_ids)
        ],
        "all_flora_species": [
            {
                "species_id": getattr(species, "species_id", -1),
                "name": getattr(species, "name", ""),
                "color": getattr(species, "color", "#000000"),
                "extinct": getattr(species, "species_id", -1) not in live_species_ids,
            }
            for species in loop.config.flora_species
        ],
        "signal_overlay": signal_overlay.tolist() if signal_overlay is not None else None,
        "toxin_overlay": toxin_overlay.tolist() if toxin_overlay is not None else None,
        "max_signal": float(signal_overlay.max()) if signal_overlay is not None else 0.0,
        "max_toxin": float(toxin_overlay.max()) if toxin_overlay is not None else 0.0,
        "plants": plants,
        "mycorrhizal_links": _build_live_mycorrhizal_links(loop),
        "swarms": swarms,
        "terminated": loop.terminated,
        "termination_reason": loop.termination_reason,
        "running": loop.running,
        "paused": loop.paused,
    }
