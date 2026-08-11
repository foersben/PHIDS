# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Utilities for grid dimensions, power-of-two detection, and coordinate masking."""

from __future__ import annotations


def is_power_of_two(n: int) -> bool:
    """Return True if n > 0 and n is a power of 2."""
    return n > 0 and (n & (n - 1)) == 0


def get_grid_masks(width: int, height: int) -> tuple[bool, int, int]:
    """Return (is_pow2, mask_x, mask_y) for toroidal coordinate wrapping.

    When both width and height are powers of 2, toroidal wrapping (x % width, y % height)
    can be computed as single-cycle bitwise AND operations (x & mask_x, y & mask_y)
    where mask_x = width - 1 and mask_y = height - 1.

    Args:
        width: Grid horizontal dimension.
        height: Grid vertical dimension.

    Returns:
        Tuple of (is_pow2_flag, mask_x, mask_y).
    """
    is_pow2 = is_power_of_two(width) and is_power_of_two(height)
    mask_x = (width - 1) if is_pow2 else width
    mask_y = (height - 1) if is_pow2 else height
    return is_pow2, mask_x, mask_y
