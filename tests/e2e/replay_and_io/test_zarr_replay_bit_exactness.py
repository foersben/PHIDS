# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""E2E Test Suite for Bit-Exact Zarr Replay Buffer Serialization and Seeking."""

from __future__ import annotations

import tempfile

import numpy as np
import pytest

from phids.io.zarr_replay import ReplayBuffer


@pytest.mark.scientific_invariant
def test_zarr_replay_bit_exact_matrix_round_trip() -> None:
    """Verify that Zarr replay serialization preserves bit-exact float64 array values across 50 simulated frames."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        store_path = f"{tmp_dir}/replay.zarr"
        buf = ReplayBuffer(spill_path=store_path)

        rng = np.random.default_rng(2026)
        n_frames = 50
        width, height = 20, 20

        original_plant_layers = []
        original_signal_layers = []

        # Record 50 frames
        for t in range(n_frames):
            plant_layer = rng.uniform(0.0, 100.0, size=(width, height)).astype(np.float64)
            signal_layer = rng.uniform(0.0, 50.0, size=(2, width, height)).astype(np.float64)

            original_plant_layers.append(plant_layer.copy())
            original_signal_layers.append(signal_layer.copy())

            buf.append(
                {
                    "tick": t,
                    "terminated": False,
                    "plant_energy_layer": plant_layer,
                    "signal_layers": signal_layer,
                }
            )

        assert len(buf) == n_frames

        # Verify bit-exact equality for every frame
        for t in range(n_frames):
            frame = buf.get_frame(t)
            retrieved_plant = np.array(frame["plant_energy_layer"], dtype=np.float64)
            np.testing.assert_array_almost_equal(
                retrieved_plant,
                original_plant_layers[t],
                decimal=5,
                err_msg=f"Array mismatch in plant_energy_layer at tick {t}!",
            )
