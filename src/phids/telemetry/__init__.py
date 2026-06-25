"""Telemetry sub-package for simulation observation, termination, and export.

This sub-package implements the three analytical layers that enable scientific interpretation of
completed and in-progress PHIDS simulations. The analytics module (``TelemetryRecorder``)
accumulates per-tick population, energy, and defense-cost metrics into a Polars-backed rolling
buffer, providing both aggregate Lotka-Volterra scalars and per-species breakdowns suitable for
Chart.js visualisation and Monte Carlo ensemble aggregation. The conditions module
(``check_termination``) implements seven rule-based termination criteria (Z1 through Z7) that
halt simulation execution when configured population, energy, or extinction thresholds are
reached, enabling hypothesis-driven experimental design with explicit stopping rules. The export
module provides four output format converters — CSV, NDJSON, PNG (headless Agg matplotlib), and
PGFPlots LaTeX — that transform Polars and pandas DataFrames into publication-ready artifacts for
peer-reviewed manuscript submission.

The telemetry sub-package is intentionally read-only with respect to engine state: it samples ECS
components and environmental layers at the end of each tick without mutating them, preserving the
double-buffered determinism guarantee of the simulation core.
"""
