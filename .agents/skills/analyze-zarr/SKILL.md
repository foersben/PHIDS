---
type: skill
title: Trigger
status: active
version: '0.1'
description: Inspect and validate Zarr replay buffers to verify state recording.
tags:
- python
timestamp: '2026-07-21T16:01:38Z'
resources:
- scripts/inspect_zarr.py
name: Analyze Zarr Telemetry
---

# Trigger
After running a simulation scenario to confirm telemetry schema correctness.

# Execution
```bash
uv run python scripts/inspect_zarr.py path/to/replay.zarr
```
