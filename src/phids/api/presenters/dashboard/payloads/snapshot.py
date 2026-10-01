# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Extraction of thread-safe UI snapshots from the simulation loop."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from phids.api.presenters.dashboard.payloads.metrics import _compute_plant_metrics

if TYPE_CHECKING:
    from phids.engine.core.ecs import ECSWorld
    from phids.engine.loop import SimulationLoop


def _extract_plants(world: ECSWorld) -> list[dict[str, Any]]:
    """Extract plant component data into a list of dictionaries for UI serialisation.

    Args:
        world: The current ECSWorld instance containing plant entities.

    Returns:
        A list of dictionaries containing properties of each plant entity.
    """
    from phids.engine.components.plant import PlantComponent

    plants = []
    for entity in world.query(PlantComponent):
        p = entity.get_component(PlantComponent)
        metrics = _compute_plant_metrics(p)

        plants.append(
            {
                "entity_id": p.entity_id,
                "species_id": p.species_id,
                "x": p.x,
                "y": p.y,
                "energy": p.energy,
                "max_energy": p.max_energy,
                "structural_mass": metrics.structural_mass,
                "max_structural_mass": metrics.max_structural_mass,
                "fragility_pct": metrics.fragility_pct,
                "incidental_risk_level": metrics.incidental_risk_level,
                "root_link_count": len(p.mycorrhizal_connections),
                "mycorrhizal_connections": set(p.mycorrhizal_connections),
            }
        )
    return plants


def _extract_swarms(world: ECSWorld) -> list[dict[str, Any]]:
    """Extract swarm component data into a list of dictionaries for UI serialisation.

    Args:
        world: The current ECSWorld instance containing swarm entities.

    Returns:
        A list of dictionaries containing properties of each swarm entity.
    """
    from phids.engine.components.swarm import SwarmComponent

    swarms = []
    for entity in world.query(SwarmComponent):
        s = entity.get_component(SwarmComponent)
        swarms.append(
            {
                "species_id": s.species_id,
                "x": s.x,
                "y": s.y,
                "population": s.population,
                "energy": s.energy,
                "energy_min": s.energy_min,
                "repelled": s.repelled,
                "repelled_ticks_remaining": s.repelled_ticks_remaining,
            }
        )
    return swarms


def _extract_substances(world: ECSWorld) -> list[dict[str, Any]]:
    """Extract substance component data into a list of dictionaries for UI serialisation.

    Args:
        world: The current ECSWorld instance containing substance entities.

    Returns:
        A list of dictionaries containing properties of each substance entity.
    """
    from phids.engine.components.substances import SubstanceComponent

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
    return substances


def extract_ui_snapshot(loop: SimulationLoop) -> dict[str, Any]:
    """Extract a fast, thread-safe shallow copy of UI-required state.

    This function runs synchronously while holding the simulation lock. It returns a
    dictionary containing primitive values, copied NumPy arrays, and lightweight dicts
    representing the components needed for UI streaming.
    """
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

    snapshot["plants"] = _extract_plants(world)
    snapshot["swarms"] = _extract_swarms(world)
    snapshot["substances"] = _extract_substances(world)

    return snapshot
