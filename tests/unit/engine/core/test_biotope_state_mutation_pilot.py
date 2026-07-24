# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Focused pilot tests for GridEnvironment methods targeted by mutmut."""

from __future__ import annotations

import numpy as np
import pytest

from phids.engine.core.biotope import GridEnvironment, _make_gaussian_kernel


def test_grid_environment_init_dimensions() -> None:
    """Validate initialization boundaries and allocations."""
    env = GridEnvironment(width=10, height=20, num_signals=2, num_toxins=3)
    assert env.width == 10
    assert env.height == 20
    assert env.plant_energy_layer.shape == (10, 20)
    assert env._plant_energy_layer_write.shape == (10, 20)
    assert env.flow_field.shape == (10, 20)
    assert env.wind_vector_x.shape == (10, 20)
    assert env.wind_vector_y.shape == (10, 20)
    assert env.signal_layers.shape == (2, 10, 20)
    assert env.toxin_layers.shape == (3, 10, 20)
    assert env.apparent_nutrition_layer.shape == (10, 20)
    assert env._apparent_nutrition_layer_write.shape == (10, 20)


def test_grid_environment_update_wind_at() -> None:
    """Validate local wind vector updates."""
    env = GridEnvironment(width=5, height=5, num_signals=1, num_toxins=1)
    env.update_wind_at(2, 3, 1.5, -2.5)
    assert env.wind_vector_x[2, 3] == 1.5
    assert env.wind_vector_y[2, 3] == -2.5
    # Ensure it only affected the target cell
    assert env.wind_vector_x[0, 0] == 0.0


def test_grid_environment_plant_energy_lifecycle() -> None:
    """Validate double-buffering logic for plant energy layers."""
    env = GridEnvironment(width=5, height=5, num_signals=1, num_toxins=1)

    # set_plant_energy writes to the explicit layer but does NOT update plant_energy_write aggregate yet
    env.set_plant_energy(1, 1, 0, 10.0)
    assert env._plant_energy_by_species_write[0, 1, 1] == 10.0

    # rebuild_energy_layer computes the sum and swaps buffers
    env.rebuild_energy_layer()
    assert env.plant_energy_layer[1, 1] == 10.0

    # clear_plant_energy resets species layer
    env.clear_plant_energy(1, 1, 0)
    assert env._plant_energy_by_species_write[0, 1, 1] == 0.0

    # After rebuild, aggregate plant energy should drop
    env.rebuild_energy_layer()
    assert env.plant_energy_layer[1, 1] == 0.0


def test_grid_environment_apparent_nutrition() -> None:
    """Validate setting apparent nutrition."""
    env = GridEnvironment(width=5, height=5, num_signals=1, num_toxins=1)
    env.set_apparent_nutrition(2, 2, 0.5)
    assert env._apparent_nutrition_layer_write[2, 2] == 0.5

    env.rebuild_energy_layer()
    assert env.apparent_nutrition_layer[2, 2] == 0.5


def test_grid_environment_to_dict() -> None:
    """Validate dictionary snapshot serialisation."""
    env = GridEnvironment(width=2, height=2, num_signals=1, num_toxins=1)
    env.plant_energy_layer.fill(1.0)
    snapshot = env.to_dict()
    assert "signal_layers" in snapshot
    assert "toxin_layers" in snapshot
    assert "plant_energy_layer" in snapshot


def test_make_gaussian_kernel() -> None:
    """Validate the normalized diffusion kernel bounds."""
    kernel = _make_gaussian_kernel(sigma=1.0)
    assert kernel.shape == (5, 5)
    assert np.isclose(kernel.sum(), 1.0)
    assert kernel[1, 1] > kernel[0, 0]  # Center weight > corner weight


def test_grid_environment_init_bounds() -> None:
    """Validate that initialization rejects out-of-bound dimensions."""
    from phids.shared.constants import GRID_H_MAX, GRID_W_MAX, MAX_SUBSTANCE_TYPES

    with pytest.raises(ValueError, match="width"):
        GridEnvironment(width=0)
    with pytest.raises(ValueError, match="width"):
        GridEnvironment(width=GRID_W_MAX + 1)

    with pytest.raises(ValueError, match="height"):
        GridEnvironment(height=0)
    with pytest.raises(ValueError, match="height"):
        GridEnvironment(height=GRID_H_MAX + 1)

    with pytest.raises(ValueError, match="num_signals"):
        GridEnvironment(num_signals=0)
    with pytest.raises(ValueError, match="num_signals"):
        GridEnvironment(num_signals=MAX_SUBSTANCE_TYPES + 1)

    with pytest.raises(ValueError, match="num_toxins"):
        GridEnvironment(num_toxins=0)
    with pytest.raises(ValueError, match="num_toxins"):
        GridEnvironment(num_toxins=MAX_SUBSTANCE_TYPES + 1)


def test_make_gaussian_kernel_arithmetic() -> None:
    """Validate exact arithmetic structure of the diffusion kernel."""
    kernel = _make_gaussian_kernel(size=5, sigma=0.4)
    # The center weight should be dominant (approx 0.845 for sigma=0.4)
    assert kernel[2, 2] > 0.8
    assert kernel[2, 2] < 0.9
    # The sum must be strictly 1.0 (normalized)
    assert np.isclose(kernel.sum(), 1.0)
    # The corners should be effectively zero due to truncation/low sigma
    assert kernel[0, 0] < 1e-6
