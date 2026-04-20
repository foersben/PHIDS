"""Doc-to-contract checks for the `/ws/ui/stream` payload reference documentation."""

from __future__ import annotations

import json
from pathlib import Path


def test_ui_stream_docs_cover_v1_contract_fields_and_column_sets() -> None:
    """UI diagnostics docs mention all v1 top-level fields and columnar table columns."""
    repo_root = Path(__file__).resolve().parents[3]
    docs_text = (repo_root / "docs/technical_architecture/interfaces_and_ui.md").read_text(
        encoding="utf-8"
    )
    snapshot = json.loads(
        (repo_root / "tests/unit/api/fixtures/ui_stream_contract_v1.json").read_text(
            encoding="utf-8"
        )
    )

    missing_top_level = [key for key in snapshot["top_level_keys"] if f"`{key}`" not in docs_text]
    missing_plant_columns = [
        key for key in snapshot["plants_columns"] if f"`{key}`" not in docs_text
    ]
    missing_swarm_columns = [
        key for key in snapshot["swarms_columns"] if f"`{key}`" not in docs_text
    ]

    assert not missing_top_level, "Missing top-level /ws/ui/stream fields in docs: " + ", ".join(
        missing_top_level
    )
    assert not missing_plant_columns, "Missing plants table columns in docs: " + ", ".join(
        missing_plant_columns
    )
    assert not missing_swarm_columns, "Missing swarms table columns in docs: " + ", ".join(
        missing_swarm_columns
    )
