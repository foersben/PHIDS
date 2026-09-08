# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Authoritative scalar coercion utilities with robust fallback semantics.

This module provides deterministic conversion functions between loosely-typed runtime objects
(e.g., deserialized JSON, untyped dictionary values, external inputs) and strict primitive numeric
types (int, float). It replaces scattered ad-hoc try-except coercion logic across the engine, API,
and batch pipelines, ensuring uniform handling of boolean edge cases, strings, and missing data.
"""

from __future__ import annotations


def coerce_int(value: object, default: int = 0) -> int:
    """Convert an arbitrary value to an integer with stable fallback semantics.

    Handles booleans explicitly (preserving standard integer mapping if boolean, or returning
    default when strict non-boolean conversion is needed), handles numeric casts, and trims/parses
    string representations safely without raising exceptions.

    Args:
        value: The raw input object to convert (e.g. str, int, float, or None).
        default: Fallback integer returned if conversion fails or value is None. Defaults to 0.

    Returns:
        int: Converted integer value or default if conversion is impossible.

    Examples:
        >>> coerce_int(42)
        42
        >>> coerce_int("128")
        128
        >>> coerce_int("invalid", default=-1)
        -1
        >>> coerce_int(None, default=10)
        10
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        try:
            return int(value)
        except (ValueError, OverflowError):
            return default
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            try:
                # Handle string floats such as "12.0"
                return int(float(value.strip()))
            except (ValueError, OverflowError):
                return default
    return default


def coerce_float(value: object, default: float = 0.0) -> float:
    """Convert an arbitrary value to a float with stable fallback semantics.

    Safely converts integers, floats, and numeric strings to Python floats while mapping booleans,
    incompatible types, and unparsable strings to the provided default value.

    Args:
        value: The raw input object to convert.
        default: Fallback float returned if conversion fails or value is None. Defaults to 0.0.

    Returns:
        float: Converted floating point value or default if conversion fails.

    Examples:
        >>> coerce_float(3.14)
        3.14
        >>> coerce_float("1.25e-3")
        0.00125
        >>> coerce_float(True, default=0.0)
        1.0
        >>> coerce_float(False, default=1.0)
        0.0
        >>> coerce_float("nan_string", default=1.0)
        1.0
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return default
    return default
