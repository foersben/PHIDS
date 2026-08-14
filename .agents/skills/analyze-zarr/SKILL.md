---
type: Agent Skill
title: Trigger
status: stable
stale_after: "2027-01-01"
version: 0.1
description: Inspect and validate Zarr replay buffers to verify state recording.
tags: [python]
generated: {by: process:okf-updater, at: "2026-07-21T16:01:38Z"}
verified: {by: process:okf-updater, at: "2026-08-14T16:00:00Z"}
name: Analyze Zarr Telemetry
sources:
- id: inspect_zarr
  resource: scripts/inspect_zarr.py
---

# Trigger

After running a simulation scenario to confirm telemetry schema correctness.

# Execution

```bash
uv run python scripts/inspect_zarr.py path/to/replay.zarr
```
