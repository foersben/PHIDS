# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""DuckDB persistence layer for the PHIDS empirical database.

Provides schema DDL, Polars bulk insertion, JSON export for engine
compatibility, and convenience query helpers for API/UI endpoints.
"""

from data_pipeline.db.export import export_bio_database_json, publish_to_huggingface
from data_pipeline.db.query import BioQuery
from data_pipeline.db.schema import DB_PATH, create_schema, open_connection
from data_pipeline.db.writer import write_all

__all__ = [
    "DB_PATH",
    "BioQuery",
    "create_schema",
    "export_bio_database_json",
    "open_connection",
    "publish_to_huggingface",
    "write_all",
]
