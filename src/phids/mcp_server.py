"""Model Context Protocol surface for PHIDS diagnostics.

This module provides a compact stdio-based MCP server that exposes read-only
runtime state without disturbing the HTTP API launcher. The server is intended
for tooling integrations that need a deterministic summary of the active draft
configuration and recent log history while preserving the simulation engine's
single-writer discipline.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from phids.api.ui_state import get_draft
from phids.shared.logging_config import get_recent_logs

mcp = FastMCP("phids")


def _build_runtime_snapshot() -> dict[str, Any]:
    """Assemble a read-only snapshot of the active PHIDS draft state.

    Returns:
        dict[str, Any]: Compact summary containing scenario metadata, grid
        dimensions, species counts, and top-level tick configuration.
    """
    draft = get_draft()
    return {
        "scenario_name": draft.scenario_name,
        "grid_width": draft.grid_width,
        "grid_height": draft.grid_height,
        "max_ticks": draft.max_ticks,
        "tick_rate_hz": draft.tick_rate_hz,
        "flora_species": len(draft.flora_species),
        "herbivore_species": len(draft.herbivore_species),
        "substance_definitions": len(draft.substance_definitions),
        "initial_plants": len(draft.initial_plants),
        "initial_swarms": len(draft.initial_swarms),
    }


@mcp.tool()
def runtime_snapshot() -> dict[str, Any]:
    """Return a compact snapshot of the active PHIDS draft configuration.

    Returns:
        dict[str, Any]: Read-only summary of the currently loaded draft state.
    """
    return _build_runtime_snapshot()


@mcp.tool()
def recent_logs(limit: int = 80) -> list[dict[str, str]]:
    """Return the newest structured log entries recorded by PHIDS.

    Args:
        limit: Maximum number of log rows to return.

    Returns:
        list[dict[str, str]]: Most recent diagnostic log entries in descending
        recency order.
    """
    return get_recent_logs(limit=limit)


def run_mcp_server() -> None:
    """Start the PHIDS MCP server over stdio."""
    mcp.run()
