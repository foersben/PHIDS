"""Unit checks for scenario helper serialization and deserialization.

This module validates that scenario helper utilities preserve schema-consistent values across
in-memory dict conversion, JSON persistence, and file-backed reload operations.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from phids.api.schemas import SimulationConfig
from phids.io.scenario import load_scenario_from_dict, load_scenario_from_json, scenario_to_json


def test_scenario_helpers_roundtrip_json_file(
    tmp_path: Path,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify scenario helpers preserve config values across dict and JSON round-trips."""
    config = config_builder()
    data = config.model_dump(mode="json")

    loaded_from_dict = load_scenario_from_dict(data)
    assert loaded_from_dict.grid_width == config.grid_width

    out_path = tmp_path / "scenario.json"
    text = scenario_to_json(config, out_path)
    assert out_path.read_text(encoding="utf-8") == text

    loaded_from_file = load_scenario_from_json(out_path)
    assert loaded_from_file.model_dump(mode="json") == config.model_dump(mode="json")
