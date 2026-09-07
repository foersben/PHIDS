---
type: Agent Skill
title: Visualize Open Knowledge Format Graph
status: stable
stale_after: "2027-01-01T00:00:00Z"
version: 1.0
description: Generates an interactive HTML knowledge graph visualization of the PHIDS documentation and agent ecosystem.
tags: [visualization, okf, documentation, graph]
generated: {by: process:okf-updater, at: "2026-09-06T23:00:00Z"}
verified: {by: process:okf-updater, at: "2026-09-06T23:00:00Z"}
name: Visualize Open Knowledge Format
sources:
- id: visualize_okf
  resource: scripts/visualize_okf.py
---

# Trigger

Dispatched when analyzing cross-document dependencies, auditing knowledge graph continuity, or generating `docs/viz.html` for documentation deployment.

# Execution

```bash
uv run python scripts/visualize_okf.py
```
