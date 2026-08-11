# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit test suite for scenario loader validation, JSON serialization, and error branches."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from phids.io.scenario import (
    load_scenario_from_dict,
    load_scenario_from_json,
    scenario_to_json,
)


def test_load_scenario_from_dict_validation_error() -> None:
    """Verify load_scenario_from_dict raises ValidationError on invalid parameters."""
    invalid_dict = {"grid_width": -10, "grid_height": 40}
    with pytest.raises(ValidationError):
        load_scenario_from_dict(invalid_dict)


def test_load_scenario_from_json_root_not_object() -> None:
    """Verify load_scenario_from_json raises ValueError when JSON root is a list."""
    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = Path(tmpdir) / "array_root.json"
        json_path.write_text("[1, 2, 3]", encoding="utf-8")

        with pytest.raises(ValueError, match=r"Scenario JSON root must be an object"):
            load_scenario_from_json(json_path)


def test_scenario_to_json_file_output() -> None:
    """Verify scenario_to_json serializes and writes to destination file path."""
    from phids.api.ui_state.state import DraftState

    config = DraftState.default().build_sim_config()
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "exported_scenario.json"
        json_str = scenario_to_json(config, path=out_path)

        assert isinstance(json_str, str)
        assert out_path.exists()

        reloaded = load_scenario_from_json(out_path)
        assert reloaded.grid_width == config.grid_width
        assert reloaded.grid_height == config.grid_height
