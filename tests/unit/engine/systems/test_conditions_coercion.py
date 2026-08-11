# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for signaling condition coercion functions and fallback branches."""

from __future__ import annotations

import pytest

from phids.engine.systems.signaling.conditions import _coerce_float, _coerce_int


@pytest.mark.unit
def test_coerce_int_branches() -> None:
    """Verify _coerce_int branch handling across bool, valid string, invalid string, and non-scalar object types.

    Raises:
        AssertionError: If _coerce_int fails to coerce valid inputs or fall back to default.
    """
    # Bool branch
    assert _coerce_int(True, 0) == 1
    assert _coerce_int(False, 10) == 0

    # Valid scalar types
    assert _coerce_int(42, 0) == 42
    assert _coerce_int(3.14, 0) == 3
    assert _coerce_int("100", 0) == 100

    # Invalid string -> ValueError fallback
    assert _coerce_int("not_an_int", 999) == 999

    # Non-scalar object -> default fallback
    assert _coerce_int([1, 2, 3], 888) == 888
    assert _coerce_int(None, 777) == 777


@pytest.mark.unit
def test_coerce_float_branches() -> None:
    """Verify _coerce_float branch handling across bool, valid string, invalid string, and non-scalar object types.

    Raises:
        AssertionError: If _coerce_float fails to coerce valid inputs or fall back to default.
    """
    # Bool branch
    assert _coerce_float(True, 0.0) == 1.0
    assert _coerce_float(False, 10.0) == 0.0

    # Valid scalar types
    assert _coerce_float(42, 0.0) == 42.0
    assert _coerce_float(3.14, 0.0) == 3.14
    assert _coerce_float("2.718", 0.0) == 2.718

    # Invalid string -> ValueError fallback
    assert _coerce_float("invalid_float", 9.99) == 9.99

    # Non-scalar object -> default fallback
    assert _coerce_float({"key": "val"}, 8.88) == 8.88
    assert _coerce_float(None, 7.77) == 7.77
