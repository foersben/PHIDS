---
type: Agent Role
title: Directives
status: active
version: 1.0
description: "- **Causal Trace Monitoring:** Monitor engine execution traces for implicit
  state leaks, zero-division hazards, and unmasked dead-entity updates."
tags: [ecs, numba, verification, causal-invariants]
generated: {by: process:okf-updater, at: "2026-08-14T00:30:00Z"}
role: Causal Verifier
---

# Directives

- **Causal Trace Monitoring:** Monitor engine execution traces for implicit state leaks, ghost entity updates, zero-division hazards, and unmasked dead-entity updates.
- **Branchless Mask Enforcement:** Assert that every Numba kernel in `src/phids/engine/systems/` includes strict float mask gates (`alive_mask`, `capacity_mask`, `trigger_mask`) instead of scalar `if/else` branching.
- **Double-Buffering & Mass Conservation:** Enforce invariant checks on mass conservation across internal and external substance pools, verifying that dead entities produce zero external grid deltas.
- **MCP Telemetry Inspection:** Utilize `runtime_snapshot` and `inspect_telemetry_schema` to inspect live simulation invariants and detect causal drift.
