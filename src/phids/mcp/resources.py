# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Declarative context resources exposed via FastMCP for PHIDS.

Provides passive read feeds allowing AI agents to inspect configuration drafts
and live simulation status without consuming tool invocation budgets.
"""

from __future__ import annotations

import json

from phids.mcp.app import mcp
from phids.mcp.helpers import _draft_to_json, get_active_sim_loop, get_current_draft


@mcp.resource("phids://config/draft.json")
def active_draft_resource() -> str:
    """Provide the full, untruncated JSON layout of the active configuration draft.

    Agents can read this resource directly to digest species mappings, substance
    definitions, trigger-rule trees, diet matrices, and termination thresholds
    without spending a tool-call budget on ``runtime_snapshot``.

    Returns:
        str: Indented JSON string of the current DraftState.
    """
    return _draft_to_json(get_current_draft())


@mcp.resource("phids://simulation/live.json")
def live_simulation_resource() -> str:
    """Provide real-time JSON snapshot of the active running SimulationLoop.

    Returns live tick count, status flags, active ECS entity counts, total plant
    energy, total herbivore population, and mycorrhizal connection stats.

    Returns:
        str: Indented JSON string of the live simulation loop status.
    """
    loop = get_active_sim_loop()
    if loop is None:
        return json.dumps({"status": "idle", "message": "No active simulation loop currently loaded"})

    from phids.engine.components.plant import PlantComponent
    from phids.engine.components.swarm import SwarmComponent

    plants = [e.get_component(PlantComponent) for e in loop.world.query(PlantComponent)]
    swarms = [e.get_component(SwarmComponent) for e in loop.world.query(SwarmComponent)]

    total_links = sum(len(p.mycorrhizal_connections) for p in plants) // 2

    return json.dumps(
        {
            "status": "running" if loop.running and not loop.paused else ("paused" if loop.paused else "ready"),
            "tick": loop.tick,
            "max_ticks": loop.config.max_ticks,
            "terminated": loop.terminated,
            "termination_reason": loop.termination_reason,
            "active_plants": len(plants),
            "active_swarms": len(swarms),
            "total_flora_energy": round(sum(p.energy for p in plants), 2),
            "total_herbivore_population": sum(s.population for s in swarms),
            "mycorrhizal_links_count": total_links,
        },
        indent=2,
    )
