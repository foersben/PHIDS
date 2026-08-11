"""Unit tests for Zarr spatial chunking configurations."""

import numpy as np
import pytest

from phids.io.zarr_replay import ReplayBuffer


@pytest.fixture
def replay_buffer(tmp_path) -> ReplayBuffer:
    """Provide a temporary ReplayBuffer."""
    zarr_path = tmp_path / "test_chunking.zarr"
    return ReplayBuffer(spill_path=str(zarr_path))


def test_1d_array_chunking(replay_buffer: ReplayBuffer) -> None:
    """Test that 1D arrays are chunked linearly up to 256,000 elements."""
    # A massive 1D array of 500,000 elements
    field_data = np.zeros(500_000, dtype=np.float32)

    root = replay_buffer._ensure_store()
    frame_group = root.create_group("tick_1")
    replay_buffer._store_field(frame_group, "swarms_x", field_data)

    zarr_array = frame_group["swarms_x"]
    assert zarr_array.chunks == (256_000,)


def test_2d_spatial_chunking(replay_buffer: ReplayBuffer) -> None:
    """Test that 2D arrays are chunked into 256x256 spatial blocks."""
    field_data = np.zeros((1024, 1024), dtype=np.float32)

    root = replay_buffer._ensure_store()
    frame_group = root.create_group("tick_1")
    replay_buffer._store_field(frame_group, "flow_field", field_data)

    zarr_array = frame_group["flow_field"]
    assert zarr_array.chunks == (256, 256)


def test_3d_channel_chunking(replay_buffer: ReplayBuffer) -> None:
    """Test that 3D layer arrays are chunked as (1, 256, 256)."""
    # 4 channels (e.g. signal layers), 1024x1024 grid
    field_data = np.zeros((4, 1024, 1024), dtype=np.float32)

    root = replay_buffer._ensure_store()
    frame_group = root.create_group("tick_1")
    replay_buffer._store_field(frame_group, "signal_layers", field_data)

    zarr_array = frame_group["signal_layers"]
    assert zarr_array.chunks == (1, 256, 256)


def test_small_array_clamping(replay_buffer: ReplayBuffer) -> None:
    """Test that chunks clamp to array size if smaller than 256x256."""
    field_data = np.zeros((100, 100), dtype=np.float32)

    root = replay_buffer._ensure_store()
    frame_group = root.create_group("tick_1")
    replay_buffer._store_field(frame_group, "small_field", field_data)

    zarr_array = frame_group["small_field"]
    assert zarr_array.chunks == (100, 100)
