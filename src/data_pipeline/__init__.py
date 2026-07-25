# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""PHIDS Empirical Database ETL Pipeline.

This package ingests ecological trait data from open-access scientific databases,
aligns it taxonomically, normalises it into engine-compatible float bounds, clusters
it into archetypes, and compiles a validated ``bio_database.json`` payload.

Data sources and their licenses:
- TRY Plant Trait Database: CC-BY 4.0 (https://www.try-db.org)
- Global Biotic Interactions (GLoBI): CC-BY 4.0 (https://globalbioticinteractions.org)
- PanTHERIA: CC0 / Public Domain (https://doi.org/10.1890/08-1494.1)
- Dr. Duke's Phytochemical DB: CC0 / Public Domain (USDA ARS)
- ToxValDB: Open Government Data / CC0 (EPA)
- Pherobase: Academic use (www.pherobase.com)
- GBIF: CC0 (https://www.gbif.org)
- Animal Diversity Web (ADW): CC-BY-NC (University of Michigan - data used only for
  parameter derivation, not redistributed verbatim)

All CC-BY sources must retain their citation in ``manifest.json`` produced alongside
the compiled database.
"""

from data_pipeline.run_all import run_all

__all__ = ["run_all"]
