# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""GIFT (Global Inventory of Floras and Traits) ingest client.

!!! LEGAL WARNING !!!
======================
This module is part of the PHIDS Extended Dataset subpackage.
It is ONLY accessible when ``PHIDS_EXTENDED_MODE=1`` is set (enforced by
the parent ``__init__.py`` guard).

DATA LICENSE: CC-BY-SA 4.0 (ShareAlike)
-----------------------------------------
GIFT data is licensed under Creative Commons Attribution ShareAlike 4.0
International (CC-BY-SA 4.0).

The ShareAlike (SA) clause requires that any derivative database incorporating
GIFT data MUST be distributed under the same CC-BY-SA license. This makes it
INCOMPATIBLE with the PHIDS Proprietary Commercial License.

However, it IS compatible with academic publication under the Extended Dataset
(CC-BY-NC-SA 4.0), because CC-BY-NC-SA is more restrictive than CC-BY-SA
in the commercial dimension while being equally ShareAlike.

This client MUST NOT be used in the default ``run_all.py`` pipeline.
Data produced by this client MUST NOT be published to:
  ``foersben/PHIDS-empirical-database``

It MAY ONLY be published to:
  ``foersben/PHIDS-extended-dataset`` (CC-BY-NC-SA 4.0)

Data source
-----------
- Database: GIFT - Global Inventory of Floras and Traits
- License:  CC-BY-SA 4.0
- URL:      https://gift.uni-goettingen.de/
- Citation: Weigelt, P., et al. (2020). GIFT - A Global Inventory of Floras
            and Traits for macroecology and biogeography. Journal of
            Biogeography, 47(1), 16-43.
            https://doi.org/10.1111/jbi.13623

Traits extracted
----------------
- plant_height_max (mapped to engine max_energy)
- seed_mass (mapped to engine max_energy partial)
- SLA (specific leaf area, mapped to growth_rate)
- woodiness (binary, used as digestibility proxy)
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

CACHE_PATH = Path(__file__).parent.parent.parent / "cache" / "extended" / "gift_raw.parquet"

# GIFT REST API endpoint (public, no registration required for basic traits)
GIFT_API_BASE = "https://gift.uni-goettingen.de/api/traits"

SOURCE_NAME = "GIFT"
assert SOURCE_NAME in NC_SOURCES, "GIFT must be registered in NC_SOURCES"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_gift(force_refresh: bool = False) -> pl.DataFrame:
    """Fetch plant trait data from the GIFT REST API.

    Queries the GIFT API for species-level functional traits covering
    plant height, seed mass, and specific leaf area across the global
    flora catalogue.

    Args:
        force_refresh: Re-fetch from GIFT API even if cache exists.

    Returns:
        A Polars DataFrame with TRY-compatible schema annotated with
        source_db="GIFT".

    """
    if CACHE_PATH.exists() and not force_refresh:
        logger.info("GIFT (CC-BY-SA): loading from cache %s", CACHE_PATH)
        return pl.read_parquet(CACHE_PATH)

    try:
        import httpx
    except ImportError:
        logger.error("httpx not installed: uv sync --group pipeline")
        return _empty_gift_frame()

    # GIFT trait IDs (from the GIFT data documentation)
    gift_traits: dict[str, int] = {
        "plant_height_max": 1,  # Max vegetative height in m
        "seed_mass": 2,  # Seed dry mass in mg
        "SLA": 3,  # Specific leaf area cm2/g
    }

    all_records: list[dict[str, object]] = []

    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        for trait_name, trait_id in gift_traits.items():
            logger.info("GIFT (CC-BY-SA): fetching trait '%s' (ID=%d)", trait_name, trait_id)
            try:
                response = client.get(
                    GIFT_API_BASE,
                    params={"trait_id": trait_id, "format": "json"},
                )
                if response.status_code != 200:
                    logger.warning(
                        "GIFT (CC-BY-SA): HTTP %d for trait '%s'",
                        response.status_code,
                        trait_name,
                    )
                    continue

                data = response.json()
                for entry in data if isinstance(data, list) else []:
                    try:
                        all_records.append(
                            {
                                "species_name": str(entry.get("taxon_name", "")).strip(),
                                "trait_id": _gift_trait_to_try_id(trait_name),
                                "trait_name": trait_name,
                                "std_value": float(entry.get("trait_value", 0)),
                                "unit_name": str(entry.get("unit", "")),
                                "observation_id": str(entry.get("entity_id", "")),
                                "dataset_id": f"GIFT-{SOURCE_NAME}",
                            }
                        )
                    except (ValueError, TypeError):
                        continue

            except Exception as exc:
                logger.warning("GIFT (CC-BY-SA): error for '%s': %s", trait_name, exc)

    if not all_records:
        logger.warning("GIFT (CC-BY-SA): no records fetched - API may require registration")
        return _empty_gift_frame()

    df = pl.DataFrame(all_records)
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(CACHE_PATH)
    logger.info("GIFT (CC-BY-SA): cached %d records to %s", len(df), CACHE_PATH)
    return df


def _gift_trait_to_try_id(trait_name: str) -> int:
    """Map GIFT trait names to pseudo-TRY IDs.

    Args:
        trait_name: GIFT trait name string.

    Returns:
        Integer pseudo-trait ID.

    """
    mapping: dict[str, int] = {
        "plant_height_max": 3106,
        "seed_mass": 26,
        "SLA": 3117,
    }
    return mapping.get(trait_name, 9999)


def _empty_gift_frame() -> pl.DataFrame:
    """Return empty TRY-compatible schema DataFrame.

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
