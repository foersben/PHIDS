"""Unit checks for telemetry export helper round-trips across file and bytes outputs."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from phids.telemetry.export import (
    aggregate_to_dataframe,
    export_bytes_csv,
    export_bytes_json,
    export_csv,
    export_json,
)


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


def test_aggregate_to_dataframe_coerces_species_keys_and_defaults_missing_std() -> None:
    """Aggregate export coercion keeps per-species series stable for mixed key types."""
    aggregate: dict[str, object] = {
        "ticks": [0, 1],
        "flora_population_mean": [5.0, 6.0],
        "flora_population_std": [0.1, 0.2],
        "herbivore_population_mean": [2.0, 3.0],
        "herbivore_population_std": [0.3, 0.4],
        "per_flora_pop_mean": {"1": [4.0, 5.0]},
        "per_herbivore_pop_mean": {2: [1.0, 2.0]},
    }

    df = aggregate_to_dataframe(
        aggregate, flora_names={1: "flora-a"}, herbivore_names={2: "swarm-b"}
    )

    assert list(df["flora-a_pop_mean"]) == [4.0, 5.0]
    assert list(df["flora-a_pop_std"]) == [0.0, 0.0]
    assert list(df["swarm-b_pop_mean"]) == [1.0, 2.0]
    assert list(df["swarm-b_pop_std"]) == [0.0, 0.0]


def test_aggregate_to_dataframe_returns_empty_for_non_list_ticks() -> None:
    """Aggregate export returns an empty dataframe when ticks are missing or malformed."""
    df = aggregate_to_dataframe({"ticks": "invalid"})
    assert df.empty
