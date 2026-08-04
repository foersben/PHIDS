# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Utility functions for telemetry normalization and scalar coercion."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from phids.engine.batch.types import TelemetryRow


def _coerce_int(value: object) -> int:
    """Convert telemetry scalar to int with stable fallback semantics.

    Args:
        value: The value to convert.

    Returns:
        The converted value.
    """
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, str)):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def _coerce_float(value: object) -> float:
    """Convert telemetry scalar to float with stable fallback semantics.

    Args:
        value: The value to convert.

    Returns:
        The converted value.
    """
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float, str)):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def _species_count(row: TelemetryRow, field: str, species_id: int) -> float:
    """Read one species count from a telemetry row field map with numeric fallback.

    Args:
        row: The telemetry row.
        field: The field name.
        species_id: The species identifier.

    Returns:
        The species count.
    """
    raw_map = row.get(field, {})
    if not isinstance(raw_map, dict):
        return 0.0
    return _coerce_float(raw_map.get(species_id, 0.0))


def _get_int_keys(d: object) -> set[int]:
    """Return all integer keys from a dict.

    Args:
        d: The object to extract keys from.

    Returns:
        The extracted keys.
    """
    if isinstance(d, dict):
        return {k for k in d.keys() if isinstance(k, int)}
    return set()


def _sanitize_for_json(value: object) -> object:
    """Recursively coerce aggregate values into strict JSON-compatible scalars.

    This sanitiser replaces all non-finite floating-point values (``NaN``,
    ``+inf``, ``-inf``) with ``None`` so downstream ``json.dump(...,
    allow_nan=False)`` remains standards-compliant and browser ``JSON.parse``
    never encounters invalid numeric tokens.

    Args:
        value: Arbitrary Python/NumPy value.

    Returns:
        object: JSON-safe structure preserving the original shape.
    """
    if isinstance(value, dict):
        return {str(k): _sanitize_for_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_for_json(v) for v in value]
    if isinstance(value, np.generic):
        return _sanitize_for_json(value.item())
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)
