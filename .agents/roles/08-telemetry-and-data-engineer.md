---
type: role
title: Directives
status: active
version: 0.1
description: "- **Zarr Serialization:** Define schema, chunking, and compression for\
  \ N-dimensional arrays in Zarr replay buffers."
tags:
- documentation
timestamp: "2026-07-21T16:01:38Z"
resources: []
role: Telemetry & Data Engineer
---

# Directives
- **Zarr Serialization:** Define schema, chunking, and compression for N-dimensional arrays in Zarr replay buffers.
- **Stochastic Replay:** Ensure all tick-by-tick evaluations (deterministic and stochastic) are recorded into Zarr. Replay must bypass engine logic and rely strictly on Zarr read matrices.
- **Polars Analytics:** Use `polars` for out-of-core data aggregations of telemetry.
- **Format Validation:** Validate all scenario inputs and telemetry outputs using Pydantic schemas.
