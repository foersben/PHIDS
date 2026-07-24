---
type: skill
name: Analyze Zarr Telemetry
description: Inspect and validate Zarr replay buffers to verify state recording.
---
# Trigger
After running a simulation scenario to confirm telemetry schema correctness.

# Execution
```bash
uv run python scripts/inspect_zarr.py path/to/replay.zarr
```
