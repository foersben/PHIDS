---
type: Agent Rule
title: "Rule 01: Stochastic Engine & Replay Invariants"
status: stable
stale_after: "2027-01-01T00:00:00Z"
version: 1.0
trigger: always_on
description: Stochastic engine, PRNG seed streams, and telemetry replay invariants.
tags: [stochastic, prng, replay, zarr, determinism]
generated: {by: "process:agent-os-refactor", at: "2026-10-30T00:00:00Z"}
verified: {by: "process:agent-os-refactor", at: "2026-10-30T00:00:00Z"}
---

# Stochastic Engine & Replay Invariants

Mandates governing reproducibility, PRNG streams, and bit-exact replay in the PHIDS simulation engine.

## Core Mandates

* **PRNG Streams:** All stochastic sampling must derive from explicit `numpy.random.Generator` instances (PCG64 bit generator). Global `numpy.random.*` or bare `random.*` calls are strictly banned.
* **Deterministic Seeding:** Seeds must be deterministically partitioned per Biotope coordinate tile or Swarm component slice. Given the same scenario definition and master seed, tick trajectories must be bit-identical across runs.
* **Zarr Replay Buffering:** Every simulation evaluation (deterministic kinetics and stochastic outcomes alike) must serialize tick-by-tick into Zarr replay buffers (`/replay/{scenario_id}/{seed}/tick_{N}`).
* **Engine-Bypassing Playback:** Replay inspection and frontend trajectory scrubbing must query historical Zarr arrays directly, strictly bypassing all engine calculation and loop logic.
* **Double-Buffering Immutability:** Engine components read strictly from current layer arrays and write exclusively to `_write` layers. Read buffers remain immutable throughout the tick phase.
* **State Hash Invariance:** Key invariant tests must compute state hashes (BLAKE3/SHA-256 over contiguous component buffers) at defined checkpoint intervals to assert bit-level reproducibility.
