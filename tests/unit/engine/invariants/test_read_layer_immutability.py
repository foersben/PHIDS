# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit Invariant Tests for Double-Buffering Read-Layer Immutability.

This module validates that writes to GridEnvironment _write buffers leave the current _read
layer cryptographic SHA-256 byte hash 100% unchanged prior to rebuild_energy_layer().
"""

from __future__ import annotations

import hashlib

import pytest

from phids.engine.core.biotope import GridEnvironment


@pytest.mark.scientific_invariant
def test_grid_environment_read_layer_immutability() -> None:
    """Verify that _write layer modifications leave the _read layer bit-exact unchanged before swap.

    Raises:
        AssertionError: If the SHA-256 byte hash of the _read buffer changes before rebuild_energy_layer().
    """
    env = GridEnvironment(16, 16)
    env.set_plant_energy(5, 5, 0, 80.0)

    # Compute initial cryptographic hash of current read buffer
    initial_hash = hashlib.sha256(env.plant_energy_layer.tobytes()).hexdigest()

    # Modify the write layer directly
    env._plant_energy_layer_write[5, 5] = 999.0
    env._plant_energy_layer_write[6, 6] = 500.0

    # Verify that read buffer hash is 100% identical
    post_write_hash = hashlib.sha256(env.plant_energy_layer.tobytes()).hexdigest()
    assert initial_hash == post_write_hash, "_read layer was mutated before swap_buffers()!"

    # After explicit rebuild/swap, the new read hash should match updated values
    env.rebuild_energy_layer()
    swapped_hash = hashlib.sha256(env.plant_energy_layer.tobytes()).hexdigest()
    assert initial_hash != swapped_hash, "rebuild_energy_layer() failed to promote _write to _read!"
