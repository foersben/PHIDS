"""Dashboard presenter for full telemetry/UI payload.

Assembles and serializes the complete live dashboard state (flora/swarm populations,
environmental layers, mycorrhizal root connections) streamed to the UI client.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from phids.api.presenters.dashboard.mycorrhizal import _build_live_mycorrhizal_links
from phids.api.presenters.dashboard.shared import _coerce_int
from phids.api.presenters.dashboard.substances import _is_live_substance_visible

if TYPE_CHECKING:
    from phids.engine.loop import SimulationLoop


def build_live_dashboard_payload(
    loop: SimulationLoop,
    *,
    substance_names: dict[int, str],
) -> dict[str, object]:
    """Assemble the full JSON payload streamed to the browser canvas over the UI WebSocket.

    This function constructs the authoritative rendering payload consumed by
    ``/ws/ui/stream``.  It collects and serialises:

    - Per-species plant energy layers from the double-buffered
      :class:`~phids.engine.core.biotope.GridEnvironment`.
    - All live plant entities as columnar arrays (parallel vectors keyed by field name)
      with positions, energy, mycorrhizal connection counts, and active substance channel
      identifiers.
    - All live swarm entities as columnar arrays with positions, population, energy state,
      repellency, and local toxin exposure.
    - Signal and toxin field overlays (maximum projection across channels).
    - Mycorrhizal network links as computed by :func:`_build_live_mycorrhizal_links`.
    - Full flora species catalogue with per-species extinction flags, enabling the legend
      to enumerate extinct species without repainting their absent energy layers.
    - Simulation lifecycle state (``tick``, ``terminated``, ``running``, ``paused``).

    The distinction between ``species_energy`` (extant species only) and ``all_flora_species``
    (full configured catalogue with ``extinct`` flags) is a deliberate design invariant: the
    canvas renderer must not composite extinct species layers onto the viewport, while the
    operator-facing legend must retain full ecological history for interpretability.

    Args:
        loop: The active :class:`~phids.engine.loop.SimulationLoop` whose ECS world and
            environment layers are serialised.
        substance_names: Mapping from substance identifier to display name.  Injected by the
            caller to eliminate implicit dependency on module-level mutable state.

    Returns:
        A dictionary conforming to the full canvas payload schema, including keys
        ``tick``, ``grid_width``, ``grid_height``, ``max_energy``, ``species_energy``,
        ``all_flora_species``, ``signal_overlay``, ``toxin_overlay``, ``max_signal``,
        ``max_toxin``, ``plants``, ``mycorrhizal_links``, ``swarms``, ``terminated``,
        ``termination_reason``, ``running``, and ``paused``.
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
    for entity in world.query(SwarmComponent):
        swarm = entity.get_component(SwarmComponent)
        toxin_level = float(env.toxin_layers[:, swarm.x, swarm.y].max()) if env.num_toxins > 0 else 0.0
        swarms["x"].append(swarm.x)
        swarms["y"].append(swarm.y)
        swarms["population"].append(swarm.population)
        swarms["species_id"].append(swarm.species_id)
        swarms["name"].append(herbivore_names.get(swarm.species_id, f"Herbivore {swarm.species_id}"))
        swarms["energy"].append(float(swarm.energy))
        swarms["energy_deficit"].append(
            max(
                0.0,
                float(swarm.population * swarm.energy_min - swarm.energy),
            )
        )
        swarms["repelled"].append(swarm.repelled)
        swarms["repelled_ticks_remaining"].append(swarm.repelled_ticks_remaining)
        swarms["toxin_level"].append(toxin_level)
        swarms["intoxicated"].append(toxin_level > 0.0)

    live_flora_species_ids = {
        sid for sid in (_coerce_int(species_id, default=-1) for species_id in plants["species_id"]) if sid >= 0
    }
    all_flora_species: list[dict[str, object]] = []
    species_energy: list[dict[str, object]] = []
    for species in loop.config.flora_species:
        species_id = species.species_id
        is_extinct = species_id not in live_flora_species_ids
        all_flora_species.append(
            {
                "species_id": species_id,
                "name": species.name,
                "extinct": is_extinct,
            }
        )
        if is_extinct:
            continue
        if species_id < env.plant_energy_by_species.shape[0]:
            species_energy.append(
                {
                    "species_id": species_id,
                    "name": species.name,
                    "layer": env.plant_energy_by_species[species_id].tolist(),
                }
            )
        else:
            # Defensive fallback: species_id outside pre-allocated layer bounds.
            species_energy.append(
                {
                    "species_id": species_id,
                    "name": species.name,
                    "layer": [[0.0] * env.height for _ in range(env.width)],
                }
            )

    return {
        "contract_version": 1,
        "tick": loop.tick,
        "grid_width": env.width,
        "grid_height": env.height,
        "max_energy": max_e,
        "plant_energy": env.plant_energy_layer.tolist(),
        "species_energy": species_energy,
        "all_flora_species": all_flora_species,
        "signal_overlay": signal_overlay.tolist() if signal_overlay is not None else [],
        "toxin_overlay": toxin_overlay.tolist() if toxin_overlay is not None else [],
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
