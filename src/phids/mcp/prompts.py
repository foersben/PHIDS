# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Pre-baked guidance prompts exposed via FastMCP for autonomous agent workflows."""

from __future__ import annotations

from phids.mcp.app import mcp


@mcp.prompt()
def analyze_simulation_drift() -> str:
    """Pre-configured prompt mapping to guide debugging agents through drift triage.

    Returns:
        str: Structured step-by-step investigation guide for stochastic drift
            anomalies inside the PHIDS engine.
    """
    return (
        "You are tasked with evaluating a stochastic drift anomaly inside the PHIDS engine.\n\n"
        "Follow this triage protocol in order:\n"
        "1. Read `phids://config/draft.json` to establish full scenario context "
        "(species, substances, termination thresholds).\n"
        "2. Call `runtime_snapshot` to confirm active entity counts and Z-code thresholds "
        "match your expectations.\n"
        "3. Call `query_diagnostic_logs` (limit=120) and scan for WARNING/ERROR entries "
        "from `phids.engine.loop`, `phids.engine.systems.*`, or Numba compilation traces.\n"
        "4. Call `validate_okf_compliance` to verify no documentation invariants were "
        "silently broken by a recent schema mutation.\n"
        "5. If a Zarr replay buffer path is available, call `inspect_telemetry_schema` "
        "to confirm frame counts and field arrays are structurally intact.\n"
        "6. Cross-reference all findings. Propose concrete parameter remediation steps "
        "targeting the most probable root cause (seed entropy, flow-field boundary, "
        "or trigger-rule population threshold)."
    )
