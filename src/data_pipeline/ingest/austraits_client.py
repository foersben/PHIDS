# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""AusTraits plant trait database ingest client.

Data source
-----------
- Database: AusTraits - A curated plant trait database for the Australian flora
- License:  CC-BY 4.0
- DOI:      https://doi.org/10.1038/s41597-021-01006-6
- Citation: Falster, D., Gallagher, R., Wenk, E.H., et al. (2021). AusTraits,
            a curated plant trait database for the Australian flora.
            Scientific Data, 8, 254. https://doi.org/10.1038/s41597-021-01006-6

Attribution requirement (CC-BY 4.0)
------------------------------------
The citation above MUST be preserved in the pipeline manifest.json and in any
public release of the compiled bio_database.json. Compatible with both EUPL-1.2
and the PHIDS Proprietary Commercial License.

Fallback role
-------------
This client is invoked automatically by ``fetch_try_or_fallback()`` in
``try_client.py`` when the TRY REST API is unavailable (404/5xx).

AusTraits provides overlapping trait coverage for many cosmopolitan and
introduced species that appear in European ecosystems, including all grass,
legume, and woody categories covered by the TRY target species list.

Data access
-----------
AusTraits releases are published on Zenodo. This client fetches the latest
stable release (5.0.0) CSV directly from Zenodo. The traits CSV is cached
locally as ``cache/austraits_raw.parquet`` after the first download.

Download URL:
  https://zenodo.org/records/10434669/files/austraits-5.0.0.zip

Traits extracted
----------------
| AusTraits trait name         | TRY TraitID equivalent | Engine parameter          |
|------------------------------|------------------------|---------------------------|
| leaf_mass_per_area           | 3117 (SLA)             | growth_rate               |
| seed_dry_mass                | 26                     | max_energy (partial)      |
| plant_height                 | 3106                   | max_energy (partial)      |
| leaf_dry_matter_content      | 146 (LDMC)             | digestibility_modifier    |
| leaf_N_per_dry_mass          | 50 (supporting)        | (supporting)              |
| wood_density                 | (bonus - no TRY equiv) | digestibility_modifier    |
"""

from __future__ import annotations

import io
import logging
import zipfile
from pathlib import Path

import httpx
import polars as pl

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ZENODO_URL = "https://zenodo.org/records/10434669/files/austraits-5.0.0.zip"
CACHE_PATH = Path(__file__).parent.parent / "cache" / "austraits_raw.parquet"

# AusTraits trait names that map to our engine parameters
TRAIT_MAP: dict[str, str] = {
    "leaf_mass_per_area": "sla_cm2_per_g",
    "seed_dry_mass": "seed_dry_mass_g",
    "plant_height": "height_cm",
    "leaf_dry_matter_content": "lignin_pct",  # proxy: high LDMC correlates with high structural investment
    "wood_density": "lignin_pct",  # secondary proxy for digestibility
}

# Only fetch these AusTraits trait names
TARGET_TRAITS: frozenset[str] = frozenset(TRAIT_MAP.keys())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_austraits(force_refresh: bool = False) -> pl.DataFrame:
    """Fetch plant trait data from the AusTraits Zenodo release.

    Downloads the AusTraits 5.0.0 release ZIP from Zenodo, extracts the
    ``traits.csv`` file, filters to the relevant trait names, and returns
    a DataFrame with the same schema as ``fetch_try()`` for drop-in
    compatibility.

    Args:
        force_refresh: Re-download from Zenodo even if cache exists.

    Returns:
        A Polars DataFrame with columns: species_name, trait_id, trait_name,
        std_value, unit_name, observation_id, dataset_id.

    """
    if CACHE_PATH.exists() and not force_refresh:
        logger.info("AusTraits: loading from cache %s", CACHE_PATH)
        return pl.read_parquet(CACHE_PATH)

    logger.info("AusTraits: downloading from Zenodo %s", ZENODO_URL)

    try:
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            response = client.get(ZENODO_URL)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning("AusTraits: download failed: %s", exc)
        return _empty_austraits_frame()
    except httpx.RequestError as exc:
        logger.warning("AusTraits: network error: %s", exc)
        return _empty_austraits_frame()

    logger.info("AusTraits: downloaded %d bytes, extracting traits.csv", len(response.content))

    try:
        df = _extract_and_parse(response.content)
    except Exception as exc:
        logger.warning("AusTraits: parse error: %s", exc)
        return _empty_austraits_frame()

    if df.is_empty():
        logger.warning("AusTraits: no trait records extracted - check trait name mapping")
        return _empty_austraits_frame()

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(CACHE_PATH)
    logger.info(
        "P1.2 Plant traits (%s CC-BY 4.0): %d trait records, %d species",
        "AusTraits",
        len(df),
        df["species_name"].n_unique(),
    )
    return df


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_and_parse(zip_bytes: bytes) -> pl.DataFrame:
    """Extract traits.csv from the ZIP archive and parse into engine schema.

    Args:
        zip_bytes: Raw ZIP file bytes from Zenodo.

    Returns:
        Polars DataFrame with TRY-compatible schema.

    """
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        # Find traits.csv inside the ZIP (may be in a subdirectory)
        traits_file = next((n for n in zf.namelist() if n.endswith("traits.csv")), None)
        if traits_file is None:
            logger.warning("AusTraits: traits.csv not found in ZIP archive")
            return _empty_austraits_frame()

        with zf.open(traits_file) as fh:
            raw = pl.read_csv(
                fh,
                infer_schema_length=10000,
                ignore_errors=True,
            )

    return _transform_to_try_schema(raw)


def _transform_to_try_schema(raw: pl.DataFrame) -> pl.DataFrame:
    """Transform raw AusTraits traits.csv into the TRY-compatible schema.

    AusTraits columns of interest:
      - taxon_name: species binomial
      - trait_name: AusTraits trait identifier
      - value: the measured value (string, needs numeric filter)
      - unit: measurement unit
      - observation_id: observation identifier

    Args:
        raw: Raw AusTraits DataFrame from the traits.csv file.

    Returns:
        TRY-schema DataFrame with engine-mapped trait names.

    """
    required = {"taxon_name", "trait_name", "value"}
    if not required.issubset(set(raw.columns)):
        logger.warning("AusTraits: expected columns %s, got %s", required, set(raw.columns))
        return _empty_austraits_frame()

    # Filter to relevant traits only
    filtered = raw.filter(pl.col("trait_name").is_in(list(TARGET_TRAITS)))
    if filtered.is_empty():
        return _empty_austraits_frame()

    records: list[dict[str, object]] = []
    for row in filtered.to_dicts():
        raw_val = str(row.get("value", "")).strip()
        try:
            std_value = float(raw_val)
        except ValueError:
            continue

        original_trait = str(row.get("trait_name", ""))

        # SLA in AusTraits is typically in mm2/mg = cm2/g (same scale as TRY 3117)
        # Height in AusTraits is in m, TRY is in m too for trait 3106 (veg height)
        # Seed mass in AusTraits is in mg, TRY trait 26 is in mg

        records.append(
            {
                "species_name": str(row.get("taxon_name", "")).strip(),
                "trait_id": _trait_name_to_id(original_trait),
                "trait_name": original_trait,
                "std_value": std_value,
                "unit_name": str(row.get("unit", "")).strip() if row.get("unit") else "",
                "observation_id": str(row.get("observation_id", "")).strip(),
                "dataset_id": "AusTraits-5.0.0",
            }
        )

    if not records:
        return _empty_austraits_frame()

    return pl.DataFrame(records)


def _trait_name_to_id(trait_name: str) -> int:
    """Map AusTraits trait names to pseudo-TRY IDs for schema compatibility.

    Args:
        trait_name: AusTraits trait name string.

    Returns:
        Integer pseudo-trait ID matching the TRY numbering convention.

    """
    _mapping: dict[str, int] = {
        "leaf_mass_per_area": 3117,
        "seed_dry_mass": 26,
        "plant_height": 3106,
        "leaf_dry_matter_content": 146,
        "leaf_N_per_dry_mass": 55,
        "wood_density": 163,  # maps to leaf_tensile_n_mm2 slot as structural proxy
    }
    return _mapping.get(trait_name, 9999)


def _empty_austraits_frame() -> pl.DataFrame:
    """Return an empty DataFrame with the TRY-compatible schema.

    Returns:
        Empty Polars DataFrame matching the TRY output schema.

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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = fetch_austraits()
    print(result.head(20))
    print(f"Shape: {result.shape}")
    print(f"Unique traits: {result['trait_name'].unique().to_list()}")
    print(f"Unique species: {result['species_name'].n_unique()}")
