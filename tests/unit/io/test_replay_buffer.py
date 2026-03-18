"""Unit checks for replay buffer persistence and truncation handling."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from phids.io.replay import ReplayBuffer


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
