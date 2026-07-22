---
type: rule
trigger: always_on
description: Stochastic engine and telemetry replay mandates
---

# Mandates

- **Telemetry Replay:** Record all tick outcomes (deterministic & stochastic) tick-by-tick into Zarr replay buffers.
- **Bypass Engine:** Playback must read historical Zarr matrices directly, bypassing all engine loop logic.
- **Immutable Tick:** Enforce double-buffering. Read states are immutable during ticks; write all outcomes (including random ones) to the `_write` layer.
- **Controlled RNG:** Seed PRNGs per Biotope region or Swarm component for reproducible debugging.
