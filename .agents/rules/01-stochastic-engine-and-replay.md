---
type: rule
title: Mandates
status: active
version: 0.1
description: "- **Telemetry Replay:** Record all tick outcomes (deterministic & stochastic)\
  \ tick-by-tick into Zarr replay buffers."
tags:
- documentation
timestamp: "2026-07-21T16:01:38Z"
resources: []
trigger: always_on
rule_id: stochastic-engine-and-replay
severity: critical
---

# Mandates
- **Telemetry Replay:** Record all tick outcomes (deterministic & stochastic) tick-by-tick into Zarr replay buffers.
- **Bypass Engine:** Playback must read historical Zarr matrices directly, bypassing all engine loop logic.
- **Immutable Tick:** Enforce double-buffering. Read states are immutable during ticks; write all outcomes (including random ones) to the `_write` layer.
- **Controlled RNG:** Seed PRNGs per Biotope region or Swarm component for reproducible debugging.
