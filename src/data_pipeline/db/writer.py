# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Bulk writer: Polars DataFrames → DuckDB tables.

Handles all inserts for the six database tables.  Every write is wrapped in
an explicit transaction so a partial pipeline failure leaves the database in
its previous clean state.

Insertion order respects FK constraints:
  1. substances        (no FK dependencies)
  2. flora_species     (no FK dependencies)
  3. herbivore_species (no FK dependencies)
  4. trigger_rules     (FK → flora_species, substances)
  5. diet_matrix       (FK → herbivore_species, flora_species)
  6. provenance        (no FK dependencies)
"""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb
import polars as pl

from data_pipeline.db.schema import create_schema, open_connection

logger = logging.getLogger(__name__)


def write_all(
    flora_archetypes: pl.DataFrame,
    herbivore_archetypes: pl.DataFrame,
    substances_df: pl.DataFrame,
    trigger_rules_df: pl.DataFrame,
    diet_matrix_df: pl.DataFrame,
    provenance_df: pl.DataFrame,
    db_path: Path | None = None,
    overwrite: bool = False,
) -> duckdb.DuckDBPyConnection:
    """Bulk-insert all pipeline outputs into the DuckDB database.

    All six tables are written inside a single transaction.  If any insert
    fails the database is rolled back to its state before the call.

    Args:
        flora_archetypes: Normalised flora archetype DataFrame.
        herbivore_archetypes: Normalised herbivore archetype DataFrame.
        substances_df: Substance definitions DataFrame.
        trigger_rules_df: Compiled trigger rules DataFrame.
        diet_matrix_df: Diet compatibility matrix DataFrame.
        provenance_df: Provenance ledger DataFrame.
        db_path: Override database file path. Defaults to DB_PATH.
        overwrite: If True, truncate all tables before inserting.

    Returns:
        The open DuckDB connection (caller should close when done).

    Raises:
        duckdb.Error: If any insert fails.

    """
    conn = open_connection(db_path)
    create_schema(conn)

    conn.execute("BEGIN TRANSACTION")
    try:
        if overwrite:
            _truncate_all(conn)

        _write_substances(conn, substances_df)
        _write_flora(conn, flora_archetypes)
        _write_herbivores(conn, herbivore_archetypes)
        _write_trigger_rules(conn, trigger_rules_df)
        _write_diet_matrix(conn, diet_matrix_df)
        _write_provenance(conn, provenance_df)

        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    logger.info("DuckDB: all tables written successfully")
    return conn


# ---------------------------------------------------------------------------
# Per-table writers
# ---------------------------------------------------------------------------


def _write_substances(conn: duckdb.DuckDBPyConnection, df: pl.DataFrame) -> None:
    """Insert substance rows, skipping duplicates by substance_id.

    Args:
        conn: Active DuckDB connection.
        df: Substances DataFrame.

    """
    if df.is_empty():
        logger.warning("Substances: empty DataFrame, skipping insert")
        return

    required = {
        "substance_id",
        "name",
        "compound_class",
        "is_toxin",
        "lethal",
        "lethality_rate",
        "repellent",
        "repellent_walk_ticks",
        "energy_cost_per_tick",
        "synthesis_duration",
        "irreversible",
    }
    df = _ensure_columns(
        df,
        required,
        defaults={
            "compound_class": "voc",
            "is_toxin": False,
            "lethal": False,
            "lethality_rate": 0.0,
            "repellent": False,
            "repellent_walk_ticks": 0,
            "energy_cost_per_tick": 0.1,
            "synthesis_duration": 3,
            "irreversible": False,
        },
    )

    conn.register("_tmp_df", df)
    conn.execute(f"INSERT OR IGNORE INTO substances ({', '.join(df.columns)}) SELECT * FROM _tmp_df")
    conn.unregister("_tmp_df")
    logger.info("Substances: inserted %d rows", len(df))


def _write_flora(conn: duckdb.DuckDBPyConnection, df: pl.DataFrame) -> None:
    """Insert flora species rows.

    Species IDs are generated from the row index if not present.

    Args:
        conn: Active DuckDB connection.
        df: Flora archetypes DataFrame.

    """
    if df.is_empty():
        logger.warning("Flora: empty DataFrame, skipping insert")
        return

    if "species_id" not in df.columns:
        df = df.with_row_index("species_id")

    required = {
        "species_id",
        "canonical_name",
        "growth_rate",
        "max_energy",
        "survival_threshold",
        "seed_cost",
        "seed_dispersion_radius",
        "mechanical_damage_per_bite",
        "digestibility_modifier",
    }
    df = _ensure_columns(
        df,
        required,
        defaults={
            "growth_rate": 0.10,
            "max_energy": 20.0,
            "survival_threshold": 2.0,
            "seed_cost": 5.0,
            "seed_dispersion_radius": 1.0,
            "mechanical_damage_per_bite": 0.0,
            "digestibility_modifier": 1.0,
            "canonical_name": "Unknown species",
        },
    )

    # Rename species_name → canonical_name if needed
    if "species_name" in df.columns and "canonical_name" not in df.columns:
        df = df.rename({"species_name": "canonical_name"})
    elif "species_name" in df.columns:
        df = df.drop("species_name")

    _insert_dataframe(conn, "flora_species", df, pk_col="species_id")
    logger.info("Flora: inserted %d species", len(df))


def _write_herbivores(conn: duckdb.DuckDBPyConnection, df: pl.DataFrame) -> None:
    """Insert herbivore species rows.

    Args:
        conn: Active DuckDB connection.
        df: Herbivore archetypes DataFrame.

    """
    if df.is_empty():
        logger.warning("Herbivores: empty DataFrame, skipping insert")
        return

    if "species_id" not in df.columns:
        df = df.with_row_index("species_id")

    required = {
        "species_id",
        "canonical_name",
        "metabolism_upkeep",
        "consumption_rate",
        "mitosis_threshold",
        "split_ratio",
    }

    # Normalise species name column
    if "MSW05_Binomial" in df.columns and "canonical_name" not in df.columns:
        df = df.rename({"MSW05_Binomial": "canonical_name"})
    elif "MSW05_Binomial" in df.columns:
        df = df.drop("MSW05_Binomial")

    df = _ensure_columns(
        df,
        required,
        defaults={
            "metabolism_upkeep": 0.10,
            "consumption_rate": 1.5,
            "mitosis_threshold": 50.0,
            "split_ratio": 0.5,
            "canonical_name": "Unknown herbivore",
        },
    )

    _insert_dataframe(conn, "herbivore_species", df, pk_col="species_id")
    logger.info("Herbivores: inserted %d species", len(df))


def _write_trigger_rules(conn: duckdb.DuckDBPyConnection, df: pl.DataFrame) -> None:
    """Insert trigger rule rows.

    Each row must have a ``flora_species_id`` FK and a ``rule_index``.

    Args:
        conn: Active DuckDB connection.
        df: Trigger rules DataFrame.

    """
    if df.is_empty():
        logger.warning("Trigger rules: empty DataFrame, skipping insert")
        return

    if "rule_id" not in df.columns:
        df = df.with_row_index("rule_id")

    required = {
        "rule_id",
        "flora_species_id",
        "rule_index",
        "min_herbivore_population",
        "aftereffect_ticks",
        "condition_kind",
        "action_type",
    }
    df = _ensure_columns(
        df,
        required,
        defaults={
            "condition_kind": "herbivore_presence",
            "action_type": "synthesize_substance",
            "min_herbivore_population": 5,
            "aftereffect_ticks": 15,
            "rule_index": 0,
        },
    )

    _insert_dataframe(conn, "trigger_rules", df, pk_col="rule_id")
    logger.info("Trigger rules: inserted %d rows", len(df))


def _write_diet_matrix(conn: duckdb.DuckDBPyConnection, df: pl.DataFrame) -> None:
    """Insert diet matrix (herbivore × flora) edges.

    Args:
        conn: Active DuckDB connection.
        df: Diet matrix DataFrame with columns:
            herbivore_species_id, flora_species_id, is_edible, globi_documented.

    """
    if df.is_empty():
        logger.warning("Diet matrix: empty DataFrame, skipping insert")
        return

    required = {"herbivore_species_id", "flora_species_id", "is_edible", "globi_documented"}
    df = _ensure_columns(
        df,
        required,
        defaults={
            "is_edible": True,
            "globi_documented": False,
        },
    )

    conn.register("_tmp_df", df)
    conn.execute(f"INSERT OR IGNORE INTO diet_matrix ({', '.join(df.columns)}) SELECT * FROM _tmp_df")
    conn.unregister("_tmp_df")
    logger.info("Diet matrix: inserted %d edges", len(df))


def _write_provenance(conn: duckdb.DuckDBPyConnection, df: pl.DataFrame) -> None:
    """Insert provenance ledger rows.

    Args:
        conn: Active DuckDB connection.
        df: Provenance records DataFrame.

    """
    if df.is_empty():
        logger.warning("Provenance: empty DataFrame, skipping insert")
        return

    if "record_id" not in df.columns:
        df = df.with_row_index("record_id")

    # Ensure access_date is a date type
    if "access_date" in df.columns and df["access_date"].dtype == pl.Utf8:
        df = df.with_columns(pl.col("access_date").str.to_date("%Y-%m-%d"))

    _insert_dataframe(conn, "provenance", df, pk_col="record_id")
    logger.info("Provenance: inserted %d records", len(df))


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _insert_dataframe(
    conn: duckdb.DuckDBPyConnection,
    table: str,
    df: pl.DataFrame,
    pk_col: str,
) -> None:
    """Insert a Polars DataFrame into a DuckDB table, skipping duplicate PKs.

    Only columns that exist in the target table schema are inserted; extra
    columns in the DataFrame are silently dropped.

    Args:
        conn: Active DuckDB connection.
        table: Target table name.
        df: Source Polars DataFrame.
        pk_col: Primary key column name (used for ``INSERT OR IGNORE``).

    """
    # Get the actual column list from the table schema
    schema_cols: list[str] = [row[0] for row in conn.execute(f"DESCRIBE {table}").fetchall()]
    # Only keep columns that exist in both df and the table
    insert_cols = [c for c in schema_cols if c in df.columns]
    # DuckDB resolves local variable names in SQL strings; register explicitly
    conn.register("_insert_buf", df.select(insert_cols))
    conn.execute(
        f"INSERT OR IGNORE INTO {table} ({', '.join(insert_cols)}) SELECT {', '.join(insert_cols)} FROM _insert_buf"
    )
    conn.unregister("_insert_buf")


def _ensure_columns(
    df: pl.DataFrame,
    required: set[str],
    defaults: dict[str, object],
) -> pl.DataFrame:
    """Add missing columns with default values.

    Args:
        df: Input DataFrame.
        required: Set of column names that must be present.
        defaults: Default values to use for any missing columns.

    Returns:
        DataFrame with all required columns present.

    """
    for col in required:
        if col not in df.columns:
            default = defaults.get(col)
            if default is not None:
                df = df.with_columns(pl.lit(default).alias(col))
            else:
                logger.warning("Missing required column '%s' with no default", col)
    return df


def _truncate_all(conn: duckdb.DuckDBPyConnection) -> None:
    """Truncate all tables in FK-safe reverse order.

    Args:
        conn: Active DuckDB connection.

    """
    tables = [
        "diet_matrix",
        "trigger_rules",
        "provenance",
        "herbivore_species",
        "flora_species",
        "substances",
    ]
    for table in tables:
        conn.execute(f"DELETE FROM {table}")
    logger.info("DuckDB: all tables truncated")
