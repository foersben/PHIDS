"""Scenario I/O: load and validate simulation configurations from JSON/dict sources."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from phytodynamics.api.schemas import SimulationConfig


def load_scenario_from_dict(data: dict[str, Any]) -> SimulationConfig:
    """Parse and validate a simulation configuration from a raw dict.

    Parameters
    ----------
    data:
        Raw configuration mapping (typically decoded from JSON).

    Returns
    -------
    SimulationConfig
        Validated Pydantic configuration instance.

    Raises
    ------
    pydantic.ValidationError
        If the configuration is invalid.
    """
    return SimulationConfig.model_validate(data)


def load_scenario_from_json(path: str | Path) -> SimulationConfig:
    """Load and validate a simulation configuration from a JSON file.

    Parameters
    ----------
    path:
        Path to the JSON scenario file.

    Returns
    -------
    SimulationConfig
        Validated Pydantic configuration instance.
    """
    raw = Path(path).read_text(encoding="utf-8")
    data: dict[str, Any] = json.loads(raw)
    return load_scenario_from_dict(data)


def scenario_to_json(config: SimulationConfig, path: str | Path | None = None) -> str:
    """Serialise a SimulationConfig to JSON.

    Parameters
    ----------
    config:
        Configuration to serialise.
    path:
        Optional file path to write the JSON to.  If None, only the string
        is returned.

    Returns
    -------
    str
        JSON representation of the configuration.
    """
    serialised = config.model_dump_json(indent=2)
    if path is not None:
        Path(path).write_text(serialised, encoding="utf-8")
    return serialised
