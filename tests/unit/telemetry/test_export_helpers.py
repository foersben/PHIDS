"""Unit checks for telemetry export helper round-trips across file and bytes outputs."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from phids.telemetry.export import export_bytes_csv, export_bytes_json, export_csv, export_json


def test_telemetry_export_helpers_write_files_and_bytes(tmp_path: Path) -> None:
    """Verify CSV and NDJSON export helpers agree between file and bytes representations."""
    frame = pl.DataFrame({"tick": [0, 1], "flora_population": [2, 3]})

    csv_path = tmp_path / "telemetry.csv"
    json_path = tmp_path / "telemetry.ndjson"
    export_csv(frame, csv_path)
    export_json(frame, json_path)

    assert "tick" in csv_path.read_text(encoding="utf-8")
    assert '"tick":0' in json_path.read_text(encoding="utf-8").replace(" ", "")
    assert export_bytes_csv(frame).startswith(b"tick")
    assert b'"tick":0' in export_bytes_json(frame).replace(b" ", b"")
