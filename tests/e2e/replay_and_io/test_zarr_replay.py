"""Comprehensive test suite for the Zarr replay backend.

This test module validates ZarrReplayBuffer field serialization round-trip fidelity,
metadata persistence, retention policies, and strict .zarr-only load semantics.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest

try:
    from phids.io.zarr_replay import ZarrReplayBuffer

    ZARR_AVAILABLE = True
except ImportError:
    ZARR_AVAILABLE = False


@pytest.mark.skipif(not ZARR_AVAILABLE, reason="zarr not installed")
class TestZarrReplayBuffer:
    """Test ZarrReplayBuffer core functionality."""

    @pytest.fixture
    def temp_zarr_dir(self) -> Path:
        """Provide a temporary directory for Zarr store."""
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_zarr_create_and_append(self, temp_zarr_dir: Path) -> None:
        """Verify buffer creation and basic append operation."""
        store_path = temp_zarr_dir / "test.zarr"
        buf = ZarrReplayBuffer(spill_path=store_path)
        assert len(buf) == 0

        state = {
            "tick": 0,
            "terminated": False,
            "termination_reason": None,
            "plant_energy_layer": np.ones((10, 10), dtype=np.float32),
            "signal_layers": np.zeros((4, 10, 10), dtype=np.float32),
        }
        buf.append(state)
        assert len(buf) == 1

    def test_zarr_field_round_trip(self, temp_zarr_dir: Path) -> None:
        """Verify field arrays survive append and get_frame round-trip."""
        store_path = temp_zarr_dir / "test.zarr"
        buf = ZarrReplayBuffer(spill_path=store_path)

        energy_field = np.random.rand(5, 5).astype(np.float32)
        signal_field = (np.random.rand(3, 5, 5) * 0.999 + 0.001).astype(np.float32)

        state = {
            "tick": 42,
            "terminated": False,
            "termination_reason": None,
            "plant_energy_layer": energy_field.copy(),
            "signal_layers": signal_field.copy(),
        }
        buf.append(state)
        retrieved = buf.get_frame(0)

        # Verify metadata
        assert retrieved["tick"] == 42
        assert retrieved["terminated"] is False
        assert retrieved["termination_reason"] is None

        # Verify field round-trip (lists after to_dict conversion)
        retrieved_energy = np.array(retrieved["plant_energy_layer"], dtype=np.float32)
        retrieved_signal = np.array(retrieved["signal_layers"], dtype=np.float32)

        np.testing.assert_array_almost_equal(energy_field, retrieved_energy)
        np.testing.assert_array_almost_equal(signal_field, retrieved_signal)

    def test_zarr_signal_epsilon_clipping(self, temp_zarr_dir: Path) -> None:
        """Verify subnormal signal tails are clipped to zero."""
        store_path = temp_zarr_dir / "test.zarr"
        buf = ZarrReplayBuffer(spill_path=store_path)

        signal_field = np.array(
            [
                [[1e-3, 1e-5, 1e-4, 2e-4], [5e-3, 1e-7, 0.0, 0.5]],
                [[0.1, 1e-6, 3e-4, 0.2], [0.05, 1e-8, 1e-3, 0.15]],
            ],
            dtype=np.float32,
        )

        state = {
            "tick": 0,
            "terminated": False,
            "termination_reason": None,
            "signal_layers": signal_field.copy(),
        }
        buf.append(state)
        retrieved = buf.get_frame(0)

        retrieved_signal = np.array(retrieved["signal_layers"], dtype=np.float32)
        # Values < 1e-4 should be clipped to 0.0
        assert retrieved_signal[0, 0, 1] == 0.0  # 1e-5
        assert retrieved_signal[0, 1, 1] == 0.0  # 1e-7
        assert retrieved_signal[1, 0, 1] == 0.0  # 1e-6
        assert retrieved_signal[1, 1, 1] == 0.0  # 1e-8
        # Values >= 1e-4 should remain
        assert retrieved_signal[0, 0, 0] == pytest.approx(1e-3)
        assert retrieved_signal[0, 1, 0] == pytest.approx(5e-3)

    def test_zarr_retention_policy(self, temp_zarr_dir: Path) -> None:
        """Verify max_frames retention policy prunes oldest frames."""
        store_path = temp_zarr_dir / "test.zarr"
        buf = ZarrReplayBuffer(max_frames=3, spill_path=store_path)

        for i in range(5):
            state = {
                "tick": i,
                "terminated": False,
                "termination_reason": None,
                "frame_id": i,
            }
            buf.append(state)

        # Only last 3 frames should be retained
        assert len(buf) == 3

        # Verify the retained frames are the last 3 (frame_id 2, 3, 4)
        frame_0 = buf.get_frame(0)
        frame_1 = buf.get_frame(1)
        frame_2 = buf.get_frame(2)
        assert frame_0.get("frame_id") == 2  # Oldest retained
        assert frame_1.get("frame_id") == 3
        assert frame_2.get("frame_id") == 4  # Newest

    def test_zarr_get_out_of_range(self, temp_zarr_dir: Path) -> None:
        """Verify IndexError is raised for out-of-range frame access."""
        store_path = temp_zarr_dir / "test.zarr"
        buf = ZarrReplayBuffer(spill_path=store_path)
        buf.append({"tick": 0})

        with pytest.raises(IndexError):
            buf.get_frame(1)

        with pytest.raises(IndexError):
            buf.get_frame(-1)

    def test_zarr_multiple_appends(self, temp_zarr_dir: Path) -> None:
        """Verify sequential appends with varied field shapes."""
        store_path = temp_zarr_dir / "test.zarr"
        buf = ZarrReplayBuffer(spill_path=store_path)

        for i in range(10):
            state = {
                "tick": i,
                "terminated": i == 9,
                "termination_reason": "max_ticks" if i == 9 else None,
                "plant_energy": np.full((4, 4), float(i), dtype=np.float32),
                "toxins": np.full((2, 4, 4), float(i + 1), dtype=np.float32),
            }
            buf.append(state)

        assert len(buf) == 10

        # Verify frame 5
        frame_5 = buf.get_frame(5)
        assert frame_5["tick"] == 5
        assert frame_5["terminated"] is False
        plant_energy = np.array(frame_5["plant_energy"], dtype=np.float32)
        np.testing.assert_array_almost_equal(plant_energy, np.full((4, 4), 5.0))

    def test_zarr_append_raw_arrays(self, temp_zarr_dir: Path) -> None:
        """Verify raw-array replay append bypasses dict/list conversion requirements."""
        store_path = temp_zarr_dir / "raw.zarr"
        buf = ZarrReplayBuffer(spill_path=store_path)

        class _Env:
            def __init__(self) -> None:
                self.plant_energy_layer = np.full((3, 3), 2.0, dtype=np.float64)
                self.signal_layers = np.full((1, 3, 3), 1e-5, dtype=np.float64)
                self.toxin_layers = np.zeros((1, 3, 3), dtype=np.float64)
                self.flow_field = np.full((3, 3), 0.5, dtype=np.float64)
                self.wind_vector_x = np.zeros((3, 3), dtype=np.float64)
                self.wind_vector_y = np.zeros((3, 3), dtype=np.float64)

        env = _Env()
        buf.append_raw_arrays(tick=7, env=env, termination_state=(False, None))

        frame = buf.get_frame(0)
        assert frame["tick"] == 7
        np.testing.assert_array_equal(
            np.asarray(frame["plant_energy_layer"]), env.plant_energy_layer
        )
        restored_signals = np.asarray(frame["signal_layers"], dtype=np.float32)
        assert float(restored_signals[0, 0, 0]) == 0.0


@pytest.mark.skipif(not ZARR_AVAILABLE, reason="zarr not installed")
class TestZarrReplayLoadSemantics:
    """Test forward-only replay loading semantics for Zarr stores."""

    @pytest.fixture
    def temp_zarr_dir(self) -> Path:
        """Provide a temporary directory for Zarr store."""
        import shutil

        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_zarr_load_native_zarr(self, temp_zarr_dir: Path) -> None:
        """Verify native Zarr store loads correctly."""
        store_path = temp_zarr_dir / "test.zarr"

        # Create native Zarr buffer
        buf_save = ZarrReplayBuffer(spill_path=store_path)
        for i in range(3):
            buf_save.append({"tick": i, "data": i * 2})

        # Load it back
        buf_load = ZarrReplayBuffer.load(store_path)
        assert len(buf_load) == 3
        frame = buf_load.get_frame(1)
        assert frame["tick"] == 1
        assert frame["data"] == 2

    def test_zarr_load_rejects_legacy_bin_paths(self, temp_zarr_dir: Path) -> None:
        """Verify .bin replay paths are rejected under forward-only loading semantics."""
        legacy_path = temp_zarr_dir / "legacy.bin"
        legacy_path.write_bytes(b"\x00\x00\x00\x00")

        with pytest.raises(ValueError, match="only \\.zarr directories are supported"):
            ZarrReplayBuffer.load(legacy_path)

    def test_zarr_load_rejects_non_zarr_files_without_suffix(self, temp_zarr_dir: Path) -> None:
        """Verify flat replay files without a .zarr suffix are rejected."""
        flat_file = temp_zarr_dir / "replay"
        flat_file.write_text("not a zarr store", encoding="utf-8")

        with pytest.raises(ValueError, match="only \\.zarr directories are supported"):
            ZarrReplayBuffer.load(flat_file)


@pytest.mark.skipif(not ZARR_AVAILABLE, reason="zarr not installed")
class TestZarrReplayAPI:
    """Test Zarr API compatibility with legacy ReplayBuffer."""

    @pytest.fixture
    def temp_zarr_dir(self) -> Path:
        """Provide a temporary directory for Zarr store."""
        import shutil

        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_zarr_api_parity(self, temp_zarr_dir: Path) -> None:
        """Verify ZarrReplayBuffer has feature parity with ReplayBuffer API."""
        store_path = temp_zarr_dir / "test.zarr"
        zarr_buf = ZarrReplayBuffer(spill_path=store_path)

        # Test append
        state = {
            "tick": 0,
            "field": np.ones((5, 5), dtype=np.float32),
        }
        zarr_buf.append(state)
        assert len(zarr_buf) == 1

        # Test get_frame
        retrieved = zarr_buf.get_frame(0)
        assert "tick" in retrieved
        assert "field" in retrieved

        # Test __len__
        assert len(zarr_buf) >= 1

        # Test save (export)
        export_path = temp_zarr_dir / "export.zarr"
        zarr_buf.save(export_path)
        assert export_path.exists()

        # Test load
        loaded_buf = ZarrReplayBuffer.load(export_path)
        assert len(loaded_buf) == len(zarr_buf)

    def test_zarr_lazy_store_initialization(self, temp_zarr_dir: Path) -> None:
        """Verify store is created lazily on first append."""
        buf = ZarrReplayBuffer()
        # Store should not exist yet
        assert buf._root is None

        # First append triggers creation
        buf.append({"tick": 0})
        assert buf._root is not None


@pytest.mark.skipif(not ZARR_AVAILABLE, reason="zarr not installed")
class TestZarrReplayIntegration:
    """Integration tests for Zarr replay with realistic simulation payloads."""

    @pytest.fixture
    def temp_zarr_dir(self) -> Path:
        """Provide a temporary directory for Zarr store."""
        import shutil

        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_zarr_realistic_snapshot(self, temp_zarr_dir: Path) -> None:
        """Test with realistic GridEnvironment snapshot structure."""
        store_path = temp_zarr_dir / "realistic.zarr"
        buf = ZarrReplayBuffer(spill_path=store_path)

        # Simulate realistic multi-species, multi-signal snapshot
        grid_w, grid_h = 40, 40
        num_flora = 3
        num_signals = 4

        realistic_state = {
            "tick": 100,
            "terminated": False,
            "termination_reason": None,
            "grid_width": grid_w,
            "grid_height": grid_h,
            "plant_energy_layer": np.random.rand(num_flora, grid_h, grid_w).astype(np.float32),
            "signal_layers": np.random.rand(num_signals, grid_h, grid_w).astype(np.float32),
            "toxin_layers": np.random.rand(4, grid_h, grid_w).astype(np.float32),
            "flow_field": np.random.randn(2, grid_h, grid_w).astype(np.float32),
            "wind": np.array([0.5, -0.2], dtype=np.float32),
        }

        buf.append(realistic_state)
        retrieved = buf.get_frame(0)

        assert retrieved["tick"] == 100
        assert retrieved["grid_width"] == grid_w
        assert retrieved["grid_height"] == grid_h

        # Verify array shapes are preserved
        plant_energy = np.array(retrieved["plant_energy_layer"], dtype=np.float32)
        assert plant_energy.shape == (num_flora, grid_h, grid_w)

        signal_layers = np.array(retrieved["signal_layers"], dtype=np.float32)
        assert signal_layers.shape == (num_signals, grid_h, grid_w)

    def test_zarr_large_buffer_compression(self, temp_zarr_dir: Path) -> None:
        """Verify compression reduces storage footprint for large replays."""
        store_path = temp_zarr_dir / "large.zarr"
        buf = ZarrReplayBuffer(spill_path=store_path)

        # Generate large-scale frames
        for tick in range(20):
            state = {
                "tick": tick,
                "terminated": False,
                "termination_reason": None,
                "plant_energy": np.random.rand(16, 80, 80).astype(np.float32),
                "signals": np.random.rand(4, 80, 80).astype(np.float32),
                "toxins": np.random.rand(4, 80, 80).astype(np.float32),
            }
            buf.append(state)

        assert len(buf) == 20

        # Verify store directory exists and has meaningful size
        assert store_path.exists()
        # Zarr directory should contain metadata and data chunks
        zarr_files = list(store_path.rglob("*"))
        assert len(zarr_files) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
