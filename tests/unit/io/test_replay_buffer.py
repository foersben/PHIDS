"""Unit checks for replay buffer persistence and truncation handling."""

from __future__ import annotations

import logging
from pathlib import Path

import msgpack
import numpy as np
import pytest

from phids.io.replay import ReplayBuffer, deserialise_state


def test_replay_buffer_save_load_and_truncated_file_warning(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify replay save/load round-trips and truncated frames emit warning diagnostics."""
    replay = ReplayBuffer()
    replay.append({"tick": 0, "value": 1})
    replay.append({"tick": 1, "value": 2})

    path = tmp_path / "replay.bin"
    replay.save(path)
    loaded = ReplayBuffer.load(path)
    assert len(loaded) == 2
    assert loaded.get_frame(1)["value"] == 2

    broken_path = tmp_path / "broken_replay.bin"
    broken_path.write_bytes((10).to_bytes(4, "little") + b"123")
    with caplog.at_level(logging.WARNING, logger="phids.io.replay"):
        truncated = ReplayBuffer.load(broken_path)
    assert len(truncated) == 0
    assert "ended mid-frame" in caplog.text


def test_replay_buffer_spills_old_frames_to_disk_and_retrieves_on_demand(
    tmp_path: Path,
) -> None:
    """Verify spill mode preserves historical frame access while bounding in-memory residency."""
    spill_path = tmp_path / "spilled_frames.bin"
    replay = ReplayBuffer(max_frames=2, spill_to_disk=True, spill_path=spill_path)
    for tick in range(5):
        replay.append({"tick": tick, "value": tick * 2})

    assert len(replay) == 5
    assert spill_path.exists()
    assert replay.get_frame(0)["value"] == 0
    assert replay.get_frame(4)["value"] == 8

    saved_path = tmp_path / "merged.replay"
    replay.save(saved_path)
    loaded = ReplayBuffer.load(saved_path)
    assert len(loaded) == 5
    assert loaded.get_frame(2)["tick"] == 2


def test_replay_buffer_append_raw_arrays_serialises_environment_layers() -> None:
    """Raw-array append preserves layer payloads and termination metadata in replay frames."""

    class _EnvStub:
        def __init__(self) -> None:
            self.plant_energy_layer = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
            self.signal_layers = np.zeros((1, 2, 2), dtype=np.float32)
            self.toxin_layers = np.ones((1, 2, 2), dtype=np.float32)
            self.flow_field = np.array([[0.25, -0.5], [1.25, 2.5]], dtype=np.float32)
            self.wind_vector_x = np.full((2, 2), 0.1, dtype=np.float32)
            self.wind_vector_y = np.full((2, 2), -0.2, dtype=np.float32)

    replay = ReplayBuffer()
    replay.append_raw_arrays(
        tick=7, env=_EnvStub(), termination_state=(True, "Z1: max ticks reached")
    )

    frame = replay.get_frame(0)
    assert frame["tick"] == 7
    assert frame["terminated"] is True
    assert frame["termination_reason"] == "Z1: max ticks reached"
    assert frame["plant_energy_layer"] == [[1.0, 2.0], [3.0, 4.0]]
    np.testing.assert_allclose(
        np.asarray(frame["wind_vector_x"], dtype=np.float32),
        np.array([[0.1, 0.1], [0.1, 0.1]], dtype=np.float32),
    )
    np.testing.assert_allclose(
        np.asarray(frame["wind_vector_y"], dtype=np.float32),
        np.array([[-0.2, -0.2], [-0.2, -0.2]], dtype=np.float32),
    )


def test_deserialise_state_rejects_non_mapping_payload() -> None:
    """Decoding must fail closed when a replay frame payload is not a mapping."""
    with pytest.raises(ValueError, match="must decode to a mapping"):
        deserialise_state(msgpack.packb([1, 2, 3], use_bin_type=True))


def test_replay_buffer_in_memory_overflow_discards_oldest_without_spill() -> None:
    """Bounded in-memory mode keeps only newest frames when spill is disabled."""
    replay = ReplayBuffer(max_frames=2, spill_to_disk=False)
    for tick in range(5):
        replay.append({"tick": tick, "value": tick})

    assert len(replay) == 2
    assert replay.get_frame(0)["tick"] == 3
    assert replay.get_frame(1)["tick"] == 4


def test_replay_buffer_read_spilled_frame_requires_existing_spill_file() -> None:
    """Reading spilled payloads fails with deterministic IndexError when no spill file exists."""
    replay = ReplayBuffer(spill_to_disk=True)
    with pytest.raises(IndexError, match="Spill file is not available"):
        replay._read_spilled_frame(0)  # noqa: SLF001


def test_replay_buffer_owned_spill_cleanup_removes_file(tmp_path: Path) -> None:
    """Owned spill files are removed during cleanup to avoid stale temporary artifacts."""
    replay = ReplayBuffer(spill_to_disk=True)
    replay._spill_path = tmp_path / "owned_spill.bin"  # noqa: SLF001
    replay._owns_spill_file = True  # noqa: SLF001
    replay._spill_path.write_bytes(b"frame-bytes")  # noqa: SLF001

    replay._cleanup_spill_file()  # noqa: SLF001

    assert not replay._spill_path.exists()  # noqa: SLF001
