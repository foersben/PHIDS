# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Targeted unit and edge-case tests for Zarr telemetry replay buffer coverage.

Validates automatic store cleanup on owned scratch paths, metadata deserialization
fallback on corrupt binary payloads, epsilon signal tail clipping, and
boundary guard raising on out-of-bounds frame access.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest

from phids.io.zarr_replay import ReplayBuffer
from phids.shared.constants import SIGNAL_EPSILON

if TYPE_CHECKING:
    from pathlib import Path

try:
    import zarr  # noqa: F401

    ZARR_AVAILABLE = True
except ImportError:
    ZARR_AVAILABLE = False


@pytest.mark.skipif(not ZARR_AVAILABLE, reason="zarr not installed")
def test_zarr_cleanup_store_for_owned_paths() -> None:
    """Verify automatic cleanup of spilled telemetry store directory for owned paths."""
    buffer = ReplayBuffer()
    buffer._ensure_store()
    assert buffer._store_path is not None
    assert buffer._store_path.exists()
    store_path = buffer._store_path
    buffer._cleanup_store()
    assert not store_path.exists()


@pytest.mark.skipif(not ZARR_AVAILABLE, reason="zarr not installed")
def test_zarr_load_metadata_falls_back_on_corrupt_blob(tmp_path: Path) -> None:
    """Verify metadata loader recovers gracefully when Zarr metadata array is corrupted.

    Args:
        tmp_path: Pytest temporary directory fixture.
    """
    import zarr

    store_path = tmp_path / "corrupt.zarr"
    root = zarr.open_group(str(store_path), mode="w")
    root.create_group("frames/00000000")
    root.create_array("_metadata", data=np.frombuffer(b"not-json", dtype=np.uint8), chunks=(8,))

    buffer = ReplayBuffer(spill_path=store_path)
    buffer._load_metadata()
    assert len(buffer) == 0
    assert buffer._frame_count == 1


@pytest.mark.skipif(not ZARR_AVAILABLE, reason="zarr not installed")
def test_zarr_signal_tail_clipping_on_append_and_read(tmp_path: Path) -> None:
    """Verify signaling concentration values below SIGNAL_EPSILON are clipped to zero on append.

    Args:
        tmp_path: Pytest temporary directory fixture.
    """
    store_path = tmp_path / "signal.zarr"
    buffer = ReplayBuffer(spill_path=store_path)
    signal = np.array([[[SIGNAL_EPSILON * 0.5, SIGNAL_EPSILON * 2.0]]], dtype=np.float32)
    buffer.append({"tick": 0, "signal_layers": signal})
    frame = buffer.get_frame(0)
    restored = np.asarray(frame["signal_layers"], dtype=np.float32)
    assert restored[0, 0, 0] == 0.0
    assert restored[0, 0, 1] > 0.0


@pytest.mark.skipif(not ZARR_AVAILABLE, reason="zarr not installed")
def test_zarr_get_frame_out_of_bounds_raises(tmp_path: Path) -> None:
    """Assert IndexError is raised on out-of-bounds frame lookup in ReplayBuffer.

    Args:
        tmp_path: Pytest temporary directory fixture.
    """
    buffer = ReplayBuffer(spill_path=tmp_path / "frames.zarr")
    buffer.append({"tick": 0, "value": 1})
    with pytest.raises(IndexError):
        buffer.get_frame(4)
