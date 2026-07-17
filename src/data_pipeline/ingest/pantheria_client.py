# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""PanTHERIA ingest client.

Data source
-----------
- Database: PanTHERIA (Wilson & Reeder 2005 compilation)
- License:  CC0 1.0 Public Domain
- DOI:      https://doi.org/10.1890/08-1494.1
- Citation: Jones et al. (2009). Ecology, 90(9), 2648.

Columns extracted
-----------------
The raw TSV uses numeric column prefixes (e.g. "5-1_AdultBodyMass_g").
Only the columns required for ECS parameter derivation are retained:

| PanTHERIA column            | Engine parameter          |
|-----------------------------|---------------------------|
| 5-1_AdultBodyMass_g         | consumption_rate (log)    |
| 18-1_BasalMetRate_mLO2hr    | metabolism_upkeep         |
| 25-1_WeaningAge_d           | reproduction_energy_divisor |
| 10-1_PopulationGrpSize      | split_population_threshold |
| 1-1_ActivityCycle           | (metadata filter)         |
| MSW05_Order / MSW05_Family  | taxonomic clade grouping  |

Missing values
--------------
PanTHERIA uses -999.0 as a sentinel for missing data.  These are replaced with
``None`` immediately on load so that downstream KNN imputation handles them.

Scope
-----
The client downloads **all** mammalian species (>5000 rows) to allow the
K-Nearest Neighbours imputer to draw on the full phylogenetic neighbourhood.
The archetype extractor later filters to ecologically relevant herbivore clades.
"""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
import polars as pl

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PANTHERIA_URL = "https://esapubs.org/archive/ecol/E090/184/PanTHERIA_1-0_WR05_Aug2008.txt"

CACHE_PATH = Path(__file__).parent.parent / "cache" / "pantheria_raw.parquet"

# PanTHERIA sentinel value for missing data
_MISSING_SENTINEL = -999.0

COLUMNS_OF_INTEREST = [
    "MSW05_Binomial",  # species name (Genus species)
    "MSW05_Order",
    "MSW05_Family",
    "5-1_AdultBodyMass_g",
    "18-1_BasalMetRate_mLO2hr",
    "25-1_WeaningAge_d",
    "10-1_PopulationGrpSize",
    "1-1_ActivityCycle",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_pantheria(force_refresh: bool = False) -> pl.DataFrame:
    """Download and cache the PanTHERIA mammal life-history dataset.

    Uses a local Parquet cache to avoid repeated large downloads.  Pass
    ``force_refresh=True`` to re-download from the canonical Ecological
    Archives URL.

    Args:
        force_refresh: If True, re-download even if the cache file exists.

    Returns:
        A Polars DataFrame containing the selected life-history columns with
        ``-999.0`` sentinels replaced by ``null``.

    Raises:
        httpx.HTTPStatusError: If the download request fails.

    """
    if CACHE_PATH.exists() and not force_refresh:
        logger.info("PanTHERIA: loading from cache %s", CACHE_PATH)
        return pl.read_parquet(CACHE_PATH)

    logger.info("PanTHERIA: downloading from %s", PANTHERIA_URL)
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        response = client.get(PANTHERIA_URL)
        response.raise_for_status()

    df = _parse_pantheria_tsv(response.text)
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(CACHE_PATH)
    logger.info("PanTHERIA: cached %d species rows to %s", len(df), CACHE_PATH)
    return df


# ---------------------------------------------------------------------------
# Internal parsing
# ---------------------------------------------------------------------------


def _parse_pantheria_tsv(raw_text: str) -> pl.DataFrame:
    """Parse the raw PanTHERIA tab-separated text into a clean Polars DataFrame.

    Args:
        raw_text: The raw response body from the PanTHERIA TSV endpoint.

    Returns:
        Cleaned Polars DataFrame with null-substituted missing values.

    """
    import io

    # Read with polars from in-memory buffer
    df_full = pl.read_csv(
        io.StringIO(raw_text),
        separator="\t",
        null_values=["-999", "-999.0", "NA"],
        infer_schema_length=500,
    )

    # Normalise column names (strip whitespace)
    df_full = df_full.rename({c: c.strip() for c in df_full.columns})

    # Select only columns of interest that exist in the actual file
    available = [c for c in COLUMNS_OF_INTEREST if c in df_full.columns]
    missing_cols = set(COLUMNS_OF_INTEREST) - set(available)
    if missing_cols:
        logger.warning("PanTHERIA: expected columns not found: %s", missing_cols)

    df = df_full.select(available)

    # Replace remaining -999 / -999.0 sentinels that polars may not catch
    float_cols = [c for c in df.columns if df[c].dtype in (pl.Float64, pl.Float32)]
    for col in float_cols:
        df = df.with_columns(pl.when(pl.col(col) == _MISSING_SENTINEL).then(None).otherwise(pl.col(col)).alias(col))

    # Drop rows with no binomial name (degenerate header artefacts)
    if "MSW05_Binomial" in df.columns:
        df = df.filter(pl.col("MSW05_Binomial").is_not_null())

    logger.info("PanTHERIA: parsed %d species with %d columns", len(df), len(df.columns))
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = fetch_pantheria()
    print(result.head(10))
    print(f"Shape: {result.shape}")
    print(f"Null counts:\n{result.null_count()}")
