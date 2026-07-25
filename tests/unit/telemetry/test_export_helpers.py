# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit checks for telemetry export helper round-trips across file and bytes outputs."""

from __future__ import annotations

from typing import TYPE_CHECKING

import polars as pl

from phids.telemetry.export.core import aggregate_to_dataframe, filter_telemetry_rows
from phids.telemetry.export.structured import (
    export_bytes_csv,
    export_bytes_json,
    export_csv,
    export_json,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_telemetry_export_helpers_write_files_and_bytes(tmp_path: Path) -> None:
    """Verify CSV and NDJSON export helpers agree between file and bytes representations.

    Args:
        tmp_path: Temporary path for file creation.
    """
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

    df = aggregate_to_dataframe(aggregate, flora_names={1: "flora-a"}, herbivore_names={2: "swarm-b"})

    assert list(df["flora-a_pop_mean"]) == [4.0, 5.0]
    assert list(df["flora-a_pop_std"]) == [0.0, 0.0]
    assert list(df["swarm-b_pop_mean"]) == [1.0, 2.0]
    assert list(df["swarm-b_pop_std"]) == [0.0, 0.0]


def test_aggregate_to_dataframe_returns_empty_for_non_list_ticks() -> None:
    """Aggregate export returns an empty dataframe when ticks are missing or malformed."""
    df = aggregate_to_dataframe({"ticks": "invalid"})
    assert df.empty


def test_filter_telemetry_rows_returns_original_if_no_filters() -> None:
    """If no filters are provided, the original rows are returned."""
    rows = [{"tick": 0, "plant_pop_by_species": {1: 10, 2: 20}}]
    assert filter_telemetry_rows(rows) is rows


def test_filter_telemetry_rows_filters_flora_and_herbivores() -> None:
    """Filters nested dictionaries based on provided CSV strings."""
    rows = [
        {
            "tick": 0,
            "plant_pop_by_species": {1: 10, 2: 20, "3": 30},
            "plant_energy_by_species": {1: 1.0, 2: 2.0},
            "defense_cost_by_species": {1: 1.5, 3: 3.5},
            "swarm_pop_by_species": {10: 100, 20: 200},
            "unrelated_key": "stays_same",
        }
    ]

    filtered = filter_telemetry_rows(
        rows,
        flora_ids="1, 3, invalid",
        herbivore_ids="20",
    )

    assert len(filtered) == 1
    row = filtered[0]

    assert row["unrelated_key"] == "stays_same"
    assert row["tick"] == 0

    assert row["plant_pop_by_species"] == {1: 10, 3: 30}
    assert row["plant_energy_by_species"] == {1: 1.0}
    assert row["defense_cost_by_species"] == {1: 1.5, 3: 3.5}

    assert row["swarm_pop_by_species"] == {20: 200}
