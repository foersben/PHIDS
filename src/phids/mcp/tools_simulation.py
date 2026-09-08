# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Simulation state and batch execution inspection tools for FastMCP."""

from __future__ import annotations

import json
from typing import Any

from phids.mcp.app import mcp
from phids.mcp.helpers import get_active_sim_loop, get_current_draft, get_project_root


@mcp.tool()
def query_batch_jobs() -> dict[str, Any]:
    """Return a summary of active and completed batch jobs from the draft state.

    Provides visibility into long-running exploration tasks or evolutionary
    exploration results.

    Returns:
        dict[str, Any]: Dictionary mapping job IDs to their state representations.
    """
    draft = get_current_draft()
    return {
        job_id: {
            "status": state.status,
            "completed_runs": state.completed,
            "total_runs": state.total,
            "finished_at": state.finished_at,
        }
        for job_id, state in draft.active_batch_jobs.items()
    }


@mcp.tool()
def runtime_snapshot() -> dict[str, Any]:
    """Return a compact performance-and-counts summary of the active draft state.

    Useful as a lightweight sanity check before heavier resource reads or batch
    operations. All counts reflect the in-memory singleton draft; no simulation
    loop is touched.

    Returns:
        dict[str, Any]: Compact read-only summary including scenario metadata,
            grid dimensions, entity counts, and active termination thresholds
            (Z-codes).
    """
    draft = get_current_draft()
    return {
        "scenario_name": draft.scenario_name,
        "dimensions": f"{draft.grid_width}x{draft.grid_height}",
        "grid_width": draft.grid_width,
        "grid_height": draft.grid_height,
        "max_ticks": draft.max_ticks,
        "tick_rate_hz": draft.tick_rate_hz,
        "placement_mode": draft.placement_mode,
        "mycorrhizal_inter_species": draft.mycorrhizal_inter_species,
        "flora_species_count": len(draft.flora_species),
        "herbivore_species_count": len(draft.herbivore_species),
        "substance_definitions_count": len(draft.substance_definitions),
        "trigger_rules_count": len(draft.trigger_rules),
        "initial_plants_count": len(draft.initial_plants),
        "initial_swarms_count": len(draft.initial_swarms),
        "active_batch_jobs_count": len(draft.active_batch_jobs),
        "termination_thresholds": {
            "z2_flora_species_extinction": draft.z2_flora_species_extinction,
            "z4_herbivore_species_extinction": draft.z4_herbivore_species_extinction,
            "z6_max_total_flora_energy": draft.z6_max_total_flora_energy,
            "z7_max_total_herbivore_population": draft.z7_max_total_herbivore_population,
        },
    }


@mcp.tool()
def inspect_live_simulation() -> dict[str, Any]:
    """Return compact operational summary of the active running simulation loop.

    Useful for monitoring tick advancement, modulo-stride gates (is_medium_tick,
    is_slow_tick), and mycorrhizal root network connectivity statistics.

    Returns:
        dict[str, Any]: Compact operational breakdown of the live running loop.
    """
    loop = get_active_sim_loop()
    if loop is None:
        return {"status": "inactive", "message": "No live simulation loop currently loaded"}

    from phids.engine.components.plant import PlantComponent
    from phids.engine.components.swarm import SwarmComponent

    plants = [e.get_component(PlantComponent) for e in loop.world.query(PlantComponent)]
    swarms = [e.get_component(SwarmComponent) for e in loop.world.query(SwarmComponent)]

    connected_plants = sum(1 for p in plants if p.mycorrhizal_connections)
    total_links = sum(len(p.mycorrhizal_connections) for p in plants) // 2

    return {
        "status": "active",
        "tick": loop.tick,
        "is_medium_tick": loop.tick % 24 == 0,
        "is_slow_tick": loop.tick % 168 == 0,
        "running": loop.running,
        "paused": loop.paused,
        "terminated": loop.terminated,
        "termination_reason": loop.termination_reason,
        "plant_count": len(plants),
        "swarm_count": len(swarms),
        "total_flora_energy": round(sum(p.energy for p in plants), 2),
        "total_herbivore_population": sum(s.population for s in swarms),
        "mycorrhizal_total_links": total_links,
        "mycorrhizal_connected_plants": connected_plants,
    }


@mcp.tool()
def read_batch_summary(job_id: str) -> dict[str, Any]:
    """Read the aggregated metrics inside a batch job's summary JSON file.

    Allows agents to digest batch job metric summaries without manually
    loading JSON artifacts.

    Args:
        job_id: The ID of the batch job to read.

    Returns:
        dict[str, Any]: Dictionary containing the aggregated metrics on success,
            or an error message on failure.
    """
    summary_path = get_project_root() / "data" / "batches" / f"{job_id}_summary.json"
    if not summary_path.exists():
        return {"status": "error", "message": f"Summary file not found: {summary_path}"}

    try:
        with open(summary_path, encoding="utf-8") as f:
            return {"status": "success", "data": json.load(f)}
    except Exception as exc:
        return {"status": "error", "message": f"Failed to read summary file: {exc}"}
