# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""LEDA Traitbase ingest client.

!!! LEGAL WARNING !!!
======================
This module is part of the PHIDS Extended Dataset subpackage.
It is ONLY accessible when ``PHIDS_EXTENDED_MODE=1`` is set (enforced by
the parent ``__init__.py`` guard).

DATA LICENSE: Academic Use Only (no open-data license)
--------------------------------------------------------
The LEDA Traitbase does not carry an explicit open-data license such as CC0
or CC-BY. Access is granted for academic and non-commercial research purposes
only. Mass extraction or commercial redistribution without explicit written
permission from the copyright holders is prohibited.

This client performs a narrow, targeted download of specific CSV files
published by the LEDA project, applying the same insubstantial extraction
rationale used for Pherobase: only derived, normalized engine parameters
are stored; the raw tabular data is not redistributed.

This client MUST NOT be used in the default ``run_all.py`` pipeline.
Data produced by this client MUST NOT be published to:
  ``foersben/PHIDS-empirical-database``

It MAY ONLY be published to:
  ``foersben/PHIDS-extended-dataset`` (CC-BY-NC-SA 4.0)

Data source
-----------
- Database: LEDA Traitbase (Life history traits of the Northwest European flora)
- License:  Academic Use Only
- URL:      https://uol.de/en/landeco/research/leda/
- Citation: Kleyer, M., et al. (2008). The LEDA Traitbase: A database of
            life-history traits of Northwest European flora.
            Journal of Ecology, 96(6), 1266-1274.
            https://doi.org/10.1111/j.1365-2745.2008.01430.x

Traits extracted
----------------
- Specific leaf area (SLA)
- Plant canopy height
- Seed mass
- Leaf dry matter content (LDMC)
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

import polars as pl

# This import will raise RuntimeError if PHIDS_EXTENDED_MODE != "1"
from data_pipeline.ingest.extended import NC_SOURCES

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CACHE_PATH = Path(__file__).parent.parent.parent / "cache" / "extended" / "leda_raw.parquet"

# LEDA provides individual CSV files per trait
LEDA_BASE_URL = "https://uol.de/en/landeco/research/leda/data-files/"

LEDA_TRAIT_FILES: dict[str, str] = {
    "SLA": "SLA_und_LNC_13_04_2015.txt",
    "plant_height": "LEDA_plant_height.txt",
    "seed_mass": "seed_weight_LEDA.txt",
    "LDMC": "LDMC_und_LNC_13_04_2015.txt",
}

SOURCE_NAME = "LEDA"
assert SOURCE_NAME in NC_SOURCES, "LEDA must be registered in NC_SOURCES"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_leda(force_refresh: bool = False) -> pl.DataFrame:
    """Fetch plant trait data from the LEDA Traitbase.

    Downloads individual trait CSV files from the LEDA project website and
    combines them into a TRY-compatible schema DataFrame. Only numeric,
    species-level mean values are extracted; no raw observation text is stored.

    Args:
        force_refresh: Re-download even if cache exists.

    Returns:
        A Polars DataFrame with TRY-compatible schema annotated with
        source_db="LEDA".

    """
    if CACHE_PATH.exists() and not force_refresh:
        logger.info("LEDA (Academic): loading from cache %s", CACHE_PATH)
        return pl.read_parquet(CACHE_PATH)

    try:
        import httpx
    except ImportError:
        logger.error("httpx not installed: uv sync --group pipeline")
        return _empty_leda_frame()

    all_records: list[dict[str, object]] = []

    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        for trait_name, filename in LEDA_TRAIT_FILES.items():
            url = LEDA_BASE_URL + filename
            logger.info("LEDA (Academic): fetching %s from %s", trait_name, url)
            try:
                response = client.get(url)
                if response.status_code != 200:
                    logger.warning("LEDA (Academic): HTTP %d for '%s'", response.status_code, trait_name)
                    continue
                records = _parse_leda_txt(response.text, trait_name)
                all_records.extend(records)
                logger.info("LEDA (Academic): %d records for '%s'", len(records), trait_name)
            except Exception as exc:
                logger.warning("LEDA (Academic): error for '%s': %s", trait_name, exc)

    if not all_records:
        logger.warning("LEDA (Academic): no records fetched")
        return _empty_leda_frame()

    df = pl.DataFrame(all_records)
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(CACHE_PATH)
    logger.info("LEDA (Academic): cached %d records to %s", len(df), CACHE_PATH)
    return df


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_leda_txt(text: str, trait_name: str) -> list[dict[str, object]]:
    """Parse a LEDA tab-delimited trait file into record dicts.

    Args:
        text: Raw response text from the LEDA server.
        trait_name: Name of the trait being parsed.

    Returns:
        List of record dicts with TRY-compatible keys.

    """
    import csv

    records: list[dict[str, object]] = []
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return records

    reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter="\t")

    for row in reader:
        # LEDA files typically have 'SBS_name' (species binomial) and a numeric column
        species = (row.get("SBS_name") or row.get("species_name") or "").strip()
        if not species:
            continue

        # Try common value column names
        raw_val = None
        for col in ("mean", "Mean", "value", "Value", "SLA_mean", "height_mean", "SW_mean"):
            if col in row and row[col].strip():
                raw_val = row[col].strip()
                break

        if raw_val is None:
            continue

        try:
            std_value = float(raw_val)
        except ValueError:
            continue

        records.append(
            {
                "species_name": species,
                "trait_id": _leda_trait_to_id(trait_name),
                "trait_name": trait_name,
                "std_value": std_value,
                "unit_name": "",
                "observation_id": "",
                "dataset_id": f"LEDA-{SOURCE_NAME}",
            }
        )

    return records


def _leda_trait_to_id(trait_name: str) -> int:
    """Map LEDA trait names to pseudo-TRY IDs.

    Args:
        trait_name: LEDA trait name.

    Returns:
        Integer pseudo-trait ID.

    """
    mapping: dict[str, int] = {
        "SLA": 3117,
        "plant_height": 3106,
        "seed_mass": 26,
        "LDMC": 146,
    }
    return mapping.get(trait_name, 9999)


def _empty_leda_frame() -> pl.DataFrame:
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
