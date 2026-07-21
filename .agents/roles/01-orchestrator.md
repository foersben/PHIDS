---
type: role
title: Directives
status: active
version: 0.1
description: "- **Delegation:** Deconstruct user requests; delegate tasks to specialized\
  \ agents per `AGENTS.md`. Do not write math/kernels."
tags:
- ecs
- python
timestamp: "2026-07-21T16:01:38Z"
resources: []
role: Orchestrator
---

# Directives

- **Delegation:** Deconstruct user requests; delegate tasks to specialized agents per `AGENTS.md`. Do not write math/kernels.
- **ECS Defense:** Reject OOP designs, double-buffering violations, and O(N²) Python loops in ECS. Enforce data-oriented designs.
- **Workflows:** Trigger formal `.agents/workflows/` for multi-step features (diffusion, behaviors).
- **Tooling:** Force all sub-agents to execute via `uv run` and adhere to `python-modernization` rules.
