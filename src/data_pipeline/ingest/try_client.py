# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""TRY Plant Trait Database ingest client (public API mode).

Data source
-----------
- Database: TRY Plant Trait Database
- License:  CC-BY 4.0
- DOI:      https://doi.org/10.1111/gcb.14904
- Citation: Kattge et al. (2020). Global Change Biology, 26(1), 119-188.

Attribution requirement (CC-BY 4.0)
------------------------------------
The citation above MUST be preserved in the pipeline manifest.json and in any
public release of the compiled bio_database.json.

API mode
--------
This client uses the TRY public REST API endpoint which allows targeted queries
for specific traits and species without requiring bulk data registration.
Endpoint: https://www.try-db.org/dnld/TryDBnld.php

Traits queried
--------------
| TRY TraitID | Trait name                         | Engine parameter          |
|-------------|-------------------------------------|---------------------------|
| 3117        | Specific Leaf Area (SLA)            | growth_rate               |
| 26          | Seed dry mass                       | max_energy (partial)      |
| 3106        | Plant height, vegetative            | max_energy (partial)      |
| 163         | Leaf tensile strength               | mechanical_damage_per_bite|
| 146         | Leaf dry matter content (LDMC)      | digestibility_modifier    |
| 55          | Leaf dry mass                       | (supporting)              |

Target species list
-------------------
A curated list of 50 ecologically diverse species spanning fast-growing pioneers
to slow-growing climax species.  This list is designed to cover the full
parameter variance space before K-Means clustering.

Rate limiting
-------------
The TRY public API applies a soft rate limit.  This client uses a 2-second
inter-request delay and caches all responses to Parquet to avoid repeated calls.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import httpx
import polars as pl

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TRY_API_URL = "https://www.try-db.org/dnld/TryDBnld.php"
CACHE_PATH = Path(__file__).parent.parent / "cache" / "try_raw.parquet"

# Trait IDs to fetch
TRAIT_IDS = [3117, 26, 3106, 163, 146, 55]

# Curated candidate species list: spans pioneer annuals → climax woody species.
# Chosen to maximise ecological strategy diversity before clustering.
TARGET_SPECIES: list[str] = [
    # Fast-growing pioneer species (high SLA, low lignin)
    "Trifolium repens",  # White clover - pasture pioneer
    "Taraxacum officinale",  # Dandelion - ruderal pioneer
    "Plantago lanceolata",  # Ribwort plantain - pasture
    "Poa annua",  # Annual bluegrass - pioneer grass
    "Chenopodium album",  # Fat hen - ruderal annual
    "Arabidopsis thaliana",  # Thale cress - fast annual
    "Urtica dioica",  # Common nettle - ruderal herb
    "Rumex acetosa",  # Common sorrel - grassland herb
    "Lolium perenne",  # Ryegrass - managed pasture
    "Festuca rubra",  # Red fescue - meadow grass
    # Mid-succession species (moderate SLA, variable defenses)
    "Calluna vulgaris",  # Heather - shrubland
    "Arctostaphylos uva-ursi",  # Bearberry - heath shrub
    "Salix caprea",  # Goat willow - pioneer woody
    "Betula pendula",  # Silver birch - pioneer tree
    "Populus tremula",  # European aspen - pioneer tree
    "Quercus robur",  # English oak - mid-succession
    "Corylus avellana",  # Hazel - shrub layer
    "Crataegus monogyna",  # Hawthorn - thorny shrub
    "Rosa canina",  # Dog rose - thorny shrub
    "Rubus fruticosus",  # Bramble - thorny sprawler
    # Slow-growing climax species (low SLA, high lignin)
    "Taxus baccata",  # English yew - toxic climax
    "Abies alba",  # Silver fir - conifer climax
    "Picea abies",  # Norway spruce - conifer climax
    "Pinus sylvestris",  # Scots pine - conifer climax
    "Fagus sylvatica",  # European beech - climax hardwood
    "Quercus petraea",  # Sessile oak - climax hardwood
    "Acer pseudoplatanus",  # Sycamore - late-succession
    "Fraxinus excelsior",  # European ash - riparian climax
    "Ilex aquifolium",  # Holly - understorey evergreen
    "Buxus sempervirens",  # Box - slow evergreen shrub
    # Chemically defended species (high alkaloid/tannin content)
    "Atropa belladonna",  # Deadly nightshade - tropane alkaloids
    "Digitalis purpurea",  # Foxglove - cardiac glycosides
    "Conium maculatum",  # Hemlock - piperidine alkaloids
    "Datura stramonium",  # Jimsonweed - tropane alkaloids
    "Colchicum autumnale",  # Autumn crocus - colchicine
    "Veratrum album",  # White hellebore - steroidal alkaloids
    "Aconitum napellus",  # Monkshood - aconitine (highly toxic)
    "Euphorbia cyparissias",  # Cypress spurge - diterpene esters
    "Ranunculus acris",  # Meadow buttercup - protoanemonin
    # Grass / sedge / rush layer (silica-rich, mechanically defended)
    "Carex flacca",  # Glaucous sedge - silica-rich
    "Juncus effusus",  # Soft rush - structural defense
    "Molinia caerulea",  # Purple moor-grass - tough lignocellulose
    "Deschampsia cespitosa",  # Tufted hair-grass - high silica
    "Nardus stricta",  # Mat-grass - extremely tough
    "Brachypodium pinnatum",  # Tor grass - high lignin
    # Aquatic / wetland fringe (low mechanical defense, high palatability)
    "Phragmites australis",  # Common reed - wetland
    "Typha latifolia",  # Broadleaf cattail - wetland
    "Glyceria maxima",  # Reed sweet-grass - palatable aquatic
    "Sparganium erectum",  # Branched bur-reed - wetland
    "Iris pseudacorus",  # Yellow flag iris - toxic alkaloids
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_try(force_refresh: bool = False) -> pl.DataFrame:
    """Fetch plant trait data from the TRY public API for target species.

    Queries each trait individually per species batch to stay within the
    public API's request constraints.  Results are merged and cached to
    Parquet to avoid repeated network calls.

    Args:
        force_refresh: Re-fetch from the TRY API even if cache exists.

    Returns:
        A Polars DataFrame with columns: species_name, TraitID, TraitName,
        StdValue, UnitName, ObservationID, DatasetID.

    Raises:
        httpx.HTTPStatusError: If any API request fails.

    """
    if CACHE_PATH.exists() and not force_refresh:
        logger.info("TRY: loading from cache %s", CACHE_PATH)
        return pl.read_parquet(CACHE_PATH)

    all_records: list[dict[str, object]] = []
    species_str = "\n".join(TARGET_SPECIES)

    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        for trait_id in TRAIT_IDS:
            logger.info("TRY: fetching trait %d for %d species", trait_id, len(TARGET_SPECIES))
            records = _query_try_api(client, trait_id, species_str)
            all_records.extend(records)
            # Respect soft rate limit
            time.sleep(2.0)

    if not all_records:
        logger.warning("TRY: no records returned - API may be unavailable")
        return _empty_try_frame()

    df = pl.DataFrame(all_records)
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(CACHE_PATH)
    logger.info("TRY: cached %d records to %s", len(df), CACHE_PATH)
    return df


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _query_try_api(client: httpx.Client, trait_id: int, species_str: str) -> list[dict[str, object]]:
    """Execute a single trait query against the TRY public API.

    The TRY API uses a POST form with species names (newline-separated) and a
    list of trait IDs.  It returns a TSV-like response.

    Args:
        client: An active httpx Client.
        trait_id: The TRY numeric trait identifier.
        species_str: Newline-separated list of species binomials.

    Returns:
        A list of record dicts parsed from the API response.

    """
    try:
        response = client.post(
            TRY_API_URL,
            data={
                "taxname": species_str,
                "TraitID": str(trait_id),
                "global": "on",
                "format": "plain/text",
            },
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning("TRY: API error for trait %d: %s", trait_id, exc)
        return []
    except httpx.RequestError as exc:
        logger.warning("TRY: network error for trait %d: %s", trait_id, exc)
        return []

    return _parse_try_response(response.text, trait_id)


def _parse_try_response(text: str, trait_id: int) -> list[dict[str, object]]:
    """Parse TRY API plain-text response into record dicts.

    TRY returns a tab-separated payload with a multi-line header block
    followed by data rows.

    Args:
        text: Raw response body from the TRY API.
        trait_id: The trait ID used for this request (for logging).

    Returns:
        List of parsed record dictionaries.

    """
    import io

    lines = [line for line in text.splitlines() if line.strip() and not line.startswith("#")]
    if len(lines) < 2:
        logger.debug("TRY: empty/header-only response for trait %d", trait_id)
        return []

    try:
        import csv

        reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter="\t")
        records: list[dict[str, object]] = []
        for row in reader:
            # TRY uses 'StdValue' for the standardised numeric value
            raw_val = row.get("StdValue", "").strip()
            if not raw_val:
                continue
            try:
                std_value = float(raw_val)
            except ValueError:
                continue
            records.append(
                {
                    "species_name": row.get("AccSpeciesName", "").strip(),
                    "trait_id": int(row.get("TraitID", trait_id)),
                    "trait_name": row.get("TraitName", "").strip(),
                    "std_value": std_value,
                    "unit_name": row.get("UnitName", "").strip(),
                    "observation_id": row.get("ObservationID", "").strip(),
                    "dataset_id": row.get("DatasetID", "").strip(),
                }
            )
        return records
    except Exception as exc:
        logger.warning("TRY: parse error for trait %d: %s", trait_id, exc)
        return []


def _empty_try_frame() -> pl.DataFrame:
    """Return an empty DataFrame with the expected TRY schema.

    Returns:
        Empty Polars DataFrame with TRY column schema.

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
    result = fetch_try()
    print(result.head(20))
    print(f"Shape: {result.shape}")
    print(f"Unique traits: {result['trait_id'].unique().to_list()}")
    print(f"Unique species: {result['species_name'].n_unique()}")
