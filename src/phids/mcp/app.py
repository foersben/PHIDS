# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""FastMCP application instance and main server runner for PHIDS orchestration."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "PHIDS-Orchestrator",
    instructions=(
        "Read-only MCP surface for the PHIDS plant-herbivore simulation engine. "
        "Use the phids://config/draft.json resource for passive context reads before "
        "invoking tools. Tools are scoped to inspection and validation only - never "
        "attempt to mutate engine state through this interface."
    ),
)


def run_mcp_server() -> None:
    """Spawn the headless stdio MCP communications loop.

    Launches the FastMCP stdio server process, reading JSON-RPC requests from
    stdin and streaming responses back over stdout.
    """
    mcp.run()
