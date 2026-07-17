# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Provenance ledger for the PHIDS empirical database ETL pipeline.

Every record produced by any ingest client MUST carry a ``ProvenanceRecord``
through the entire pipeline.  At the end of the pipeline the ledger is
written into the DuckDB ``provenance`` table and also exported as
``manifest.json`` for Hugging Face Hub upload.

License interoperability summary
---------------------------------
- CC0 sources (PanTHERIA, Dr. Duke's, ToxValDB, GBIF):
    No attribution legally required; DOI/URL retained for reproducibility.
- CC-BY 4.0 sources (TRY, GLoBI):
    Citation string and DOI MUST appear in ``manifest.json`` and any public
    release of bio_database.json or bio_database.duckdb.
- Academic-use sources (Pherobase, ADW):
    Raw values may be used for parameter derivation; verbatim redistribution
    of the source text is prohibited.  Only derived parameters are stored.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

import polars as pl


@dataclass(frozen=True)
class ProvenanceRecord:
    """An immutable attribution record for a single data point.

    Attributes:
        species_canonical: GBIF-resolved canonical species name.
        source_db: Human-readable database name.
        source_license: SPDX license identifier or descriptive string.
        source_doi: DOI or stable URL for the originating dataset.
        source_citation: Full bibliographic citation (required for CC-BY sources).
        access_date: ISO-8601 date the data was fetched.
        raw_trait_key: The original column/trait name in the source database.
        raw_trait_value: The original, unscaled value (float or None).
        derived_param: The engine parameter name this value maps to.
        derived_value: The normalised float value after transformation.
    """

    species_canonical: str
    source_db: str
    source_license: str
    source_doi: str
    source_citation: str
    access_date: str
    raw_trait_key: str
    raw_trait_value: float | None
    derived_param: str
    derived_value: float


# ---------------------------------------------------------------------------
# Per-source citation strings (CC-BY compliance)
# ---------------------------------------------------------------------------

CITATIONS: dict[str, dict[str, str]] = {
    "TRY": {
        "license": "CC-BY 4.0",
        "doi": "https://doi.org/10.1111/gcb.14904",
        "citation": (
            "Kattge, J., Bonisch, G., Diaz, S., et al. (2020). TRY plant trait database"
            " - enhanced coverage and open access. Global Change Biology, 26(1), 119-188."
            " https://doi.org/10.1111/gcb.14904"
        ),
    },
    "GLoBI": {
        "license": "CC-BY 4.0",
        "doi": "https://doi.org/10.1016/j.ecoinf.2014.08.005",
        "citation": (
            "Poelen, J.H., Simons, J.D., Mungall, C.J. (2014). Global biotic interactions:"
            " An open infrastructure to share and analyze species-interaction datasets."
            " Ecological Informatics, 24, 148-159."
            " https://doi.org/10.1016/j.ecoinf.2014.08.005"
        ),
    },
    "PanTHERIA": {
        "license": "CC0 1.0",
        "doi": "https://doi.org/10.1890/08-1494.1",
        "citation": (
            "Jones, K.E., Bielby, J., Cardillo, M., et al. (2009). PanTHERIA:"
            " a species-level database of life history, ecology, and geography of extant"
            " and recently extinct mammals. Ecology, 90(9), 2648."
            " https://doi.org/10.1890/08-1494.1"
        ),
    },
    "DrDuke": {
        "license": "CC0 (Public Domain - USDA ARS)",
        "doi": "https://phytochem.nal.usda.gov",
        "citation": (
            "Duke, J.A. (2010). Dr. Duke's Phytochemical and Ethnobotanical Databases."
            " USDA Agricultural Research Service. https://phytochem.nal.usda.gov"
        ),
    },
    "ToxValDB": {
        "license": "Open Government Data / CC0 (US EPA)",
        "doi": "https://doi.org/10.1093/toxsci/kfac097",
        "citation": (
            "Wignall, J., et al. (2022). ToxValDB: Bringing together animal and human"
            " toxicological data for risk assessment. Toxicological Sciences, 190(2)."
            " https://doi.org/10.1093/toxsci/kfac097"
        ),
    },
    "Pherobase": {
        "license": "Academic Use Only - derived parameters only, not redistributed",
        "doi": "https://www.pherobase.com",
        "citation": (
            "El-Sayed, A.M. (2014). The Pherobase: Database of Pheromones and Semiochemicals. https://www.pherobase.com"
        ),
    },
    "GBIF": {
        "license": "CC0 1.0",
        "doi": "https://doi.org/10.15468/dl.gbif",
        "citation": (
            "GBIF Secretariat (2023). GBIF Backbone Taxonomy."
            " Checklist dataset https://doi.org/10.15468/39omei via GBIF.org."
        ),
    },
    "ADW": {
        "license": "CC-BY-NC 4.0 (University of Michigan)",
        "doi": "https://animaldiversity.org",
        "citation": (
            "Myers, P., Espinosa, R., Parr, C.S., Jones, T., Hammond, G.S., Dewey, T.A. (2025)."
            " The Animal Diversity Web. University of Michigan Museum of Zoology."
            " https://animaldiversity.org"
        ),
    },
    # -------------------------------------------------------------------------
    # CC-BY 4.0 sources - compatible with Commercial License
    # -------------------------------------------------------------------------
    "AusTraits": {
        "license": "CC-BY 4.0",
        "doi": "https://doi.org/10.1038/s41597-021-01006-6",
        "citation": (
            "Falster, D., Gallagher, R., Wenk, E.H., et al. (2021). AusTraits, a curated plant"
            " trait database for the Australian flora. Scientific Data, 8, 254."
            " https://doi.org/10.1038/s41597-021-01006-6"
        ),
        "note": "Fallback for TRY when API is unavailable. Compatible with Commercial License.",
    },
    # -------------------------------------------------------------------------
    # EXTENDED DATASET ONLY - NC-licensed sources
    # These MUST NOT appear in the core pipeline provenance table.
    # The publish guard in export.py will raise RuntimeError if they do.
    # -------------------------------------------------------------------------
    "BIEN": {
        "license": "CC-BY-NC-ND 4.0 - NON-COMMERCIAL, NO DERIVATIVES",
        "doi": "https://doi.org/10.1111/2041-210X.12861",
        "citation": (
            "Maitner, B.S., et al. (2018). The bien r package: A tool to access the Botanical"
            " Information and Ecology Network (BIEN) database."
            " Methods in Ecology and Evolution, 9(2), 373-379."
            " https://doi.org/10.1111/2041-210X.12861"
        ),
        "note": "EXTENDED DATASET ONLY. Incompatible with Proprietary Commercial License.",
    },
    "LEDA": {
        "license": "Academic Use Only - no explicit open-data license",
        "doi": "https://doi.org/10.1111/j.1365-2745.2008.01430.x",
        "citation": (
            "Kleyer, M., et al. (2008). The LEDA Traitbase: A database of life-history traits"
            " of Northwest European flora. Journal of Ecology, 96(6), 1266-1274."
            " https://doi.org/10.1111/j.1365-2745.2008.01430.x"
        ),
        "note": "EXTENDED DATASET ONLY. Mass extraction without written permission is prohibited.",
    },
    "GIFT": {
        "license": "CC-BY-SA 4.0 - SHAREALIKE (derivative works must use same license)",
        "doi": "https://doi.org/10.1111/jbi.13623",
        "citation": (
            "Weigelt, P., et al. (2020). GIFT - A Global Inventory of Floras and Traits for"
            " macroecology and biogeography. Journal of Biogeography, 47(1), 16-43."
            " https://doi.org/10.1111/jbi.13623"
        ),
        "note": (
            "EXTENDED DATASET ONLY. ShareAlike clause requires derivative datasets to also be"
            " CC-BY-SA. Incompatible with Proprietary Commercial License."
        ),
    },
}


def today_iso() -> str:
    """Return today's date in ISO-8601 format."""
    return datetime.date.today().isoformat()


# ---------------------------------------------------------------------------
# In-memory ledger
# ---------------------------------------------------------------------------


class ProvenanceLedger:
    """Accumulates ProvenanceRecords throughout the pipeline.

    Records are held in memory during pipeline execution and flushed to
    DuckDB at the end via ``to_dataframe()``.

    Attributes:
        records: The accumulated list of provenance records.

    """

    def __init__(self) -> None:
        """Initialise an empty ledger."""
        self.records: list[ProvenanceRecord] = []

    def add(self, record: ProvenanceRecord) -> None:
        """Append a record to the ledger.

        Args:
            record: The provenance record to append.

        """
        self.records.append(record)

    def add_many(self, records: list[ProvenanceRecord]) -> None:
        """Bulk-append records to the ledger.

        Args:
            records: List of provenance records to append.

        """
        self.records.extend(records)

    def to_dataframe(self) -> pl.DataFrame:
        """Serialise all accumulated records to a Polars DataFrame.

        The DataFrame schema matches the DuckDB ``provenance`` table exactly
        so it can be passed directly to ``db.writer.write_all()``.

        Returns:
            Polars DataFrame of provenance records.

        """
        if not self.records:
            return pl.DataFrame(
                {
                    "species_canonical": pl.Series([], dtype=pl.Utf8),
                    "source_db": pl.Series([], dtype=pl.Utf8),
                    "source_license": pl.Series([], dtype=pl.Utf8),
                    "source_doi": pl.Series([], dtype=pl.Utf8),
                    "source_citation": pl.Series([], dtype=pl.Utf8),
                    "access_date": pl.Series([], dtype=pl.Utf8),
                    "raw_trait_key": pl.Series([], dtype=pl.Utf8),
                    "raw_trait_value": pl.Series([], dtype=pl.Float64),
                    "derived_param": pl.Series([], dtype=pl.Utf8),
                    "derived_value": pl.Series([], dtype=pl.Float64),
                }
            )

        return pl.DataFrame(
            [
                {
                    "species_canonical": r.species_canonical,
                    "source_db": r.source_db,
                    "source_license": r.source_license,
                    "source_doi": r.source_doi,
                    "source_citation": r.source_citation,
                    "access_date": r.access_date,
                    "raw_trait_key": r.raw_trait_key,
                    "raw_trait_value": r.raw_trait_value,
                    "derived_param": r.derived_param,
                    "derived_value": r.derived_value,
                }
                for r in self.records
            ]
        )
