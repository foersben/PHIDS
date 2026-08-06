# Documentation Overhaul Changelog

## Structural Analysis & Re-organization
* **Removed** `docs/speculative_research` directory to enforce logical grouping.
* **Relocated** `parameter_calibration_strategy.md` and `spatiotemporal_scaling.md` into `docs/scientific_model/future_prospects/`.
* **Relocated** `ai_coevolution_dse.md` and `agentic_log_writer.md` into `docs/scenario_guide/future_prospects/`.
* **Relocated** `gpu_cuda_acceleration.md` into `docs/technical_architecture/future_prospects/`.
* **Updated** `zensical.toml` mapping to strictly reflect these newly grouped nested hierarchies.
* **Updated** repository-wide internal markdown references in `roadmap.md`, `index.md`, `agent_ecosystem.md`, and section indexes to resolve paths against the new schema.

## Scientific Tone & Expository Depth
* **Rewrote** `docs/scientific_model/ecological_analytics.md` to elevate writing quality to an advanced scientific textbook standard.
* **Replaced** bullet-point summaries in `Batch Processing Diagnostics` with continuous flowing prose detailing Stacked Biomass Proxies, Phase Space tracking, and Kaplan-Meier estimators for survival probability.
* **Replaced** bullet-point summaries in `Live Simulation Diagrams` with explanatory prose mapping grid cell metrics to visual telemetry charts.
* **Replaced** bullet-point summaries in `Tabular Ledger` with technical prose detailing zero-copy memory management via Polars.
* **Integrated** the generalized Reaction-Diffusion formal mathematical PDE using LaTeX syntax into the preamble context of `ecological_analytics.md`.

## Diagrams & Technical Verification
* **Added** a Mermaid.js `sequenceDiagram` in `docs/scientific_model/ecological_analytics.md` accurately modeling the ECS Double-Buffering Phase Commit system architecture.
* **Verified** full markdown compilation success using `zensical build` with 0 unresolved references.
