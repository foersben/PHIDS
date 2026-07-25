# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Ingest sub-package.

Each client module in this package is responsible for fetching raw trait data
from one upstream scientific database and persisting it as a Polars DataFrame
cached in Parquet format under ``src/data_pipeline/cache/``.

Clients are intentionally stateless: they fetch, validate column presence, and
write.  No transformation or normalisation occurs here.
"""

from data_pipeline.ingest.drduke_client import fetch_drduke
from data_pipeline.ingest.globi_client import fetch_globi
from data_pipeline.ingest.pantheria_client import fetch_pantheria
from data_pipeline.ingest.pherobase_client import fetch_pherobase
from data_pipeline.ingest.try_client import fetch_try

__all__ = [
    "fetch_drduke",
    "fetch_globi",
    "fetch_pantheria",
    "fetch_pherobase",
    "fetch_try",
]
