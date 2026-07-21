---
type: guide
title: Agent Ecosystem & MCP
status: active
version: 0.1
description: Documentation for Agent Ecosystem & MCP in the PHIDS framework.
tags:
- phids
timestamp: "2026-07-21T16:01:38Z"
resources: []
---

To manage documentation, testing, and lifecycle operations reproducibly, PHIDS integrates an explicit human-and-agent governance model based on the Model Context Protocol (MCP).

## Agent Roles & Governance

To keep implementation truth, documentation truth, and verification truth separated until they can be deliberately reconciled, tasks are routed to specialized agents:

- **`docs-librarian`**: The centralized coordinator for all documentation logic, structure, and validation. It maintains the Information Architecture (IA) and delegates concrete file writing.
- **`docs-scientist`**: Dedicated to writing formal, equation-backed scientific and mathematical modeling documentation (like those found in the Scientific Model deep dives).
- **`docs-operator`**: Focuses on operational, procedural guides tailored to developer execution, CI runbooks, and repository configurations.
- **`git-ops`**: The sole agent authorized to manage repository commits, branches, and PR workflows. It safeguards clean commit slices and strictly respects remote-impacting authorizations.
- **`test-ops`**: Triggers, evaluates, and resolves failures in the test suites, typing coverage, and benchmark outputs, isolating the smallest valid failing slice before pushing fixes upstream.

## Model Context Protocol (MCP) Capabilities

MCP defines the strict technical surface connecting the repository tooling to the AI agents. While the agent governance dictates *who* executes a task, the MCP capability layer defines exactly *what* an AI can read or execute through the connected PHIDS server.

It consists of three distinct classes:

- **Resources**: Read-only contexts providing state visibility without execution side effects. For example, `phids://config/draft.json` exposes the full active scenario draft configuration without spending a tool-call budget.
- **Tools**: Executable actions governed by safety barriers. These actively inspect the repository or the runtime environment. Available tools include `runtime_snapshot` (enhanced counts and dimensions), `inspect_telemetry_schema` (Zarr data layout visibility), `validate_okf_compliance` (pre-commit aligned constraint verification), and `query_diagnostic_logs`.
- **Prompts**: Standardized instructions utilized during specific triage operations to improve consistency (e.g., `analyze_simulation_drift` for debugging workflow bootstrapping).

Agents do not execute generic, arbitrary operations; rather, they rely on specifically registered MCP Tools assigned to their governance role to affect the repository deterministically.
