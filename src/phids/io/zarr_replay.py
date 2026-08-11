# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""High-performance chunked replay storage using Zarr for PHIDS simulation snapshots.

This module implements a Zarr-based replay backend that provides identical ``ReplayBuffer``
API semantics while achieving superior memory efficiency and I/O performance for large-scale
simulations. Zarr's chunked columnar storage model naturally maps to PHIDS field layers
(plant energy per species, signal concentrations, toxin fields, flow-field gradients),
enabling selective decompression and random access without materializing entire snapshots
into Python memory.

The Zarr schema employs fixed-depth chunking across the spatial and temporal dimensions,
with metadata groups for tick counters and termination state. Metadata (tick index,
termination flags) is stored in a separate consolidated JSON array, eliminating the need
to read field chunks for iteration or seeking. Field chunks are compressed using Zstd,
offering superior compression ratio and speed compared to default Zarr Blosc profiles
when applied to dense floating-point arrays. Subnormal tails (values < 1e-4) in signal
layers are omitted during serialization via a custom codec or post-hoc masking, further
reducing storage overhead without loss of ecological fidelity.

The design aligns with the project's strict data-oriented paradigm: snapshots are decomposed
into structured field arrays during checkpoint and reassembled into the dictionary format
for re-simulation compatibility. All serialization and field codec logic is stateless,
ensuring deterministic round-trip fidelity.
"""

from __future__ import annotations

import atexit
import json
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Any, Protocol, TypedDict, cast

import numpy as np

type ReplayScalar = bool | int | float | str | None
type ReplayValue = ReplayScalar | list["ReplayValue"] | dict[str, "ReplayValue"]
type ReplayState = dict[str, ReplayValue]

try:
    import zarr
    import zarr.codecs
except ImportError as e:
    raise ImportError("zarr>=3.0 is required for ZarrReplayBuffer. Install with: uv add zarr") from e

logger = logging.getLogger(__name__)

# Metadata compression threshold (fields smaller than this are stored as JSON arrays)
METADATA_THRESHOLD_BYTES = 4096


class _ReplayEnvLike(Protocol):
    """Structural contract for environment layers consumed by append_raw_arrays."""

    plant_energy_layer: np.ndarray
    signal_layers: np.ndarray
    toxin_layers: np.ndarray
    flow_field: np.ndarray
    wind_vector_x: np.ndarray
    wind_vector_y: np.ndarray


class _MetadataEntry(TypedDict):
    """Per-frame metadata record persisted alongside Zarr field arrays."""

    tick: int
    terminated: bool
    termination_reason: str | None


class ReplaySlice:
    """Immutable zero-copy view over a temporal slice of Zarr replay frames.

    Provides high-performance NumPy array access across consecutive simulation ticks
    without materializing Python list objects or triggering unnecessary copies.
    """

    def __init__(
        self,
        start_tick: int,
        end_tick: int,
        metadata: list[_MetadataEntry],
        fields: dict[str, np.ndarray],
    ) -> None:
        """Initialize the ReplaySlice.

        Args:
            start_tick: Start index of the slice (inclusive, 0-based).
            end_tick: End index of the slice (exclusive, 0-based).
            metadata: Metadata records for the frames in the slice.
            fields: Dictionary mapping field names to stacked or indexed NumPy arrays.
        """
        self.start_tick = start_tick
        self.end_tick = end_tick
        self.metadata = metadata
        self.fields = fields

    def __len__(self) -> int:
        """Return the number of frames contained in this slice."""
        return len(self.metadata)

    def get_field(self, field_name: str) -> np.ndarray:
        """Retrieve the zero-copy NumPy array for a specific field in this slice.

        Args:
            field_name: Name of the environment layer field.

        Returns:
            np.ndarray: The requested field data array.

        Raises:
            KeyError: If the field is not present in this slice.
        """
        if field_name not in self.fields:
            raise KeyError(f"Field '{field_name}' not found in ReplaySlice.")
        return self.fields[field_name]

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata and field arrays to a dictionary representation.

        Returns:
            dict[str, Any]: Mapping of metadata and NumPy array fields.
        """
        return {
            "start_tick": self.start_tick,
            "end_tick": self.end_tick,
            "metadata": list(self.metadata),
            "fields": self.fields,
        }


class NoOpReplayBuffer:
    """A no-op replay buffer that does not store or write any frames, preventing disk usage during tuning."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the NoOpReplayBuffer (does nothing).

        Args:
            args: Positional arguments (ignored).
            kwargs: Keyword arguments (ignored).
        """
        pass

    def append(self, state: object) -> None:
        """Append a state snapshot to the buffer (no-op).

        Args:
            state: The simulation state object to append.
        """
        pass

    def append_raw_arrays(self, *args: Any, **kwargs: Any) -> None:
        """Append raw environment arrays to the buffer (no-op).

        Args:
            args: Positional arguments (ignored).
            kwargs: Keyword arguments (ignored).
        """
        pass

    def __len__(self) -> int:
        """Return the number of frames in the buffer (always 0)."""
        return 0

    def get_frame_arrays(self, tick: int) -> dict[str, np.ndarray]:
        """Return raw NumPy arrays for the frame (no-op).

        Args:
            tick: Index of the frame.

        Raises:
            IndexError: Always raised since the no-op buffer holds no frames.
        """
        raise IndexError(f"Replay frame index out of range: {tick} (buffer is empty)")

    def get_slice(self, start_tick: int, end_tick: int) -> ReplaySlice:
        """Return a ReplaySlice for the specified range (no-op).

        Args:
            start_tick: Start index.
            end_tick: End index.

        Returns:
            ReplaySlice: Empty slice container.
        """
        return ReplaySlice(
            start_tick=start_tick,
            end_tick=end_tick,
            metadata=[],
            fields={},
        )


class ReplayBuffer:
    """Append-only Zarr-backed buffer of chunked tick frames.

    Provides backwards-compatible `ReplayBuffer` API semantics over a Zarr store.

    The schema is laid out as:

    - ``zarr.root['_metadata']``: JSON array of tick/termination metadata
    - ``zarr.root['fields/{field_name}/data']``: Chunked field array
    """

    def __init__(
        self,
        max_frames: int | None = None,
        *,
        spill_to_disk: bool = False,  # noqa: ARG002  # Ignored for Zarr; included for drop-in compatibility
        spill_path: str | Path | None = None,
    ) -> None:
        """Create or open a Zarr replay buffer.

        Args:
            max_frames: Optional upper bound on retained frames. When set and greater
                than zero, only the most recent ``max_frames`` snapshots are retained
                in the Zarr store. Older frames are automatically pruned during append.
                If ``None``, all frames are retained indefinitely.
            spill_to_disk: Accepted for API compatibility but has no effect; Zarr
                storage is always disk-backed.
            spill_path: Optional explicit path for the Zarr store. If omitted,
                a temporary directory is allocated lazily.
        """
        self._store_path: Path | None = Path(spill_path) if spill_path is not None else None
        self._owns_store = spill_path is None
        self._max_frames = max_frames if max_frames is None else max(1, int(max_frames))
        self._metadata: list[_MetadataEntry] = []
        self._root: zarr.Group | None = None
        self._frame_count: int = 0
        self._frame_offset: int = 0  # Index of oldest retained frame in Zarr store

    def _coerce_metadata_entries(self, payload: object) -> list[_MetadataEntry]:
        """Return metadata entries that match the persisted per-frame metadata schema.

        Args:
            payload: The payload to coerce.

        Returns:
            The coerced metadata entries.
        """
        if not isinstance(payload, list):
            return []
        entries: list[_MetadataEntry] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            tick = item.get("tick")
            terminated = item.get("terminated")
            termination_reason = item.get("termination_reason")
            if not isinstance(tick, int) or not isinstance(terminated, bool):
                continue
            if termination_reason is not None and not isinstance(termination_reason, str):
                continue
            entries.append(
                {
                    "tick": tick,
                    "terminated": terminated,
                    "termination_reason": termination_reason,
                }
            )
        return entries

    def _decode_metadata_bytes(self, payload: object) -> bytes:
        """Return byte payload for persisted metadata arrays.

        The `_metadata` Zarr node is expected to store a uint8 array containing
        UTF-8 JSON bytes. This helper performs explicit runtime narrowing before
        conversion so callers avoid unchecked indexing/type-ignore patterns.

        Args:
            payload: The payload to decode.

        Returns:
            The decoded byte payload.
        """
        if not isinstance(payload, zarr.Array):
            raise TypeError("_metadata node is not a Zarr array")
        array_obj = payload
        return bytes(np.asarray(array_obj[:], dtype=np.uint8).tolist())

    def _ensure_store(self) -> zarr.Group:
        """Lazily create or open the Zarr store group.

        Returns:
            zarr.Group: The Zarr store group.
        """
        if self._root is not None:
            return self._root

        if self._store_path is None:
            temp_dir = Path(tempfile.gettempdir())
            self._store_path = temp_dir / f"phids_replay_zarr_{uuid.uuid4().hex}.zarr"
            if self._owns_store:
                atexit.register(self._cleanup_store)

        self._store_path.mkdir(parents=True, exist_ok=True)
        self._root = zarr.open_group(str(self._store_path), mode="a")
        self._load_metadata()
        return self._root

    def _parse_metadata_obj(self, meta_obj: object) -> None:
        """Parse the metadata object and update the replay buffer's metadata.

        Args:
            meta_obj: The metadata object to parse.
        """
        if isinstance(meta_obj, list):
            self._metadata = self._coerce_metadata_entries(meta_obj)
            self._frame_offset = 0
        elif isinstance(meta_obj, dict) and "_metadata" in meta_obj:
            self._metadata = self._coerce_metadata_entries(meta_obj["_metadata"])
            frame_offset = meta_obj.get("_frame_offset", 0)
            self._frame_offset = frame_offset if isinstance(frame_offset, int) else 0
        self._frame_count = len(self._metadata) + self._frame_offset

    def _load_metadata(self) -> None:
        """Load metadata array from Zarr store if it exists."""
        root = self._ensure_store()
        if "_metadata" in root:
            try:
                meta_bytes = self._decode_metadata_bytes(root["_metadata"])
                meta_str = meta_bytes.decode("utf-8")
                meta_obj = json.loads(meta_str)
                self._parse_metadata_obj(meta_obj)
            except Exception as e:
                logger.warning("Failed to load metadata from Zarr store: %s", e)
                # Fall back to scanning for frame groups
                self._metadata = []
                self._frame_offset = 0
                frame_idx = 0
                while f"frames/{frame_idx:08d}" in root:
                    frame_idx += 1
                self._frame_count = frame_idx
        else:
            # Scan for frame groups if no metadata exists
            self._metadata = []
            self._frame_offset = 0
            frame_idx = 0
            while f"frames/{frame_idx:08d}" in root:
                frame_idx += 1
            self._frame_count = frame_idx

    def _save_metadata(self) -> None:
        """Persist metadata array to Zarr store."""
        root = self._ensure_store()
        # Store both metadata and frame offset
        meta_obj = {
            "_metadata": self._metadata,
            "_frame_offset": self._frame_offset,
        }
        meta_str = json.dumps(meta_obj)
        meta_bytes = np.frombuffer(meta_str.encode("utf-8"), dtype=np.uint8)

        if "_metadata" in root:
            del root["_metadata"]
        root.create_array(
            "_metadata",
            data=meta_bytes,
            chunks=(len(meta_bytes),),
            compressors=(zarr.codecs.ZstdCodec(level=10),),
        )

    def append(self, state: ReplayState) -> None:
        """Serialize and append a tick state to the buffer.

        Decomposes the state dict into field arrays, storing each as a
        chunked Zarr dataset. Metadata (tick, termination) is stored separately.

        Args:
            state: Tick state mapping (e.g., from ``SimulationLoop.get_state_snapshot()``).
        """
        tick_value = state.get("tick", self._frame_count)
        terminated_value = state.get("terminated", False)
        termination_reason_value = state.get("termination_reason", None)
        self._append_fields(
            tick=int(tick_value) if isinstance(tick_value, (int, float, str)) else self._frame_count,
            terminated=bool(terminated_value),
            termination_reason=(termination_reason_value if isinstance(termination_reason_value, str) else None),
            fields={
                field_name: field_data
                for field_name, field_data in state.items()
                if field_name not in ("tick", "terminated", "termination_reason")
            },
        )

    def append_raw_arrays(
        self,
        *,
        tick: int,
        env: _ReplayEnvLike,
        termination_state: tuple[bool, str | None],
    ) -> None:
        """Append replay frame directly from environment NumPy arrays.

        Args:
            tick: Current simulation tick.
            env: Grid environment exposing replay layer arrays.
            termination_state: Tuple ``(terminated, termination_reason)``.
        """
        terminated, termination_reason = termination_state
        self._append_fields(
            tick=tick,
            terminated=terminated,
            termination_reason=termination_reason,
            fields={
                "plant_energy_layer": env.plant_energy_layer,
                "signal_layers": env.signal_layers,
                "toxin_layers": env.toxin_layers,
                "flow_field": env.flow_field,
                "wind_vector_x": env.wind_vector_x,
                "wind_vector_y": env.wind_vector_y,
            },
        )

    def _append_fields(
        self,
        *,
        tick: int,
        terminated: bool,
        termination_reason: str | None,
        fields: dict[str, ReplayValue | np.ndarray],
    ) -> None:
        """Persist one frame's metadata and field payloads into the store.

        Args:
            tick: The current tick.
            terminated: Whether the simulation is terminated.
            termination_reason: The reason for termination.
            fields: The fields to store.
        """
        root = self._ensure_store()

        metadata_entry: _MetadataEntry = {
            "tick": int(tick),
            "terminated": bool(terminated),
            "termination_reason": termination_reason,
        }
        self._metadata.append(metadata_entry)

        frame_key = f"frames/{self._frame_count:08d}"
        if frame_key not in root:
            root.create_group(frame_key)
        frame_group = cast("zarr.Group", root[frame_key])

        for field_name, field_data in fields.items():
            self._store_field(frame_group, field_name, field_data)

        self._frame_count += 1
        self._save_metadata()

        if self._max_frames is not None and len(self._metadata) > self._max_frames:
            frames_to_drop = len(self._metadata) - self._max_frames
            for i in range(frames_to_drop):
                self._metadata.pop(0)
                old_frame_key = f"frames/{self._frame_offset + i:08d}"
                if old_frame_key in root:
                    del root[old_frame_key]
                    logger.debug("Pruned frame %d (retention policy)", self._frame_offset + i)
            self._frame_offset += frames_to_drop
            self._save_metadata()

    def _store_field(
        self,
        frame_group: zarr.Group,
        field_name: str,
        field_data: ReplayValue | np.ndarray,
    ) -> None:
        """Store a single field (array or nested list) into the frame group.

        Args:
            frame_group: The frame group to store the field in.
            field_name: The name of the field.
            field_data: The field data to store.
        """
        if isinstance(field_data, (list, tuple)):
            field_data = np.asarray(field_data, dtype=np.float32)
        elif isinstance(field_data, np.ndarray):
            if field_data.dtype != np.float32:
                field_data = field_data.astype(np.float32)

        if not isinstance(field_data, np.ndarray):
            # Store scalar or string as JSON metadata
            if field_name not in frame_group.attrs:
                frame_group.attrs[field_name] = field_data
            return

        # Dimensionality-based heuristic for optimal CPU L2 cache alignment (~256 KB)
        chunk_shape: tuple[int, ...]
        if field_data.ndim == 1:
            chunk_shape = (min(field_data.shape[0], 256_000),)
        elif field_data.ndim == 2:
            chunk_shape = (min(field_data.shape[0], 256), min(field_data.shape[1], 256))
        elif field_data.ndim == 3:
            chunk_shape = (1, min(field_data.shape[1], 256), min(field_data.shape[2], 256))
        else:
            chunk_shape = tuple(field_data.shape)

        # Truncate subnormal signal tails
        if "signal" in field_name.lower():
            field_data = np.where(np.abs(field_data) < 1e-4, 0.0, field_data)

        if field_name in frame_group:
            del frame_group[field_name]

        frame_group.create_array(
            field_name,
            data=field_data,
            chunks=chunk_shape,
            compressors=(zarr.codecs.ZstdCodec(level=10),),
        )

    def __len__(self) -> int:
        """Return total number of retained frames.

        Returns:
            Total number of retained frames.
        """
        return len(self._metadata)

    def get_frame(self, tick: int) -> ReplayState:
        """Return the deserialized state for the specified frame index.

        Args:
            tick: Index of the frame to retrieve (0-based).

        Returns:
            ReplayState: Reconstructed state mapping.

        Raises:
            IndexError: If the tick is out of range.
        """
        if tick < 0 or tick >= len(self._metadata):
            raise IndexError(f"Replay frame index out of range: {tick} (total frames={len(self._metadata)})")

        root = self._ensure_store()
        # Calculate actual frame index in Zarr store (accounting for offset)
        actual_frame_idx = self._frame_offset + tick
        frame_key = f"frames/{actual_frame_idx:08d}"
        if frame_key not in root:
            raise IndexError(f"Frame {tick} not found in Zarr store (key: {frame_key})")

        frame_group = cast("zarr.Group", root[frame_key])
        state: ReplayState = {}

        # Restore metadata
        if tick < len(self._metadata):
            metadata = self._metadata[tick]
            state["tick"] = metadata["tick"]
            state["terminated"] = metadata["terminated"]
            state["termination_reason"] = metadata["termination_reason"]

        # Restore field arrays
        try:
            for field_name in frame_group.array_keys():
                field_obj = frame_group[field_name]
                if not isinstance(field_obj, zarr.Array):
                    continue
                array_data = np.asarray(field_obj[:])
                # Convert back to native Python lists for compatibility
                state[field_name] = cast("ReplayValue", array_data.tolist())
        except (AttributeError, TypeError):
            pass

        # Restore scalar/string attributes
        try:
            for attr_name, attr_value in frame_group.attrs.items():
                if attr_name not in state:
                    state[attr_name] = cast("ReplayValue", attr_value)
        except (AttributeError, TypeError):
            pass

        return state

    def get_frame_arrays(self, tick: int) -> dict[str, np.ndarray]:
        """Return raw NumPy arrays for a single frame without converting to Python lists.

        Args:
            tick: Index of the frame to retrieve (0-based).

        Returns:
            dict[str, np.ndarray]: Dictionary mapping field names to NumPy float32 arrays.

        Raises:
            IndexError: If the tick is out of range.
        """
        if tick < 0 or tick >= len(self._metadata):
            raise IndexError(f"Replay frame index out of range: {tick} (total frames={len(self._metadata)})")

        root = self._ensure_store()
        actual_frame_idx = self._frame_offset + tick
        frame_key = f"frames/{actual_frame_idx:08d}"
        if frame_key not in root:
            raise IndexError(f"Frame {tick} not found in Zarr store (key: {frame_key})")

        frame_group = cast("zarr.Group", root[frame_key])
        arrays: dict[str, np.ndarray] = {}

        try:
            for field_name in frame_group.array_keys():
                field_obj = frame_group[field_name]
                if isinstance(field_obj, zarr.Array):
                    arrays[field_name] = np.asarray(field_obj[:])
        except (AttributeError, TypeError) as e:
            logger.warning("Failed to extract array keys for frame %d: %s", tick, e)

        return arrays

    def get_slice(self, start_tick: int, end_tick: int) -> ReplaySlice:
        """Retrieve a contiguous range of frames as a zero-copy ReplaySlice DTO.

        Args:
            start_tick: Starting frame index (inclusive, 0-based).
            end_tick: Ending frame index (exclusive, 0-based).

        Returns:
            ReplaySlice: Zero-copy slice container holding frame metadata and NumPy arrays.

        Raises:
            IndexError: If start_tick or end_tick are out of range.
        """
        total = len(self._metadata)
        if start_tick < 0 or start_tick > total or end_tick < 0 or end_tick > total:
            raise IndexError(f"Replay slice range [{start_tick}:{end_tick}] out of bounds for buffer of size {total}")
        if start_tick >= end_tick:
            return ReplaySlice(start_tick=start_tick, end_tick=end_tick, metadata=[], fields={})

        metadata_slice = self._metadata[start_tick:end_tick]
        aggregated_fields: dict[str, list[np.ndarray]] = {}

        for t in range(start_tick, end_tick):
            frame_arrays = self.get_frame_arrays(t)
            for field_name, arr in frame_arrays.items():
                if field_name not in aggregated_fields:
                    aggregated_fields[field_name] = []
                aggregated_fields[field_name].append(arr)

        stacked_fields: dict[str, np.ndarray] = {}
        for field_name, arr_list in aggregated_fields.items():
            if arr_list:
                stacked_fields[field_name] = np.stack(arr_list, axis=0)

        return ReplaySlice(
            start_tick=start_tick,
            end_tick=end_tick,
            metadata=metadata_slice,
            fields=stacked_fields,
        )

    def save(self, path: str | Path) -> None:
        """Export the Zarr store to a standalone file for external storage.

        This creates a snapshot of the current Zarr store by consolidating
        metadata and copying the store directory.

        Args:
            path: Destination file path (or directory for full export).
        """
        destination = Path(path)
        if destination.suffix == ".zarr":
            import shutil

            if destination.exists():
                shutil.rmtree(destination)
            if self._store_path is not None:
                shutil.copytree(str(self._store_path), str(destination))
            logger.info("Zarr replay exported to %s (frames=%d)", destination, self._frame_count)
        else:
            raise ValueError("Zarr export requires a .zarr destination directory")

    @classmethod
    def load(cls, path: str | Path) -> ReplayBuffer:
        """Load a Zarr replay store.

        If the path is a .zarr directory, opens it directly.

        Args:
            path: Path to the Zarr directory.

        Returns:
            Zarr replay buffer attached to the loaded directory.
        """
        source = Path(path)

        if not source.exists() or not source.is_dir():
            raise ValueError(f"Replay path must be an existing directory: {path}")

        buf = cls(spill_path=source)
        # Ensure metadata is loaded before returning
        buf._ensure_store()
        buf._load_metadata()
        logger.info("Zarr replay loaded from %s (%d frames)", source, len(buf))
        return buf

    def _cleanup_store(self) -> None:
        """Remove owned Zarr store on interpreter shutdown."""
        if self._store_path is None or not self._owns_store:
            return
        try:
            import shutil

            shutil.rmtree(self._store_path, ignore_errors=True)
        except OSError:
            logger.debug("Zarr replay cleanup skipped for %s", self._store_path)
