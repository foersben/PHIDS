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

import logging
from pathlib import Path
from typing import Any

import msgpack  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


def serialise_state(state: dict[str, Any]) -> bytes:
    """Serialise a state snapshot to a msgpack frame.

    Args:
        state: Tick state mapping (for example, the output of
            ``SimulationLoop.get_state_snapshot()``).

    Returns:
        bytes: msgpack-encoded frame.
    """
    return msgpack.packb(state, use_bin_type=True)  # type: ignore[no-any-return]


def deserialise_state(data: bytes) -> dict[str, Any]:
    """Deserialize a msgpack frame into a state mapping.

    Args:
        data: msgpack-encoded bytes produced by :func:`serialise_state`.

    Returns:
        dict[str, Any]: Decoded state mapping.
    """
    result: dict[str, Any] = msgpack.unpackb(data, raw=False)
    return result


class ReplayBuffer:
    """Append-only buffer of binary-serialised tick frames.

    Supports writing to and reading from a binary replay file for
    deterministic re-simulation.
    """

    def __init__(self) -> None:
        """Create an empty replay buffer.

        The buffer stores msgpack-serialised frames in an append-only list.
        """
        self._frames: list[bytes] = []

    def append(self, state: dict[str, Any]) -> None:
        """Serialize and append a tick state to the buffer.

        Args:
            state: Tick state mapping to serialize and store.
        """
        self._frames.append(serialise_state(state))

    def __len__(self) -> int:
        """Return number of stored frames."""
        return len(self._frames)

    def get_frame(self, tick: int) -> dict[str, Any]:
        """Return the deserialised state for the specified tick index.

        Args:
            tick: Index of the frame to retrieve (0-based).

        Returns:
            dict[str, Any]: Decoded state mapping for the requested tick.
        """
        return deserialise_state(self._frames[tick])

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
