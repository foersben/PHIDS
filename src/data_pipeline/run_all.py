# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""PHIDS Empirical Database ETL Pipeline Orchestrator.

Executes all pipeline phases in sequence, writing all outputs to a DuckDB
database and generating a JSON export for engine compatibility.

Usage
-----
    uv run --group pipeline python src/data_pipeline/run_all.py

Or via just:
    just etl
    just etl-refresh   # force-refresh all API caches

Pipeline phases
---------------
Phase 1 - Ingest:    Fetch from TRY, GLoBI, PanTHERIA, DrDuke, Pherobase.
                     Results cached as Parquet in src/data_pipeline/cache/.
Phase 2 - Align:     GBIF synonym resolution and cross-source merge.
Phase 3 - Impute:    Phylogenetically-grouped KNN imputation.
Phase 4 - Normalise: Min-Max / log-scale transforms → engine float bounds.
Phase 5 - Cluster:   K-Means archetype extraction (Rule of 16).
Phase 6 - Compile:   Trigger synthesis, substance registry, diet matrix.
Phase 7 - Persist:   Write all tables to DuckDB (bio_database.duckdb).
Phase 8 - Export:    Generate bio_database.json from DuckDB.
Phase 9 - Publish:   Optional Hugging Face Hub upload (CI mode).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

# Ensure src/ is on the import path when running as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

import polars as pl

from data_pipeline.archetype_extractor import extract_flora_archetypes, extract_herbivore_archetypes
from data_pipeline.cleaning.gbif_resolver import build_synonym_map, resolve_gbif_synonyms
from data_pipeline.cleaning.knn_imputer import impute_missing_traits
from data_pipeline.compile.diet import _build_diet_matrix_df
from data_pipeline.compile.substances import _build_substances_df
from data_pipeline.compile.trigger_rules import _build_trigger_rules_df
from data_pipeline.db import (
    BioQuery,
    export_bio_database_json,
    publish_to_huggingface,
    write_all,
)
from data_pipeline.db.export import export_manifest_json
from data_pipeline.ingest.drduke_client import fetch_drduke
from data_pipeline.ingest.globi_client import HERBIVORE_CANDIDATES, fetch_globi
from data_pipeline.ingest.pantheria_client import fetch_pantheria
from data_pipeline.ingest.pherobase_client import fetch_pherobase
from data_pipeline.ingest.try_client import TARGET_SPECIES, fetch_try_or_fallback
from data_pipeline.provenance import CITATIONS, ProvenanceLedger, ProvenanceRecord, today_iso
from data_pipeline.transform import normalise_flora_dataframe, normalise_herbivore_dataframe

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("phids.etl")

# ---------------------------------------------------------------------------
# Substance registry (stable IDs across pipeline runs)
# ---------------------------------------------------------------------------

def run_all(
    force_refresh: bool = False,
    publish: bool = False,
    hf_repo: str = "foersben/PHIDS-empirical-database",
) -> None:
    """Execute the full PHIDS empirical database ETL pipeline.

    Args:
        force_refresh: Re-fetch and re-process all data sources even if caches exist.
        publish: Upload compiled database to Hugging Face Hub after compilation.
        hf_repo: Hugging Face repository ID for publishing.
    """
    t_start = time.perf_counter()
    ledger = ProvenanceLedger()

    # -------------------------------------------------------------------------
    # Phase 1: Ingest
    # -------------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("PHASE 1: Source Ingestion")
    logger.info("=" * 60)

    pantheria_df = fetch_pantheria(force_refresh=force_refresh)
    logger.info("P1.1 PanTHERIA (CC0): %d species rows", len(pantheria_df))

    try_df, try_source = fetch_try_or_fallback(force_refresh=force_refresh)
    n_try_species = try_df["species_name"].n_unique() if "species_name" in try_df.columns else 0
    logger.info(
        "P1.2 Plant traits (%s CC-BY 4.0): %d trait records, %d species",
        try_source,
        len(try_df),
        n_try_species,
    )

    globi_df = fetch_globi(force_refresh=force_refresh)
    logger.info("P1.3 GLoBI (CC-BY 4.0): %d interaction records", len(globi_df))

    phytochem_df = fetch_drduke(force_refresh=force_refresh)
    logger.info("P1.4 DrDuke + ToxValDB (CC0): %d compound records", len(phytochem_df))

    voc_df = fetch_pherobase(force_refresh=force_refresh)
    logger.info("P1.5 Pherobase (academic use): %d VOC records", len(voc_df))

    # -------------------------------------------------------------------------
    # Phase 2: Taxonomic Alignment
    # -------------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("PHASE 2: GBIF Synonym Resolution")
    logger.info("=" * 60)

    all_species = list(set(TARGET_SPECIES + HERBIVORE_CANDIDATES))
    gbif_df = resolve_gbif_synonyms(all_species, force_refresh=force_refresh)
    synonym_map = build_synonym_map(gbif_df)
    resolved_count = int(gbif_df.filter(pl.col("resolved"))["resolved"].sum())
    logger.info("P2.1 GBIF (CC0): %d / %d names resolved", resolved_count, len(all_species))

    # -------------------------------------------------------------------------
    # Phase 3: Merge + Impute
    # -------------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("PHASE 3: Data Merging & KNN Imputation")
    logger.info("=" * 60)

    flora_merged = _pivot_try_data(try_df, gbif_df, synonym_map)
    logger.info("P3.1 Flora merged: %d species, %d columns", len(flora_merged), len(flora_merged.columns))

    flora_numeric_cols = ["sla_cm2_per_g", "seed_dry_mass_g", "height_cm", "leaf_tensile_n_mm2", "lignin_pct"]
    flora_imputed = impute_missing_traits(
        flora_merged, numeric_cols=flora_numeric_cols, family_col="family", order_col="order_name"
    )

    pantheria_with_gbif = _join_pantheria_gbif(pantheria_df, gbif_df)
    herbivore_numeric_cols = [
        "5-1_AdultBodyMass_g",
        "18-1_BasalMetRate_mLO2hr",
        "25-1_WeaningAge_d",
        "10-1_PopulationGrpSize",
    ]
    herbivore_imputed = impute_missing_traits(
        pantheria_with_gbif, numeric_cols=herbivore_numeric_cols, family_col="family", order_col="order_name"
    )
    logger.info("P3.2 Imputation complete")

    # -------------------------------------------------------------------------
    # Phase 4: Normalise
    # -------------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("PHASE 4: Normalisation → Engine Bounds")
    logger.info("=" * 60)

    flora_normalised = normalise_flora_dataframe(flora_imputed)
    herbivore_normalised = normalise_herbivore_dataframe(herbivore_imputed)

    if "growth_rate" in flora_normalised.columns:
        gr_min = flora_normalised["growth_rate"].min()
        gr_max = flora_normalised["growth_rate"].max()
        logger.info("P4.1 growth_rate range: [%.4f, %.4f]", gr_min, gr_max)

    # -------------------------------------------------------------------------
    # Phase 5: Archetype Extraction
    # -------------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("PHASE 5: K-Means Archetypes (Rule of 16)")
    logger.info("=" * 60)

    flora_archetypes = extract_flora_archetypes(
        flora_normalised,
        species_name_col="species_name",
        force_refresh=force_refresh,
    )
    herbivore_archetypes = extract_herbivore_archetypes(
        herbivore_normalised,
        species_name_col="MSW05_Binomial",
        force_refresh=force_refresh,
    )
    logger.info(
        "P5.1 Flora archetypes: %d | Herbivore archetypes: %d", len(flora_archetypes), len(herbivore_archetypes)
    )

    # -------------------------------------------------------------------------
    # Phase 6: Compile substances, trigger rules, diet matrix
    # -------------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("PHASE 6: Trigger Compilation & Relational Assembly")
    logger.info("=" * 60)

    substances_df = _build_substances_df(voc_df, phytochem_df)
    logger.info("P6.1 Substances: %d rows", len(substances_df))

    # Assign stable integer species_ids
    flora_with_id = flora_archetypes.with_row_index("species_id").with_columns(
        pl.lit("TRY+DrDuke+Pherobase").alias("source_databases")
    )
    herbivore_with_id = herbivore_archetypes.with_row_index("species_id").with_columns(
        pl.lit("PanTHERIA+GLoBI").alias("source_databases")
    )

    trigger_rules_df = _build_trigger_rules_df(
        flora_with_id,
        phytochem_df,
        voc_df,
        species_name_col="species_name",
    )
    logger.info("P6.2 Trigger rules: %d rows", len(trigger_rules_df))

    diet_matrix_df = _build_diet_matrix_df(
        herbivore_with_id,
        flora_with_id,
        globi_df,
        herbivore_name_col="MSW05_Binomial",
        flora_name_col="species_name",
    )
    logger.info("P6.3 Diet matrix: %d edges", len(diet_matrix_df))

    # Add provenance entries for archetypes
    _record_archetype_provenance(ledger, flora_with_id, herbivore_with_id)

    # -------------------------------------------------------------------------
    # Phase 7: Write to DuckDB
    # -------------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("PHASE 7: Persist to DuckDB")
    logger.info("=" * 60)

    conn = write_all(
        flora_archetypes=flora_with_id,
        herbivore_archetypes=herbivore_with_id,
        substances_df=substances_df,
        trigger_rules_df=trigger_rules_df,
        diet_matrix_df=diet_matrix_df,
        provenance_df=ledger.to_dataframe(),
        overwrite=True,
    )

    summary = BioQuery.summary(conn)
    logger.info("P7.1 DuckDB row counts: %s", summary)

    # -------------------------------------------------------------------------
    # Phase 8: Export JSON (engine compatibility)
    # -------------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("PHASE 8: JSON Export & Manifest")
    logger.info("=" * 60)

    json_path = export_bio_database_json(conn=conn)
    manifest_path = export_manifest_json(conn=conn)
    conn.close()

    logger.info("P8.1 bio_database.json: %d bytes", json_path.stat().st_size)
    logger.info("P8.2 manifest.json:     %d bytes", manifest_path.stat().st_size)

    # -------------------------------------------------------------------------
    # Phase 9: Optional Hugging Face Publish
    # -------------------------------------------------------------------------
    if publish:
        logger.info("=" * 60)
        logger.info("PHASE 9: Hugging Face Hub → foersben/PHIDS-empirical-database")
        logger.info("=" * 60)
        hf_token = os.environ.get("HF_TOKEN")
        publish_to_huggingface(repo_id=hf_repo, hf_token=hf_token)

    elapsed = time.perf_counter() - t_start
    logger.info("=" * 60)
    logger.info("ETL PIPELINE COMPLETE in %.1fs", elapsed)
    for table, count in summary.items():
        logger.info("  %-30s %d rows", table + ":", count)
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# Phase 6 assemblers
# ---------------------------------------------------------------------------


def _record_archetype_provenance(
    ledger: ProvenanceLedger,
    flora_df: pl.DataFrame,
    herbivore_df: pl.DataFrame,
) -> None:
    """Add provenance records for all compiled archetypes.

    Args:
        ledger: ProvenanceLedger to append to.
        flora_df: Flora archetypes DataFrame.
        herbivore_df: Herbivore archetypes DataFrame.
    """
    date = today_iso()
    for row in flora_df.to_dicts():
        ledger.add(
            ProvenanceRecord(
                species_canonical=str(row.get("species_name", "unknown")),
                source_db="TRY+DrDuke+Pherobase",
                source_license="CC-BY 4.0 (TRY); CC0 (DrDuke); Academic (Pherobase)",
                source_doi=CITATIONS["TRY"]["doi"],
                source_citation=CITATIONS["TRY"]["citation"],
                access_date=date,
                raw_trait_key="archetype_k_means",
                raw_trait_value=None,
                derived_param="growth_rate",
                derived_value=float(row.get("growth_rate", 0.0)),
            )
        )
    for row in herbivore_df.to_dicts():
        ledger.add(
            ProvenanceRecord(
                species_canonical=str(row.get("MSW05_Binomial", "unknown")),
                source_db="PanTHERIA+GLoBI",
                source_license="CC0 (PanTHERIA); CC-BY 4.0 (GLoBI)",
                source_doi=CITATIONS["PanTHERIA"]["doi"],
                source_citation=CITATIONS["PanTHERIA"]["citation"],
                access_date=date,
                raw_trait_key="archetype_k_means",
                raw_trait_value=None,
                derived_param="metabolism_upkeep",
                derived_value=float(row.get("metabolism_upkeep", 0.0)),
            )
        )


# ---------------------------------------------------------------------------
# Merge helpers (unchanged from previous version)
# ---------------------------------------------------------------------------


def _pivot_try_data(
    try_df: pl.DataFrame,
    gbif_df: pl.DataFrame,
    synonym_map: dict[str, str],
) -> pl.DataFrame:
    """Pivot TRY long-format to wide per-species and join GBIF taxonomy.

    Args:
        try_df: Long-format TRY DataFrame.
        gbif_df: GBIF resolution DataFrame.
        synonym_map: Raw-to-canonical name map.

    Returns:
        Wide-format flora DataFrame.
    """
    if try_df.is_empty() or "trait_id" not in try_df.columns:
        return _fallback_flora_frame()

    trait_id_to_col: dict[int, str] = {
        3117: "sla_cm2_per_g",
        26: "seed_dry_mass_g",
        3106: "height_cm",
        163: "leaf_tensile_n_mm2",
        146: "lignin_pct",
        55: "leaf_dry_mass_g",
    }

    agg = try_df.group_by(["species_name", "trait_id"]).agg(pl.col("std_value").median().alias("median_value"))

    species_list = agg["species_name"].unique().to_list()
    rows: list[dict[str, object]] = []
    for species in species_list:
        canonical = synonym_map.get(species, species)
        row: dict[str, object] = {"species_name": canonical, "raw_species_name": species}
        for trait_row in agg.filter(pl.col("species_name") == species).to_dicts():
            col_name = trait_id_to_col.get(int(trait_row["trait_id"]))
            if col_name:
                row[col_name] = trait_row["median_value"]
        rows.append(row)

    from data_pipeline.ingest.try_client import TARGET_SPECIES

    existing_canonicals = {r.get("species_name") for r in rows}
    for target in TARGET_SPECIES:
        if target not in existing_canonicals:
            rows.append({"species_name": target, "raw_species_name": target})

    flora_wide = pl.DataFrame(rows)

    gbif_select = gbif_df.select(
        pl.col("canonical_name").alias("species_name"),
        "family",
        "order_name",
        "class_name",
        "phylum",
    ).unique("species_name")

    return flora_wide.join(gbif_select, on="species_name", how="left")


def _fallback_flora_frame() -> pl.DataFrame:
    """Return a minimal flora frame with jittered neutral traits when TRY is unavailable.

    The jitter guarantees K-Means will see distinct feature vectors and extract
    the full 16 permitted archetypes instead of collapsing all plants into 1.

    Returns:
        Flora DataFrame with pseudo-random trait columns for KNN imputation to fill.
    """
    from data_pipeline.ingest.try_client import TARGET_SPECIES

    n = len(TARGET_SPECIES)
    import numpy as np

    # Deterministic jitter to ensure reproducible K-Means clustering
    rng = np.random.default_rng(42)

    return pl.DataFrame(
        {
            "species_name": TARGET_SPECIES,
            "sla_cm2_per_g": rng.uniform(5.0, 15.0, n).tolist(),
            "seed_dry_mass_g": rng.uniform(0.1, 5.0, n).tolist(),
            "height_cm": rng.uniform(10.0, 500.0, n).tolist(),
            "leaf_tensile_n_mm2": rng.uniform(1.0, 5.0, n).tolist(),
            "lignin_pct": rng.uniform(10.0, 30.0, n).tolist(),
            "family": [None] * n,
            "order_name": [None] * n,
        }
    )


def _join_pantheria_gbif(
    pantheria_df: pl.DataFrame,
    gbif_df: pl.DataFrame,
) -> pl.DataFrame:
    """Join GBIF taxonomy onto PanTHERIA by binomial name.

    Args:
        pantheria_df: Raw PanTHERIA DataFrame.
        gbif_df: GBIF resolution DataFrame.

    Returns:
        PanTHERIA with taxonomy columns appended.
    """
    if "MSW05_Binomial" not in pantheria_df.columns:
        return pantheria_df

    gbif_select = gbif_df.select(
        pl.col("raw_name").alias("MSW05_Binomial"),
        "family",
        "order_name",
        "class_name",
    ).unique("MSW05_Binomial")

    return pantheria_df.join(gbif_select, on="MSW05_Binomial", how="left")


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the ETL pipeline.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="PHIDS Empirical Database ETL Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Re-fetch all sources ignoring Parquet caches",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Upload to foersben/PHIDS-empirical-database on Hugging Face Hub",
    )
    parser.add_argument(
        "--hf-repo",
        type=str,
        default="foersben/PHIDS-empirical-database",
        help="Hugging Face repository ID",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_all(force_refresh=args.force_refresh, publish=args.publish, hf_repo=args.hf_repo)
