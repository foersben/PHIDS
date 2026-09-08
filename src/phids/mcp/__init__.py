# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Model Context Protocol (MCP) modular orchestration package for PHIDS.

Provides read-only simulation state resources, validation primitives,
diagnostic inspection, and telemetry exporters via FastMCP.
"""

from __future__ import annotations

from phids.mcp.app import mcp, run_mcp_server
from phids.mcp.prompts import analyze_simulation_drift
from phids.mcp.resources import active_draft_resource, live_simulation_resource
from phids.mcp.tools_simulation import (
    inspect_live_simulation,
    query_batch_jobs,
    read_batch_summary,
    runtime_snapshot,
)
from phids.mcp.tools_telemetry import (
    export_telemetry_data,
    inspect_telemetry_schema,
    query_telemetry_schema,
)
from phids.mcp.tools_validation import (
    query_diagnostic_logs,
    validate_biological_invariants,
    validate_okf_compliance,
    validate_simulation_config,
)

__all__ = [
    "active_draft_resource",
    "analyze_simulation_drift",
    "export_telemetry_data",
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
    "validate_biological_invariants",
    "validate_okf_compliance",
    "validate_simulation_config",
]
