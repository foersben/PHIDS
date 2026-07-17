# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Pherobase VOC ingest client.

Data source
-----------
- Database: The Pherobase
- License:  Academic use permitted
- URL:      https://www.pherobase.com
- Citation: El-Sayed, A.M. (2014). The Pherobase: Database of Pheromones and
            Semiochemicals. https://www.pherobase.com

Usage constraint
----------------
Raw data from the Pherobase MAY NOT be redistributed verbatim.
Only DERIVED PARAMETERS (diffusion_coefficient, repellent_walk_ticks) may
appear in the compiled bio_database.json.  The manifest records:
  - the compound name and access URL
  - the raw molecular weight and vapor pressure (the inputs)
  - the derived diffusion coefficient (the output)

This design ensures we never redistribute Pherobase text, only our own
derived normalised values computed from publicly available physical chemistry
constants.

Cross-reference
---------------
Molecular weights and vapor pressures for common plant VOCs are additionally
verified against the NIST WebBook (Public Domain, US Government).
  URL: https://webbook.nist.gov/chemistry/

Purpose
-------
Extracts molecular weight and vapor pressure for key plant-emitted volatile
organic compounds (VOCs) to derive the spatial diffusion coefficients used in
the reaction-diffusion PDE layer of the simulation engine.

Physical chemistry
------------------
The diffusion coefficient D is approximated using the simplified
Wilke-Lee modification of the Chapman-Enskog equation:

    D ∝ 1 / sqrt(M_compound)

where M_compound is the molecular weight in g/mol.  Lighter molecules
diffuse faster.  This is normalised to [0.01, 0.9] for the engine.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path

import polars as pl

logger = logging.getLogger(__name__)

CACHE_PATH = Path(__file__).parent.parent / "cache" / "pherobase_raw.parquet"

# Key plant-emitted VOCs relevant to herbivore-induced plant signalling.
# Physical data sourced from Pherobase + NIST WebBook cross-reference.
# Molecular weights in g/mol; vapor pressures in mmHg at 25°C.
#
# References per compound:
# - alpha-pinene: NIST WebBook CAS 80-56-8
# - beta-caryophyllene: Pherobase ID phero3432; NIST CAS 87-44-5
# - (Z)-3-hexenyl acetate: Pherobase ID phero2281; NIST CAS 3681-71-8
# - methyl salicylate: NIST WebBook CAS 119-36-8 (systemic signal)
# - linalool: NIST WebBook CAS 78-70-6
# - indole: Pherobase; NIST CAS 120-72-9
# - (E)-beta-farnesene: Pherobase (aphid alarm pheromone + plant VOC)
PHEROBASE_VOC_TABLE: list[dict[str, object]] = [
    {
        "compound_name": "alpha-pinene",
        "molecular_weight_g_mol": 136.23,
        "vapor_pressure_mmhg_25c": 4.75,
        "emission_context": "constitutive_terpenoid",
        "plant_association": ["Pinus sylvestris", "Abies alba", "Picea abies", "Taxus baccata"],
        "pherobase_url": "https://www.pherobase.com/database/compound/compounds-detail-alpha-pinene.php",
        "nist_url": "https://webbook.nist.gov/cgi/cbook.cgi?ID=80-56-8",
    },
    {
        "compound_name": "beta-caryophyllene",
        "molecular_weight_g_mol": 204.35,
        "vapor_pressure_mmhg_25c": 0.004,
        "emission_context": "herbivore_induced_sesquiterpene",
        "plant_association": [
            "Trifolium repens",
            "Urtica dioica",
            "Betula pendula",
            "Quercus robur",
            "Fagus sylvatica",
        ],
        "pherobase_url": "https://www.pherobase.com/database/compound/compounds-detail-beta-caryophyllene.php",
        "nist_url": "https://webbook.nist.gov/cgi/cbook.cgi?ID=87-44-5",
    },
    {
        "compound_name": "(Z)-3-hexenyl acetate",
        "molecular_weight_g_mol": 142.20,
        "vapor_pressure_mmhg_25c": 0.71,
        "emission_context": "herbivore_induced_green_leaf_volatile",
        "plant_association": [
            "Trifolium repens",
            "Lolium perenne",
            "Plantago lanceolata",
            "Rumex acetosa",
            "Molinia caerulea",
        ],
        "pherobase_url": "https://www.pherobase.com/database/compound/compounds-detail-z-3-hexenyl-acetate.php",
        "nist_url": "https://webbook.nist.gov/cgi/cbook.cgi?ID=3681-71-8",
    },
    {
        "compound_name": "methyl salicylate",
        "molecular_weight_g_mol": 152.15,
        "vapor_pressure_mmhg_25c": 0.1,
        "emission_context": "systemic_jasmonate_signal",
        "plant_association": [
            "Betula pendula",
            "Populus tremula",
            "Salix caprea",
            "Quercus robur",
            "Calluna vulgaris",
        ],
        "pherobase_url": "https://www.pherobase.com/database/compound/compounds-detail-methyl-salicylate.php",
        "nist_url": "https://webbook.nist.gov/cgi/cbook.cgi?ID=119-36-8",
    },
    {
        "compound_name": "linalool",
        "molecular_weight_g_mol": 154.25,
        "vapor_pressure_mmhg_25c": 0.16,
        "emission_context": "herbivore_induced_monoterpene_alcohol",
        "plant_association": [
            "Calluna vulgaris",
            "Crataegus monogyna",
            "Rosa canina",
            "Ilex aquifolium",
        ],
        "pherobase_url": "https://www.pherobase.com/database/compound/compounds-detail-linalool.php",
        "nist_url": "https://webbook.nist.gov/cgi/cbook.cgi?ID=78-70-6",
    },
    {
        "compound_name": "indole",
        "molecular_weight_g_mol": 117.15,
        "vapor_pressure_mmhg_25c": 0.068,
        "emission_context": "herbivore_induced_indole",
        "plant_association": [
            "Zea mays",
            "Arabidopsis thaliana",
        ],
        "pherobase_url": "https://www.pherobase.com/database/compound/compounds-detail-indole.php",
        "nist_url": "https://webbook.nist.gov/cgi/cbook.cgi?ID=120-72-9",
    },
    {
        "compound_name": "(E)-beta-farnesene",
        "molecular_weight_g_mol": 204.35,
        "vapor_pressure_mmhg_25c": 0.003,
        "emission_context": "aphid_alarm_and_plant_voc",
        "plant_association": [
            "Betula pendula",
            "Populus tremula",
        ],
        "pherobase_url": "https://www.pherobase.com/database/compound/compounds-detail-e-beta-farnesene.php",
        "nist_url": "https://webbook.nist.gov/cgi/cbook.cgi?ID=18794-84-8",
    },
]

# Physical bounds for normalisation (from the full VOC literature range)
_MW_MIN = 50.0  # lightest plant VOCs (e.g. ethylene: 28 g/mol)
_MW_MAX = 400.0  # heaviest sesqui/diterpene signals


def fetch_pherobase(force_refresh: bool = False) -> pl.DataFrame:
    """Load VOC physical chemistry data and derive diffusion coefficients.

    Because the Pherobase prohibits verbatim redistribution, this client
    uses a curated, literature-verified parameter table rather than scraping.
    Physical data is cross-checked against NIST WebBook (Public Domain).

    Args:
        force_refresh: Re-derive even if cache exists.

    Returns:
        Polars DataFrame with columns: compound_name, molecular_weight_g_mol,
        vapor_pressure_mmhg_25c, diffusion_coefficient, emission_context,
        plant_association (List[str]).

    """
    if CACHE_PATH.exists() and not force_refresh:
        logger.info("Pherobase: loading from cache %s", CACHE_PATH)
        return pl.read_parquet(CACHE_PATH)

    records = []
    for voc in PHEROBASE_VOC_TABLE:
        mw = float(voc["molecular_weight_g_mol"])  # type: ignore[arg-type]
        diff_coeff = _derive_diffusion_coefficient(mw)
        records.append(
            {
                "compound_name": voc["compound_name"],
                "molecular_weight_g_mol": mw,
                "vapor_pressure_mmhg_25c": float(voc["vapor_pressure_mmhg_25c"]),  # type: ignore[arg-type]
                "diffusion_coefficient": diff_coeff,
                "emission_context": voc["emission_context"],
                "plant_associations": "|".join(voc["plant_association"]),  # type: ignore[arg-type]
                "pherobase_url": voc["pherobase_url"],
                "nist_url": voc["nist_url"],
            }
        )

    df = pl.DataFrame(records)

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(CACHE_PATH)
    logger.info("Pherobase: cached %d VOC records to %s", len(df), CACHE_PATH)
    return df


def _derive_diffusion_coefficient(molecular_weight_g_mol: float) -> float:
    """Compute normalised diffusion coefficient from molecular weight.

    Uses an inverse-sqrt relationship (Chapman-Enskog approximation):
        D ∝ 1 / sqrt(M)

    Normalised to [0.01, 0.90] using the empirical VOC MW range [50, 400].

    Args:
        molecular_weight_g_mol: Molecular weight in g/mol.

    Returns:
        Normalised diffusion coefficient in [0.01, 0.90].

    """
    # Raw diffusion proxy: D ∝ 1/sqrt(M)
    d_raw = 1.0 / math.sqrt(max(molecular_weight_g_mol, 1.0))
    # Compute bounds from MW limits
    d_min = 1.0 / math.sqrt(_MW_MAX)
    d_max = 1.0 / math.sqrt(_MW_MIN)
    # Min-Max normalise to [0.01, 0.90]
    d_norm = (d_raw - d_min) / (d_max - d_min) * (0.90 - 0.01) + 0.01
    return round(max(0.01, min(0.90, d_norm)), 4)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = fetch_pherobase()
    print(result.select(["compound_name", "molecular_weight_g_mol", "diffusion_coefficient"]))
    print(
        f"\nDiffusion coefficient range: [{result['diffusion_coefficient'].min():.3f}, "
        f"{result['diffusion_coefficient'].max():.3f}]"
    )
