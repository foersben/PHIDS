# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit test suite for Zarr replay buffer edge cases, error branches, and bounds checks."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest

from phids.io.zarr_replay import (
    NoOpReplayBuffer,
    ReplayBuffer,
    ReplaySlice,
)


@pytest.fixture
def temp_zarr_dir() -> Path:
    """Provide a temporary directory for Zarr store."""
    tmpdir = tempfile.mkdtemp()
    yield Path(tmpdir)
    import shutil

    shutil.rmtree(tmpdir, ignore_errors=True)


def test_noop_replay_buffer_bounds() -> None:
    """Verify NoOpReplayBuffer raises IndexError on frame access and no-ops gracefully."""
    buf = NoOpReplayBuffer()
    assert len(buf) == 0

    buf.append({"tick": 0})
    assert len(buf) == 0

    with pytest.raises(IndexError, match=r"Replay frame index out of range"):
        buf.get_frame_arrays(0)

    slice_view = buf.get_slice(0, 0)
    assert slice_view.start_tick == 0
    assert slice_view.end_tick == 0
    assert len(slice_view.metadata) == 0


def test_replay_slice_get_field() -> None:
    """Verify ReplaySlice field retrieval and KeyError on invalid fields."""
    metadata = [{"tick": 0, "terminated": False, "termination_reason": None}]
    fields = {"plant_energy_layer": np.ones((1, 10, 10), dtype=np.float32)}
    rslice = ReplaySlice(0, 1, metadata, fields)

    assert rslice.get_field("plant_energy_layer").shape == (1, 10, 10)

    with pytest.raises(KeyError, match=r"Field 'nonexistent' not found in ReplaySlice."):
        rslice.get_field("nonexistent")


def test_zarr_replay_bounds_and_slice(temp_zarr_dir: Path) -> None:
    """Verify ReplayBuffer out-of-bounds frame access and slice validation."""
    store_path = temp_zarr_dir / "bounds_test.zarr"
    buf = ReplayBuffer(spill_path=store_path)

    state = {
        "tick": 0,
        "terminated": False,
        "termination_reason": None,
        "plant_energy_layer": np.ones((10, 10), dtype=np.float32),
    }
    buf.append(state)
    assert len(buf) == 1

    # Out of bounds frame access
    with pytest.raises(IndexError, match=r"Replay frame index out of range"):
        buf.get_frame(5)

    with pytest.raises(IndexError, match=r"Replay frame index out of range"):
        buf.get_frame(-1)

    with pytest.raises(IndexError, match=r"Replay frame index out of range"):
        buf.get_frame_arrays(10)

    # Invalid slice bounds
    with pytest.raises(IndexError, match=r"Replay slice range"):
        buf.get_slice(0, 10)

    with pytest.raises(IndexError, match=r"Replay slice range"):
        buf.get_slice(-1, 1)


def test_zarr_replay_save_and_load_validation(temp_zarr_dir: Path) -> None:
    """Verify save and load error branches."""
    store_path = temp_zarr_dir / "export_src.zarr"
    buf = ReplayBuffer(spill_path=store_path)
    buf.append({"tick": 0, "terminated": False, "termination_reason": None})

    save_dest = temp_zarr_dir / "save_dest.zarr"
    buf.save(save_dest)
    assert save_dest.exists()

    nonexistent_path = temp_zarr_dir / "nonexistent.zarr"
    with pytest.raises(ValueError, match=r"Replay path must be an existing directory"):
        ReplayBuffer.load(nonexistent_path)
