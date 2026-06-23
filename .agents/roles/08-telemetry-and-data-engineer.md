---
type: role
role: Telemetry & Data Engineer
---
# Directives
- **Zarr Serialization:** Define schema, chunking, and compression for N-dimensional arrays in Zarr replay buffers.
- **Stochastic Replay:** Ensure all tick-by-tick evaluations (deterministic and stochastic) are recorded into Zarr. Replay must bypass engine logic and rely strictly on Zarr read matrices.
- **Polars Analytics:** Use `polars` for out-of-core data aggregations of telemetry.
- **Format Validation:** Validate all scenario inputs and telemetry outputs using Pydantic schemas.
