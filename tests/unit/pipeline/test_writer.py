import sys
from unittest.mock import MagicMock
sys.modules['sklearn'] = MagicMock()
sys.modules['sklearn.cluster'] = MagicMock()
sys.modules['sklearn.preprocessing'] = MagicMock()
sys.modules['sklearn.impute'] = MagicMock()

import sys
from unittest.mock import MagicMock
sys.modules['sklearn'] = MagicMock()
sys.modules['sklearn.cluster'] = MagicMock()
sys.modules['sklearn.preprocessing'] = MagicMock()
sys.modules['sklearn.impute'] = MagicMock()

# ruff: noqa: D100, D103
import pathlib
import tempfile

import polars as pl

from data_pipeline.db.writer import _ensure_columns, write_all


def test_ensure_columns() -> None:
    df = pl.DataFrame({"a": [1], "b": ["x"]})
    required = {"a", "c"}
    defaults = {"c": 5}
    df_ensured = _ensure_columns(df, required, defaults)
    assert "c" in df_ensured.columns
    assert df_ensured["c"][0] == 5
    assert "a" in df_ensured.columns
    assert "b" in df_ensured.columns  # _ensure_columns doesn't drop extras


def test_write_all() -> None:
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False) as f:
        tmp_path = f.name
    pathlib.Path(tmp_path).unlink()

    # Create dummy DataFrames
    flora = pl.DataFrame(
        {
            "species_id": [1],
            "canonical_name": ["TestFlora"],
            "growth_rate": [0.1],
            "max_energy": [50.0],
            "survival_threshold": [5.0],
            "seed_cost": [10.0],
            "seed_dispersion_radius": [2.0],
            "mechanical_damage_per_bite": [0.1],
            "digestibility_modifier": [1.0],
        }
    )

    herbivore = pl.DataFrame(
        {
            "species_id": [1],
            "canonical_name": ["TestHerb"],
            "metabolism_upkeep": [0.1],
            "consumption_rate": [1.0],
            "mitosis_threshold": [20.0],
            "split_ratio": [0.5],
        }
    )

    substances = pl.DataFrame(
        {
            "substance_id": [1],
            "name": ["TestSub"],
            "is_toxin": [False],
            "lethal": [False],
            "lethality_rate": [0.0],
            "repellent": [True],
            "repellent_walk_ticks": [5],
            "energy_cost_per_tick": [0.1],
            "synthesis_duration": [3],
            "irreversible": [False],
        }
    )

    trigger_rules = pl.DataFrame(
        {
            "rule_id": [1],
            "flora_species_id": [1],
            "rule_index": [0],
            "min_herbivore_population": [5],
            "aftereffect_ticks": [10],
            "condition_kind": ["herbivore_presence"],
            "action_type": ["synthesize_substance"],
        }
    )

    diet_matrix = pl.DataFrame(
        {
            "herbivore_species_id": [1],
            "flora_species_id": [1],
            "is_edible": [True],
            "globi_documented": [False],
        }
    )

    provenance = pl.DataFrame(
        {
            "record_id": [1],
            "species_canonical": ["TestFlora"],
            "source_db": ["TestDB"],
            "source_license": ["CC0"],
            "access_date": ["2026-07-16"],
            "raw_trait_key": ["test_trait"],
            "derived_param": ["growth_rate"],
            "derived_value": [0.1],
        }
    )

    conn = write_all(
        flora_archetypes=flora,
        herbivore_archetypes=herbivore,
        substances_df=substances,
        trigger_rules_df=trigger_rules,
        diet_matrix_df=diet_matrix,
        provenance_df=provenance,
        db_path=tmp_path,
        overwrite=True,
    )

    # Verify flora row count
    assert conn.execute("SELECT count(*) FROM flora_species").fetchone()[0] == 1

    conn.close()
    pathlib.Path(tmp_path).unlink()
