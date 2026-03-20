"""Deterministic per-tick state serialisation for PHIDS replay and re-simulation.

This module implements the binary frame store used to record and replay ``SimulationLoop`` state
snapshots. Each tick's state dictionary — containing grid dimensions, plant energy layers, signal
layers, toxin layers, flow-field gradients, and wind vectors — is encoded as a compact msgpack
frame and appended to an in-memory :class:`ReplayBuffer`. The frame format prefixes each payload
with a 4-byte little-endian length field to enable sequential reading from arbitrarily long replay
files without scanning for frame boundaries.

The :class:`ReplayBuffer` is intentionally append-only in the forward direction: frames are
accumulated during a live simulation run and may be serialised to disk via :meth:`ReplayBuffer.save`
for post-hoc analysis, deterministic re-simulation seeding, or WebSocket replay streaming. The
``msgpack`` encoding is chosen for its byte-efficiency relative to JSON and its absence of any
Python-specific serialisation assumptions, making replay files portable across interpreter
versions. Nested NumPy arrays are serialised as nested Python lists by ``SimulationLoop.get_state_snapshot``
before being passed to this module; the replay module itself has no NumPy dependency, preserving
its role as a pure I/O boundary.
"""

from __future__ import annotations

import atexit
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Protocol, TypeAlias, cast

import msgpack  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

ReplayScalar: TypeAlias = None | bool | int | float | str
ReplayValue: TypeAlias = ReplayScalar | list["ReplayValue"] | dict[str, "ReplayValue"]
ReplayState: TypeAlias = dict[str, ReplayValue]


class _ReplayArrayLike(Protocol):
    """Structural contract for array payloads that can be serialized through tolist()."""

    def tolist(self) -> object: ...


class _ReplayEnvLike(Protocol):
    """Structural contract for environment layers consumed by append_raw_arrays."""

    plant_energy_layer: _ReplayArrayLike
    signal_layers: _ReplayArrayLike
    toxin_layers: _ReplayArrayLike
    flow_field: _ReplayArrayLike
    wind_vector_x: _ReplayArrayLike
    wind_vector_y: _ReplayArrayLike


def serialise_state(state: ReplayState) -> bytes:
    """Serialise a state snapshot to a msgpack frame.

    Args:
        state: Tick state mapping (for example, the output of
            ``SimulationLoop.get_state_snapshot()``).

    Returns:
        bytes: msgpack-encoded frame.
    """
    return cast(bytes, msgpack.packb(state, use_bin_type=True))


def deserialise_state(data: bytes) -> ReplayState:
    """Deserialize a msgpack frame into a state mapping.

    Args:
        data: msgpack-encoded bytes produced by :func:`serialise_state`.

    Returns:
        ReplayState: Decoded state mapping.
    """
    decoded = msgpack.unpackb(data, raw=False)
    if not isinstance(decoded, dict):
        raise ValueError("Replay frame payload must decode to a mapping.")
    return cast(ReplayState, decoded)


class ReplayBuffer:
    """Append-only buffer of binary-serialised tick frames.

    Supports writing to and reading from a binary replay file for
    deterministic re-simulation.
    """

    def __init__(
        self,
        max_frames: int | None = None,
        *,
        spill_to_disk: bool = False,
        spill_path: str | Path | None = None,
    ) -> None:
        """Create an empty replay buffer.

        The buffer stores msgpack-serialised frames in an append-only list.

        Args:
            max_frames: Optional upper bound on retained frames. When set,
                the oldest frames are discarded first after appends when
                ``spill_to_disk`` is disabled. When ``spill_to_disk`` is
                enabled, this value defines the in-memory cache size while
                older frames are written to disk.
            spill_to_disk: When ``True``, frames that age out of the in-memory
                cache are persisted to disk and remain addressable via
                :meth:`get_frame`.
            spill_path: Optional explicit path for the spill file. If omitted,
                a temporary file path is allocated lazily.
        """
        self._frames: list[bytes] = []
        self._max_frames = max_frames if max_frames is None else max(1, int(max_frames))
        self._spill_to_disk = spill_to_disk
        self._spilled_index: list[tuple[int, int]] = []
        self._spill_path: Path | None = Path(spill_path) if spill_path is not None else None
        self._owns_spill_file = spill_path is None

    def append(self, state: ReplayState) -> None:
        """Serialize and append a tick state to the buffer.

        Args:
            state: Tick state mapping to serialize and store.
        """
        self._frames.append(serialise_state(state))
        if self._max_frames is not None and len(self._frames) > self._max_frames:
            overflow = len(self._frames) - self._max_frames
            if self._spill_to_disk:
                for _ in range(overflow):
                    self._spill_frame(self._frames.pop(0))
            else:
                del self._frames[:overflow]

    def append_raw_arrays(
        self,
        *,
        tick: int,
        env: _ReplayEnvLike,
        termination_state: tuple[bool, str | None],
    ) -> None:
        """Append replay frame from environment arrays.

        This method decouples replay ingestion from UI snapshot generation. The
        fallback msgpack backend remains list-serialisation based, so arrays are
        converted to nested lists only at this replay boundary.

        Args:
            tick: Current simulation tick.
            env: Grid environment object exposing replay layer arrays.
            termination_state: Tuple ``(terminated, termination_reason)``.
        """
        terminated, termination_reason = termination_state
        state: ReplayState = {
            "tick": int(tick),
            "terminated": bool(terminated),
            "termination_reason": termination_reason,
            "plant_energy_layer": cast(ReplayValue, env.plant_energy_layer.tolist()),
            "signal_layers": cast(ReplayValue, env.signal_layers.tolist()),
            "toxin_layers": cast(ReplayValue, env.toxin_layers.tolist()),
            "flow_field": cast(ReplayValue, env.flow_field.tolist()),
            "wind_vector_x": cast(ReplayValue, env.wind_vector_x.tolist()),
            "wind_vector_y": cast(ReplayValue, env.wind_vector_y.tolist()),
        }
        self.append(state)

    def __len__(self) -> int:
        """Return number of stored frames."""
        return len(self._spilled_index) + len(self._frames)

    def get_frame(self, tick: int) -> ReplayState:
        """Return the deserialised state for the specified tick index.

        Args:
            tick: Index of the frame to retrieve (0-based).

        Returns:
            ReplayState: Decoded state mapping for the requested tick.
        """
        if tick < 0 or tick >= len(self):
            raise IndexError(f"Replay frame index out of range: {tick}")

        spilled_count = len(self._spilled_index)
        if tick < spilled_count:
            return deserialise_state(self._read_spilled_frame(tick))
        return deserialise_state(self._frames[tick - spilled_count])

    def _spill_frame(self, frame: bytes) -> None:
        """Persist one frame into the spill file and record its byte location."""
        spill_path = self._ensure_spill_path()
        with spill_path.open("ab") as fp:
            record_start = fp.tell()
            fp.write(len(frame).to_bytes(4, "little"))
            fp.write(frame)
        self._spilled_index.append((record_start + 4, len(frame)))

    def _read_spilled_frame(self, spilled_index: int) -> bytes:
        """Load a spilled frame payload by absolute spilled-frame index."""
        if self._spill_path is None:
            raise IndexError("Spill file is not available for requested frame")
        payload_offset, payload_length = self._spilled_index[spilled_index]
        with self._spill_path.open("rb") as fp:
            fp.seek(payload_offset)
            payload = fp.read(payload_length)
        if len(payload) != payload_length:
            raise IndexError("Spill frame could not be read completely")
        return payload

    def _ensure_spill_path(self) -> Path:
        """Create and return a spill file path if spilling is enabled."""
        if self._spill_path is None:
            temp_dir = Path(tempfile.gettempdir())
            self._spill_path = temp_dir / f"phids_replay_{uuid.uuid4().hex}.bin"
            if self._owns_spill_file:
                atexit.register(self._cleanup_spill_file)
        return self._spill_path

    def _cleanup_spill_file(self) -> None:
        """Remove owned spill file on interpreter shutdown when present."""
        if self._spill_path is None or not self._owns_spill_file:
            return
        try:
            self._spill_path.unlink(missing_ok=True)
        except OSError:
            logger.debug("Replay spill cleanup skipped for %s", self._spill_path)

    def save(self, path: str | Path) -> None:
        """Write all frames to a binary replay file.

        The file format is an append of records where each record begins with a
        4-byte little-endian unsigned integer describing the following frame
        length, immediately followed by the frame bytes.

        Args:
            path: Destination file path.
        """
        destination = Path(path)
        with destination.open("wb") as fp:
            if self._spill_path is not None and self._spill_path.exists() and self._spilled_index:
                fp.write(self._spill_path.read_bytes())
            for frame in self._frames:
                length = len(frame).to_bytes(4, "little")
                fp.write(length)
                fp.write(frame)
        logger.info("Replay saved to %s (%d frames)", destination, len(self._frames))

    @classmethod
    def load(cls, path: str | Path) -> ReplayBuffer:
        """Load a replay file produced by :meth:`save`.

        Args:
            path: Path to the binary replay file.

        Returns:
            ReplayBuffer: Populated buffer ready for re-simulation.
        """
        source = Path(path)
        buf = cls()
        with source.open("rb") as fp:
            while True:
                length_bytes = fp.read(4)
                if len(length_bytes) < 4:
                    break
                length = int.from_bytes(length_bytes, "little")
                frame = fp.read(length)
                if len(frame) < length:
                    logger.warning(
                        "Replay file %s ended mid-frame (expected=%d bytes, got=%d)",
                        source,
                        length,
                        len(frame),
                    )
                    break
                buf._frames.append(frame)
        logger.info("Replay loaded from %s (%d frames)", source, len(buf._frames))
        return buf
