"""Scenario I/O helpers for loading, validating, and serialising ``SimulationConfig`` instances.

This module provides three convenience functions that bridge external JSON representations of
simulation scenarios and the Pydantic-validated ``SimulationConfig`` model. Validation is
performed by :func:`load_scenario_from_dict` via ``SimulationConfig.model_validate``, which
enforces all Rule-of-16 cardinality bounds, species-placement reference integrity, diet-matrix
shape constraints, and termination-threshold range checks before any engine state is allocated.
Any violation raises a ``pydantic.ValidationError``, preventing malformed configuration data from
reaching the ``GridEnvironment`` or ``ECSWorld`` constructors.

:func:`load_scenario_from_json` reads a UTF-8 encoded JSON file, decodes it with the standard
library ``json`` module, and delegates to :func:`load_scenario_from_dict`. :func:`scenario_to_json`
serialises a validated configuration back to canonical JSON using Pydantic's ``model_dump_json``
method, which preserves all default values and respects custom field serialisers defined in the
schema layer. Optionally, the output may be written to a file path, enabling scenario export from
the REST API and from command-line scripting workflows.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Mapping, TypeAlias

from phids.api.schemas import SimulationConfig

logger = logging.getLogger(__name__)

JSONScalar: TypeAlias = None | bool | int | float | str
JSONValue: TypeAlias = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]
JSONMapping: TypeAlias = Mapping[str, JSONValue]


def load_scenario_from_dict(data: JSONMapping) -> SimulationConfig:
    """Parse and validate a simulation configuration from a mapping.

    Args:
        data: Raw configuration mapping (typically decoded from JSON).

    Returns:
        SimulationConfig: Validated Pydantic configuration instance.

    Raises:
        pydantic.ValidationError: If the configuration is invalid.
    """
    config = SimulationConfig.model_validate(dict(data))
    logger.debug(
        "Scenario validated from mapping (grid=%dx%d, flora=%d, herbivores=%d)",
        config.grid_width,
        config.grid_height,
        len(config.flora_species),
        len(config.herbivore_species),
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
    decoded: JSONValue = json.loads(raw)
    if not isinstance(decoded, dict):
        raise ValueError(f"Scenario JSON root must be an object: {source}")
    data: dict[str, JSONValue] = decoded
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
