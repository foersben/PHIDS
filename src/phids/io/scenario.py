"""Scenario I/O helpers for loading and serialising SimulationConfig.

This module provides convenience functions to parse and validate
simulation configurations from Python mappings or JSON files.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from phids.api.schemas import SimulationConfig

logger = logging.getLogger(__name__)


def load_scenario_from_dict(data: dict[str, Any]) -> SimulationConfig:
    """Parse and validate a simulation configuration from a mapping.

    Args:
        data: Raw configuration mapping (typically decoded from JSON).

    Returns:
        SimulationConfig: Validated Pydantic configuration instance.

    Raises:
        pydantic.ValidationError: If the configuration is invalid.
    """
    config = SimulationConfig.model_validate(data)
    logger.debug(
        "Scenario validated from mapping (grid=%dx%d, flora=%d, predators=%d)",
        config.grid_width,
        config.grid_height,
        len(config.flora_species),
        len(config.predator_species),
    )
    return config


def load_scenario_from_json(path: str | Path) -> SimulationConfig:
    """Load and validate a simulation configuration from a JSON file.

    Args:
        path: Path to the JSON scenario file.

    Returns:
        SimulationConfig: Validated Pydantic configuration instance.
    """
    source = Path(path)
    raw = source.read_text(encoding="utf-8")
    data: dict[str, Any] = json.loads(raw)
    config = load_scenario_from_dict(data)
    logger.info("Scenario loaded from %s", source)
    return config


def scenario_to_json(config: SimulationConfig, path: str | Path | None = None) -> str:
    """Serialise a SimulationConfig to a JSON string or file.

    Args:
        config: Configuration to serialise.
        path: Optional file path to write the JSON to. If ``None``, only the
            JSON string is returned.

    Returns:
        str: JSON representation of the configuration.
    """
    serialised = config.model_dump_json(indent=2)
    if path is not None:
        destination = Path(path)
        destination.write_text(serialised, encoding="utf-8")
        logger.info("Scenario written to %s", destination)
    return serialised
