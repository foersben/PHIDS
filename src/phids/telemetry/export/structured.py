# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Telemetry export to structured formats.

Exports telemetry dataframes into structured formats such as CSV and NDJSON.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    import polars as pl


def export_csv(df: pl.DataFrame, path: str | Path) -> None:
    """Write the telemetry DataFrame to a CSV file.

    Args:
        df: Polars DataFrame produced by the telemetry recorder.
        path: Destination file path.

    """
    df.write_csv(str(path))


def export_json(df: pl.DataFrame, path: str | Path) -> None:
    """Write the telemetry DataFrame to a newline-delimited JSON file.

    Args:
        df: Polars DataFrame produced by the telemetry recorder.
        path: Destination file path.

    """
    df.write_ndjson(str(path))


def export_bytes_csv(df: pl.DataFrame) -> bytes:
    """Return the telemetry DataFrame serialized as CSV bytes.

    Args:
        df: Polars DataFrame to serialize.

    Returns:
        bytes: CSV-encoded bytes.

    """
    return df.write_csv().encode()


def export_bytes_json(df: pl.DataFrame) -> bytes:
    """Return the telemetry DataFrame serialized as NDJSON bytes.

    Args:
        df: Polars DataFrame to serialize.

    Returns:
        bytes: NDJSON-encoded bytes.

    """
    return df.write_ndjson().encode()
