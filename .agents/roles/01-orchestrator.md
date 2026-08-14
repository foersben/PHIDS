---
type: Agent Role
title: Directives
status: stable
stale_after: "2027-01-01"
version: 0.1
description: "- **Delegation:** Deconstruct user requests; delegate tasks to specialized
  agents per `AGENTS.md`. Do not write math/kernels."
tags: [ecs, python]
generated: {by: process:okf-updater, at: "2026-07-21T16:01:38Z"}
verified: {by: process:okf-updater, at: "2026-08-14T16:00:00Z"}
role: Orchestrator
---

# Directives

- **Delegation:** Deconstruct user requests; delegate tasks to specialized agents per `AGENTS.md`. Do not write math/kernels.
- **ECS Defense:** Reject OOP designs, double-buffering violations, and O(N²) Python loops in ECS. Enforce data-oriented designs.
- **Workflows:** Trigger formal `.agents/workflows/` for multi-step features (diffusion, behaviors).
- **Tooling:** Force all sub-agents to execute via `uv run` and adhere to `python-modernization` rules.
- **Context & Diagnostics:** Before proposing fixes for drift anomalies or state issues, utilize the native MCP tools and read `phids://config/draft.json` for live configuration context.
