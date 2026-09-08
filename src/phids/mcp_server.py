# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Public facade module for the PHIDS Model Context Protocol (MCP) server.

Exposes read-only simulation states as structural resources and provides
agentic tools for system validation and telemetry inspection without violating
the engine's single-writer architecture.

Decomposed into the modular :mod:`phids.mcp` package. This module maintains
100% backwards-compatibility for existing tests, entry points, and scripts.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from phids.api.ui_state.state import get_draft
from phids.mcp import (
    active_draft_resource,
    analyze_simulation_drift,
    export_telemetry_data,
    inspect_live_simulation,
    inspect_telemetry_schema,
    live_simulation_resource,
    mcp,
    query_batch_jobs,
    query_diagnostic_logs,
    query_telemetry_schema,
    read_batch_summary,
    run_mcp_server,
    runtime_snapshot,
    validate_biological_invariants,
    validate_okf_compliance,
    validate_simulation_config,
)
from phids.mcp.helpers import _DEFAULT_PROJECT_ROOT, _draft_to_json
from phids.shared.logging_config import get_recent_logs

_PROJECT_ROOT: Path = _DEFAULT_PROJECT_ROOT


def _get_active_sim_loop() -> Any | None:
    """Safely return the active live SimulationLoop instance if loaded under FastAPI.

    Returns:
        Any | None: The active simulation loop instance, or None if inactive.
    """
    try:
        from phids.api import main as api_main

        return getattr(api_main, "_sim_loop", None)
    except (ImportError, AttributeError):
        return None


__all__ = [
    "_PROJECT_ROOT",
    "_draft_to_json",
    "_get_active_sim_loop",
    "active_draft_resource",
    "analyze_simulation_drift",
    "export_telemetry_data",
    "get_draft",
    "get_recent_logs",
    "inspect_live_simulation",
    "inspect_telemetry_schema",
    "live_simulation_resource",
    "mcp",
    "query_batch_jobs",
    "query_diagnostic_logs",
    "query_telemetry_schema",
    "read_batch_summary",
    "run_mcp_server",
    "runtime_snapshot",
    "subprocess",
    "validate_biological_invariants",
    "validate_okf_compliance",
    "validate_simulation_config",
]

if __name__ == "__main__":
    run_mcp_server()
