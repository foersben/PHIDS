---
type: Reference
title: PHIDS Routing & Capabilities
status: stable
stale_after: "2027-01-01T00:00:00Z"
version: 1.1
description: Primary routing index for AI agents linking roles, rules, and progressive skills.
tags: [agents, guidelines, routing]
generated: {by: process:agent-os-refactor, at: "2026-10-30T00:00:00Z"}
verified: {by: process:agent-os-refactor, at: "2026-10-30T00:00:00Z"}
---

# PHIDS Routing & Capabilities Reference

This document serves as the architectural index for agent roles, rules, and operational skills in the PHIDS ecosystem.

## Master Router

The canonical operational rules and routing instructions reside at the workspace root in `AGENTS.md`.

## Architectural Summary

* **Engine:** Pure data-oriented ECS. Entities are integer IDs. Components are contiguous NumPy arrays. Systems are pure functions operating on double-buffered layers.
* **Math & JIT:** Hot-path kernels use Numba `@njit`. Dynamic allocations and Python collections are prohibited inside inner loops. State transfers use branchless float masks (0.0/1.0).
* **Replay:** Deterministic PRNG streams serialize state bit-by-bit into Zarr buffers. Playback queries Zarr buffers directly.
* **Documentation & Parity:** All behavioral cascades must maintain 1:1 table-to-trace parity verified by `verify_matrix_trace_parity.py --all`.

## Directory References

* **Agent Decision Matrix:** [.agents/index.md](index.md)
* **Specialized Agent Roles:** [.agents/roles/](roles/)
* **Behavioral Rules:** [.agents/rules/](rules/)
* **Progressive Skills:** [.agents/skills/](skills/)
