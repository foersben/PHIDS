---
type: Agent Skill
title: Trigger
status: active
version: 0.1
description: Inspect and validate Zarr replay buffers to verify state recording.
tags: [python]
generated: {by: process:okf-updater, at: "2026-07-21T16:01:38Z"}
name: Analyze Zarr Telemetry
sources:
- resource: scripts/inspect_zarr.py
---

# Trigger

After running a simulation scenario to confirm telemetry schema correctness.

# Execution

```bash
uv run python scripts/inspect_zarr.py path/to/replay.zarr
```
