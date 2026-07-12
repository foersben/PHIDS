"""Academic export pipeline for PHIDS telemetry data.

This package implements the export layer that transforms Polars DataFrames produced by
:class:`~phids.telemetry.analytics.TelemetryRecorder` into publication-ready artifacts
suitable for peer-reviewed manuscript submission. Supported formats include:

- **CSV / NDJSON** (structured)
- **PNG** (matplotlib Agg backend)
- **TikZ / PGFPlots** (LaTeX vector graphics)
- **LaTeX Tables** (booktabs formatting)

The logic has been split into sub-modules by output format to improve modularity and
reduce file size.
"""
