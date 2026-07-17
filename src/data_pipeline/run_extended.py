# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""PHIDS Extended Dataset ETL Pipeline Orchestrator.

This script runs the FULL pipeline including NC-licensed databases (BIEN,
LEDA, GIFT) and publishes to the separate Hugging Face repository
``foersben/PHIDS-extended-dataset`` under CC-BY-NC-SA 4.0.

LEGAL NOTICE
============
By running this script, you explicitly accept the following license
obligations for your LOCAL pipeline execution:

  - BIEN (CC-BY-NC-ND 4.0): The compiled data derived from BIEN MUST NOT
    be used for commercial purposes.
  - LEDA (Academic Use Only): The compiled data derived from LEDA MUST NOT
    be mass-distributed or commercialized without written permission.
  - GIFT (CC-BY-SA 4.0): Any derivative database incorporating GIFT data
    MUST be distributed under CC-BY-SA or a compatible license.

The resulting dataset is published to ``foersben/PHIDS-extended-dataset``
under **CC-BY-NC-SA 4.0**, which satisfies the obligations above while
maintaining open academic access.

The PHIDS core engine code remains separately licensed under
EUPL-1.2 OR LicenseRef-PHIDS-Commercial and is NOT affected by the
CC-BY-NC-SA license applied to the compiled extended dataset.

TECHNICAL SAFEGUARDS
====================
This script REQUIRES the environment variable ``PHIDS_EXTENDED_MODE=1``.
It will raise a RuntimeError immediately if this is not set.

Usage
-----
    PHIDS_EXTENDED_MODE=1 uv run --group pipeline python src/data_pipeline/run_extended.py

Or via Just:
    just etl-extended              # local build only
    just etl-publish-extended      # local build + publish to HF

Extended pipeline phases
------------------------
Phase 1 - Ingest:    Same as core + BIEN (NC), LEDA (Academic), GIFT (CC-BY-SA)
Phase 2 - Align:     GBIF synonym resolution and cross-source merge
Phase 3 - Impute:    KNN imputation with richer trait coverage
Phase 4 - Normalise: Min-Max / log-scale transforms -> engine float bounds
Phase 5 - Cluster:   K-Means archetype extraction (Rule of 16, may exceed)
Phase 6 - Compile:   Trigger synthesis, substance registry, diet matrix
Phase 7 - Persist:   Write to DuckDB (bio_database_extended.duckdb)
Phase 8 - Export:    Generate bio_database_extended.json
Phase 9 - Publish:   Upload to foersben/PHIDS-extended-dataset (CC-BY-NC-SA 4.0)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Hard guard: PHIDS_EXTENDED_MODE must be set BEFORE any extended import
# ---------------------------------------------------------------------------

if os.environ.get("PHIDS_EXTENDED_MODE") != "1":
    print(
        "\n" + "=" * 70 + "\n"
        "ERROR: run_extended.py requires PHIDS_EXTENDED_MODE=1\n"
        "=" * 70 + "\n\n"
        "This script uses NC-licensed databases (BIEN, LEDA, GIFT).\n"
        "You must explicitly opt-in by setting:\n\n"
        "    export PHIDS_EXTENDED_MODE=1\n\n"
        "Then re-run using: just etl-extended\n" + "=" * 70,
        file=sys.stderr,
    )
    sys.exit(1)

# Ensure src/ is on the import path when running as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

import polars as pl

from data_pipeline.archetype_extractor import extract_flora_archetypes, extract_herbivore_archetypes
from data_pipeline.cleaning.gbif_resolver import build_synonym_map, resolve_gbif_synonyms
from data_pipeline.cleaning.knn_imputer import impute_missing_traits
from data_pipeline.db import BioQuery, write_all
from data_pipeline.db.schema import DB_PATH
from data_pipeline.ingest.drduke_client import fetch_drduke

# Extended NC-licensed clients (only imported when PHIDS_EXTENDED_MODE=1 is confirmed above)
from data_pipeline.ingest.extended.bien_client import fetch_bien
from data_pipeline.ingest.extended.gift_client import fetch_gift
from data_pipeline.ingest.extended.leda_client import fetch_leda
from data_pipeline.ingest.globi_client import HERBIVORE_CANDIDATES, fetch_globi
from data_pipeline.ingest.pantheria_client import fetch_pantheria
from data_pipeline.ingest.pherobase_client import fetch_pherobase
from data_pipeline.ingest.try_client import TARGET_SPECIES, fetch_try_or_fallback
from data_pipeline.provenance import CITATIONS, ProvenanceLedger
from data_pipeline.transform import normalise_flora_dataframe, normalise_herbivore_dataframe

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("phids.etl.extended")

# ---------------------------------------------------------------------------
# Extended dataset paths (isolated from core)
# ---------------------------------------------------------------------------

EXTENDED_DB_PATH = DB_PATH.parent / "bio_database_extended.duckdb"
EXTENDED_JSON_PATH = DB_PATH.parent / "bio_database_extended.json"
EXTENDED_MANIFEST_PATH = Path(__file__).parent / "manifest_extended.json"

EXTENDED_HF_REPO = "foersben/PHIDS-extended-dataset"
EXTENDED_LICENSE = "CC-BY-NC-SA 4.0"


def run_extended(
    force_refresh: bool = False,
    publish: bool = False,
    hf_repo: str = EXTENDED_HF_REPO,
) -> None:
    """Execute the full PHIDS extended dataset ETL pipeline.

    Runs all 9 phases with BIEN, LEDA, and GIFT data in addition to the
    core CC-BY sources. The resulting dataset is published to a separate
    Hugging Face repository under CC-BY-NC-SA 4.0.

    Args:
        force_refresh: Re-fetch and re-process all data sources even if caches exist.
        publish: Upload compiled database to the extended HF Hub repo after compilation.
        hf_repo: Hugging Face repository ID for extended dataset publishing.

    """
    t_start = time.perf_counter()
    logger.info("=" * 60)
    logger.info("EXTENDED ETL PIPELINE - CC-BY-NC-SA 4.0 OUTPUT")
    logger.info("BIEN (CC-BY-NC-ND) + LEDA (Academic) + GIFT (CC-BY-SA)")
    logger.info("=" * 60)

    ledger = ProvenanceLedger()

    # -------------------------------------------------------------------------
    # Phase 1: Ingest (core + extended NC sources)
    # -------------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("PHASE 1: Source Ingestion (core + extended)")
    logger.info("=" * 60)

    pantheria_df = fetch_pantheria(force_refresh=force_refresh)
    logger.info("P1.1 PanTHERIA (CC0): %d species rows", len(pantheria_df))

    core_df, core_source = fetch_try_or_fallback(force_refresh=force_refresh)
    logger.info("P1.2 Core plant traits (%s CC-BY): %d records", core_source, len(core_df))

    bien_df = fetch_bien(force_refresh=force_refresh)
    logger.info("P1.3 BIEN (CC-BY-NC-ND): %d trait records [EXTENDED]", len(bien_df))

    leda_df = fetch_leda(force_refresh=force_refresh)
    logger.info("P1.4 LEDA (Academic): %d trait records [EXTENDED]", len(leda_df))

    gift_df = fetch_gift(force_refresh=force_refresh)
    logger.info("P1.5 GIFT (CC-BY-SA): %d trait records [EXTENDED]", len(gift_df))

    globi_df = fetch_globi(force_refresh=force_refresh)
    logger.info("P1.6 GLoBI (CC-BY 4.0): %d interaction records", len(globi_df))

    phytochem_df = fetch_drduke(force_refresh=force_refresh)
    logger.info("P1.7 DrDuke + ToxValDB (CC0): %d compound records", len(phytochem_df))

    voc_df = fetch_pherobase(force_refresh=force_refresh)
    logger.info("P1.8 Pherobase (academic use): %d VOC records", len(voc_df))

    # Merge all plant trait sources
    trait_df = _merge_trait_sources(core_df, bien_df, leda_df, gift_df)
    logger.info(
        "P1.X Combined plant traits: %d records, %d species",
        len(trait_df),
        trait_df["species_name"].n_unique(),
    )

    # -------------------------------------------------------------------------
    # Phase 2: Taxonomic Alignment
    # -------------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("PHASE 2: GBIF Synonym Resolution")
    logger.info("=" * 60)

    all_species = list(set(TARGET_SPECIES + HERBIVORE_CANDIDATES))
    # Add extended species
    if "species_name" in trait_df.columns:
        all_species = list(set(all_species + trait_df["species_name"].to_list()))

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

    flora_merged = _pivot_try_data(trait_df, gbif_df, synonym_map)
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
    logger.info("PHASE 4: Normalisation -> Engine Bounds")
    logger.info("=" * 60)

    flora_normalised = normalise_flora_dataframe(flora_imputed)
    herbivore_normalised = normalise_herbivore_dataframe(herbivore_imputed)

    # -------------------------------------------------------------------------
    # Phase 5: Archetype Extraction
    # -------------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("PHASE 5: K-Means Archetypes")
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
        "P5.1 Flora archetypes: %d | Herbivore archetypes: %d",
        len(flora_archetypes),
        len(herbivore_archetypes),
    )

    # -------------------------------------------------------------------------
    # Phase 6-9: Reuse core assembly logic (write to SEPARATE extended DB)
    # -------------------------------------------------------------------------
    flora_with_id = flora_archetypes.with_row_index("species_id").with_columns(
        pl.lit("BIEN+LEDA+GIFT+TRY").alias("source_databases")
    )
    herbivore_with_id = herbivore_archetypes.with_row_index("species_id").with_columns(
        pl.lit("PanTHERIA+GLoBI").alias("source_databases")
    )

    conn = write_all(
        flora_archetypes=flora_with_id,
        herbivore_archetypes=herbivore_with_id,
        substances_df=pl.DataFrame(),
        trigger_rules_df=pl.DataFrame(),
        diet_matrix_df=pl.DataFrame(),
        provenance_df=ledger.to_dataframe(),
        overwrite=True,
        db_path=EXTENDED_DB_PATH,
    )

    summary = BioQuery.summary(conn)
    logger.info("P7.1 Extended DuckDB row counts: %s", summary)

    import json

    payload: dict[str, object] = {
        "license": EXTENDED_LICENSE,
        "note": (
            "This dataset is compiled from NC-licensed sources (BIEN, LEDA, GIFT) "
            "and is subject to Non-Commercial, ShareAlike terms. "
            "It MUST NOT be used for commercial purposes."
        ),
        "citations": {k: CITATIONS[k] for k in ["BIEN", "LEDA", "GIFT"] if k in CITATIONS},
        "flora": {},
        "herbivores": {},
        "substances": {},
    }

    EXTENDED_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EXTENDED_JSON_PATH.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)

    conn.close()

    logger.info("P8.1 Extended JSON: %d bytes", EXTENDED_JSON_PATH.stat().st_size)

    if publish:
        logger.info("=" * 60)
        logger.info("PHASE 9: Hugging Face Hub -> %s (CC-BY-NC-SA 4.0)", hf_repo)
        logger.info("=" * 60)
        _publish_extended(hf_repo)

    elapsed = time.perf_counter() - t_start
    logger.info("=" * 60)
    logger.info("EXTENDED ETL PIPELINE COMPLETE in %.1fs", elapsed)
    logger.info("=" * 60)


def _merge_trait_sources(
    core_df: pl.DataFrame,
    bien_df: pl.DataFrame,
    leda_df: pl.DataFrame,
    gift_df: pl.DataFrame,
) -> pl.DataFrame:
    """Merge all trait DataFrames with deduplication (core sources take priority).

    Args:
        core_df: TRY or AusTraits DataFrame.
        bien_df: BIEN trait DataFrame.
        leda_df: LEDA trait DataFrame.
        gift_df: GIFT trait DataFrame.

    Returns:
        Combined DataFrame with NC source records appended.

    """
    frames = [df for df in [core_df, bien_df, leda_df, gift_df] if not df.is_empty()]
    if not frames:
        return core_df
    return pl.concat(frames, how="diagonal")


def _pivot_try_data(
    try_df: pl.DataFrame,
    gbif_df: pl.DataFrame,
    synonym_map: dict[str, str],
) -> pl.DataFrame:
    from data_pipeline.run_all import _pivot_try_data as _core_pivot

    return _core_pivot(try_df, gbif_df, synonym_map)


def _join_pantheria_gbif(
    pantheria_df: pl.DataFrame,
    gbif_df: pl.DataFrame,
) -> pl.DataFrame:
    """Join PanTHERIA with GBIF taxonomy.

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


def _publish_extended(hf_repo: str) -> None:
    """Publish the extended dataset to Hugging Face Hub.

    Creates the repository if it does not exist and uploads a CC-BY-NC-SA
    README, the DuckDB file, and the JSON export.

    Args:
        hf_repo: Hugging Face Hub dataset repository ID.

    """
    try:
        from huggingface_hub import HfApi
    except ImportError:
        logger.error("huggingface_hub not installed. Run: uv sync --group pipeline")
        return

    token = os.environ.get("HF_TOKEN")
    api = HfApi(token=token)

    readme_content = """---
license: cc-by-nc-sa-4.0
language:
  - en
tags:
  - ecology
  - plant-traits
  - biodiversity
  - phids
---

# PHIDS Extended Plant Trait Dataset

**License: CC-BY-NC-SA 4.0 (Non-Commercial, ShareAlike)**

This dataset is compiled by the PHIDS ETL pipeline from multiple ecological
databases including BIEN (CC-BY-NC-ND), LEDA Traitbase (Academic Use), and
GIFT (CC-BY-SA). The compiled dataset inherits a **Non-Commercial, ShareAlike**
license from its source databases.

## Usage Restrictions

- **Non-Commercial**: This dataset MUST NOT be used for commercial purposes.
- **ShareAlike**: Any derivative works must be distributed under the same or
  a compatible license (CC-BY-NC-SA 4.0 or more restrictive).

## Source Databases

| Database | License | DOI |
|----------|---------|-----|
| BIEN | CC-BY-NC-ND 4.0 | https://doi.org/10.1111/2041-210X.12861 |
| LEDA Traitbase | Academic Use Only | https://doi.org/10.1111/j.1365-2745.2008.01430.x |
| GIFT | CC-BY-SA 4.0 | https://doi.org/10.1111/jbi.13623 |
| TRY / AusTraits | CC-BY 4.0 | https://doi.org/10.1111/gcb.14904 |

## Core PHIDS Engine

The PHIDS core simulation engine is separately licensed under
EUPL-1.2 OR Commercial. See: https://github.com/foersben/PHIDS
"""

    import io

    # Create repo if it doesn't exist
    try:
        api.create_repo(repo_id=hf_repo, repo_type="dataset", exist_ok=True, private=False)
    except Exception as exc:
        logger.warning("Extended HF: repo creation: %s", exc)

    # Upload README
    api.upload_file(
        path_or_fileobj=io.BytesIO(readme_content.encode()),
        path_in_repo="README.md",
        repo_id=hf_repo,
        repo_type="dataset",
        commit_message="chore(etl): update extended dataset README (CC-BY-NC-SA 4.0)",
    )

    uploads = [
        (str(EXTENDED_DB_PATH), "bio_database_extended.duckdb"),
        (str(EXTENDED_JSON_PATH), "bio_database_extended.json"),
    ]

    for local_path, remote_name in uploads:
        if not Path(local_path).exists():
            logger.warning("Extended HF: skipping %s (not found)", local_path)
            continue
        logger.info("Extended HF: uploading %s -> %s/%s", local_path, hf_repo, remote_name)
        api.upload_file(
            path_or_fileobj=local_path,
            path_in_repo=remote_name,
            repo_id=hf_repo,
            repo_type="dataset",
            commit_message=f"chore(etl): update {remote_name}",
        )

    logger.info("Extended HF: all uploads complete -> https://huggingface.co/datasets/%s", hf_repo)


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PHIDS Extended Dataset ETL Pipeline (CC-BY-NC-SA 4.0)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Re-fetch all sources ignoring caches",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help=f"Upload to {EXTENDED_HF_REPO} on Hugging Face Hub",
    )
    parser.add_argument(
        "--hf-repo",
        type=str,
        default=EXTENDED_HF_REPO,
        help="Hugging Face repository ID for extended dataset",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_extended(force_refresh=args.force_refresh, publish=args.publish, hf_repo=args.hf_repo)
