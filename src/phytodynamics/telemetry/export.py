"""Telemetry export utilities: CSV and JSON export for Lotka-Volterra DataFrames."""

from __future__ import annotations

from pathlib import Path

import polars as pl


def export_csv(df: pl.DataFrame, path: str | Path) -> None:
    """Write the telemetry DataFrame to a CSV file.

    Parameters
    ----------
    df:
        Polars DataFrame produced by :class:`~phytodynamics.telemetry.analytics.TelemetryRecorder`.
    path:
        Destination file path.
    """
    df.write_csv(str(path))


def export_json(df: pl.DataFrame, path: str | Path) -> None:
    """Write the telemetry DataFrame to a newline-delimited JSON file.

    Parameters
    ----------
    df:
        Polars DataFrame produced by :class:`~phytodynamics.telemetry.analytics.TelemetryRecorder`.
    path:
        Destination file path.
    """
    df.write_ndjson(str(path))


def export_bytes_csv(df: pl.DataFrame) -> bytes:
    """Return the telemetry DataFrame serialised as CSV bytes (no filesystem I/O)."""
    return df.write_csv().encode()


def export_bytes_json(df: pl.DataFrame) -> bytes:
    """Return the telemetry DataFrame serialised as newline-delimited JSON bytes."""
    return df.write_ndjson().encode()
