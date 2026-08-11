# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for power-of-two grid coordinate wrapping utilities."""

from __future__ import annotations

from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.grid_utils import get_grid_masks, is_power_of_two


def test_is_power_of_two_classification() -> None:
    """Verify power of two identification across small and large grid dimensions."""
    powers = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024]
    non_powers = [0, -1, -16, 3, 5, 10, 15, 30, 40, 50, 100, 150, 200, 300]

    for p in powers:
        assert is_power_of_two(p) is True, f"{p} should be classified as power of 2"

    for np_val in non_powers:
        assert is_power_of_two(np_val) is False, f"{np_val} should NOT be classified as power of 2"


def test_get_grid_masks() -> None:
    """Verify mask calculation for power-of-two vs non-power-of-two grid configurations."""
    is_pow2, mask_x, mask_y = get_grid_masks(64, 64)
    assert is_pow2 is True
    assert mask_x == 63
    assert mask_y == 63

    is_pow2_rect, mask_x_rect, mask_y_rect = get_grid_masks(32, 128)
    assert is_pow2_rect is True
    assert mask_x_rect == 31
    assert mask_y_rect == 127

    is_pow2_mixed, mask_x_mixed, mask_y_mixed = get_grid_masks(40, 40)
    assert is_pow2_mixed is False
    assert mask_x_mixed == 40
    assert mask_y_mixed == 40


def test_power_of_two_vs_generic_grid_diffusion_parity() -> None:
    """Verify mathematical output parity between power-of-two bitwise AND and generic modulo signal diffusion."""
    env_pow2 = GridEnvironment(width=32, height=32, num_signals=1)
    env_pow2.signal_layers[0, 0, 0] = 10.0
    env_pow2.diffuse_signals(signal_decay_factor=0.85)

    assert env_pow2.is_pow2 is True
    assert env_pow2.mask_x == 31
    assert env_pow2.mask_y == 31

    # Verify wrap around edges (0,0 diffusing to max coordinates 31, 31)
    assert env_pow2.signal_layers[0, 31, 0] > 0.0
    assert env_pow2.signal_layers[0, 0, 31] > 0.0
