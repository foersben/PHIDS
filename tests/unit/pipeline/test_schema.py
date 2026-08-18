"""Unit tests for the DuckDB pipeline schema creation logic."""

import pathlib
import tempfile

import duckdb
import pytest

from data_pipeline.db.schema import create_schema


def test_create_schema() -> None:
    """Verify that all required tables are successfully created in the schema.

    Connects to a temporary DuckDB database in-memory and executes the `create_schema`
    DDL script. Verifies the existence of all expected tables in the information schema.
    """
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False) as f:
        tmp_path = f.name
    pathlib.Path(tmp_path).unlink()

    conn = duckdb.connect(tmp_path)
    create_schema(conn)

    tables = [
        "flora_species",
        "herbivore_species",
        "substances",
        "trigger_rules",
        "diet_matrix",
        "provenance",
    ]
    for t in tables:
        count = conn.execute(f"SELECT count(*) FROM information_schema.tables WHERE table_name = '{t}'").fetchone()[0]
        assert count == 1

    conn.close()
    pathlib.Path(tmp_path).unlink()


def test_schema_constraints() -> None:
    """Verify that DuckDB strictly enforces column constraints.

    Attempts to insert an invalid negative value into a column (`growth_rate`)
    that has a CHECK constraint enforcing positivity. Asserts that DuckDB rejects
    the transaction.
    """
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False) as f:
        tmp_path = f.name
    pathlib.Path(tmp_path).unlink()

    conn = duckdb.connect(tmp_path)
    create_schema(conn)

    with pytest.raises(duckdb.Error, match="CHECK constraint failed"):
        conn.execute("INSERT INTO flora_species (species_id, canonical_name, growth_rate) VALUES (999, 'Test', -0.1)")
        conn.execute(
            "INSERT INTO flora_species VALUES (1,'Test',-0.001,20.0,2.0,5.0,1.0,0.1,1.0,NULL,NULL,NULL,NULL,NULL,NULL)"
        )

    conn.close()
    pathlib.Path(tmp_path).unlink()
