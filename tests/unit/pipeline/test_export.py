# ruff: noqa: D100, D103
import json
import pathlib
import tempfile

import polars as pl

from data_pipeline.db.export import export_bio_database_json, export_manifest_json
from data_pipeline.db.writer import write_all


def test_export_json() -> None:
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False) as f:
        tmp_path = f.name
    try:
        pathlib.Path(tmp_path).unlink()
    except Exception:
        pass

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
            "morphological_adaptation": [0.0],
            "chemical_neutralization": [0.0],
            "digestive_efficiency": [1.0],
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
            "condition_json": [json.dumps({"kind": "herbivore_presence", "min_herbivore_population": 5})],
            "action_type": ["synthesize_substance"],
            "action_substance_id": [1],
            "action_json": [json.dumps({"type": "synthesize_substance", "substance_id": 1, "synthesis_duration": 3})],
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

    out_json = pathlib.Path(tmp_path).with_suffix(".json")
    out_manifest = pathlib.Path(tmp_path).with_name("manifest_test.json")

    export_bio_database_json(conn, str(out_json))
    export_manifest_json(conn, str(out_manifest))

    assert out_json.exists()
    assert out_manifest.exists()

    with open(out_json) as f:
        data = json.load(f)
        assert "flora" in data
        assert "TestFlora" in data["flora"]
        assert "herbivores" in data
        assert "TestHerb" in data["herbivores"]

    with open(out_manifest) as f:
        manifest = json.load(f)
        assert "records" in manifest
        assert len(manifest["records"]) == 1
        assert manifest["records"][0]["species_canonical"] == "TestFlora"

    conn.close()
    pathlib.Path(tmp_path).unlink()
    out_json.unlink()
    out_manifest.unlink()
