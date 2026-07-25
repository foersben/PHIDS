# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""BIEN (Botanical Information and Ecology Network) ingest client.

!!! LEGAL WARNING !!!
======================
This module is part of the PHIDS Extended Dataset subpackage.
It is ONLY accessible when ``PHIDS_EXTENDED_MODE=1`` is set (enforced by
the parent ``__init__.py`` guard).

DATA LICENSE: CC-BY-NC-ND 4.0
-------------------------------
BIEN data is licensed under Creative Commons Attribution NonCommercial
NoDerivatives 4.0 International (CC-BY-NC-ND 4.0).

This means:
  - Non-Commercial (NC): You MAY NOT use this data for commercial purposes.
  - No Derivatives (ND): You MAY NOT distribute a modified or transformed
    version of this data (including its inclusion in bio_database.json).

This client MUST NOT be used in the default ``run_all.py`` pipeline.
Data produced by this client MUST NOT be published to:
  ``foersben/PHIDS-empirical-database``

It MAY ONLY be published to:
  ``foersben/PHIDS-extended-dataset`` (CC-BY-NC-SA 4.0)

Data source
-----------
- Database: Botanical Information and Ecology Network (BIEN)
- License:  CC-BY-NC-ND 4.0
- URL:      https://bien.nceas.ucsb.edu/bien/
- Citation: Maitner, B.S., et al. (2018). The bien r package: A tool to
            access the Botanical Information and Ecology Network (BIEN)
            database. Methods in Ecology and Evolution, 9(2), 373-379.
            https://doi.org/10.1111/2041-210X.12861

Data access
-----------
BIEN provides a static, version-controlled data export on Zenodo.
This client fetches the stem height, seed mass, and SLA trait compilation
from the BIEN Zenodo repository.
"""

from __future__ import annotations

import logging
from pathlib import Path

import polars as pl

# This import will raise RuntimeError if PHIDS_EXTENDED_MODE != "1"
from data_pipeline.ingest.extended import NC_SOURCES

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Cache goes to the isolated extended/ subdirectory - NEVER the core cache/
CACHE_PATH = Path(__file__).parent.parent.parent / "cache" / "extended" / "bien_raw.parquet"

# Source name for provenance tracking - used by the publish guard
SOURCE_NAME = "BIEN"
assert SOURCE_NAME in NC_SOURCES, "BIEN must be registered in NC_SOURCES"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_bien(force_refresh: bool = False) -> pl.DataFrame:
    """Fetch plant trait data from the BIEN database.

    Fetches morphological and physiological trait records (stem height,
    seed mass, SLA) for a broad set of plant species from the BIEN
    Zenodo data export.

    Args:
        force_refresh: Re-download even if cache exists.

    Returns:
        A Polars DataFrame with TRY-compatible schema (species_name,
        trait_id, trait_name, std_value, unit_name, observation_id,
        dataset_id) annotated with source_db="BIEN".

    """
    if CACHE_PATH.exists() and not force_refresh:
        logger.info("BIEN (NC): loading from cache %s", CACHE_PATH)
        return pl.read_parquet(CACHE_PATH)

    try:
        import httpx
    except ImportError:
        logger.error("httpx not installed: uv sync --group pipeline")
        return _empty_bien_frame()

    # BIEN provides a Zenodo-hosted trait dataset snapshot.
    # We query the BIEN API (public, no key required) for the specific traits.
    bien_api_url = "https://biendata.org/api/species/traits"

    target_traits = ["stem_height", "seed_mass", "leaf_area_specific"]
    all_records: list[dict[str, object]] = []

    try:
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            for trait in target_traits:
                logger.info("BIEN (NC): fetching trait '%s'", trait)
                response = client.get(bien_api_url, params={"trait": trait, "limit": 5000})
                if response.status_code != 200:
                    logger.warning("BIEN (NC): HTTP %d for trait '%s'", response.status_code, trait)
                    continue
                data = response.json()
                for record in data.get("results", []):
                    try:
                        all_records.append(
                            {
                                "species_name": str(record.get("species", "")).strip(),
                                "trait_id": _bien_trait_to_id(trait),
                                "trait_name": trait,
                                "std_value": float(record.get("trait_value", 0)),
                                "unit_name": str(record.get("unit", "")),
                                "observation_id": str(record.get("id", "")),
                                "dataset_id": f"BIEN-{SOURCE_NAME}",
                            }
                        )
                    except (ValueError, TypeError):
                        continue
    except Exception as exc:
        logger.warning("BIEN (NC): fetch error: %s", exc)

    if not all_records:
        logger.warning("BIEN (NC): no records fetched - API may have changed")
        return _empty_bien_frame()

    df = pl.DataFrame(all_records)
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(CACHE_PATH)
    logger.info("BIEN (NC): cached %d records to %s", len(df), CACHE_PATH)
    return df


def _bien_trait_to_id(trait_name: str) -> int:
    """Map BIEN trait names to pseudo-TRY IDs.

    Args:
        trait_name: BIEN trait name string.

    Returns:
        Integer pseudo-trait ID.

    """
    mapping: dict[str, int] = {
        "stem_height": 3106,
        "seed_mass": 26,
        "leaf_area_specific": 3117,
    }
    return mapping.get(trait_name, 9999)


def _empty_bien_frame() -> pl.DataFrame:
    """Return an empty DataFrame with the TRY-compatible schema.

    Returns:
        Empty Polars DataFrame.

    """
    return pl.DataFrame(
        {
            "species_name": pl.Series([], dtype=pl.Utf8),
            "trait_id": pl.Series([], dtype=pl.Int64),
            "trait_name": pl.Series([], dtype=pl.Utf8),
            "std_value": pl.Series([], dtype=pl.Float64),
            "unit_name": pl.Series([], dtype=pl.Utf8),
            "observation_id": pl.Series([], dtype=pl.Utf8),
            "dataset_id": pl.Series([], dtype=pl.Utf8),
        }
    )
