"""Replay I/O: msgpack binary serialisation of per-tick state buffers.

Each tick state is serialised to a compact binary frame using msgpack,
enabling deterministic re-simulation and comprehensive event logging.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import msgpack  # type: ignore[import-untyped]


def serialise_state(state: dict[str, Any]) -> bytes:
    """Serialise a state snapshot dict to a msgpack binary frame.

    Parameters
    ----------
    state:
        Tick state dict (e.g., from
        :meth:`~phytodynamics.engine.loop.SimulationLoop.get_state_snapshot`).

    Returns
    -------
    bytes
        Compact msgpack-encoded binary representation.
    """
    return msgpack.packb(state, use_bin_type=True)  # type: ignore[no-any-return]


def deserialise_state(data: bytes) -> dict[str, Any]:
    """Decode a msgpack binary frame back to a state snapshot dict.

    Parameters
    ----------
    data:
        msgpack-encoded bytes produced by :func:`serialise_state`.

    Returns
    -------
    dict[str, Any]
        Decoded state mapping.
    """
    result: dict[str, Any] = msgpack.unpackb(data, raw=False)
    return result


class ReplayBuffer:
    """Append-only buffer of binary-serialised tick frames.

    Supports writing to and reading from a binary replay file for
    deterministic re-simulation.
    """

    def __init__(self) -> None:
        self._frames: list[bytes] = []

    def append(self, state: dict[str, Any]) -> None:
        """Serialise and append one tick state to the buffer."""
        self._frames.append(serialise_state(state))

    def __len__(self) -> int:
        return len(self._frames)

    def get_frame(self, tick: int) -> dict[str, Any]:
        """Return the deserialised state for a given tick index."""
        return deserialise_state(self._frames[tick])

    def save(self, path: str | Path) -> None:
        """Write all frames to a binary replay file.

        File format: [4-byte little-endian frame length][frame bytes] repeated.
        """
        with Path(path).open("wb") as fp:
            for frame in self._frames:
                length = len(frame).to_bytes(4, "little")
                fp.write(length)
                fp.write(frame)

    @classmethod
    def load(cls, path: str | Path) -> ReplayBuffer:
        """Load a replay file produced by :meth:`save`.

        Parameters
        ----------
        path:
            Path to the binary replay file.

        Returns
        -------
        ReplayBuffer
            Populated buffer ready for re-simulation.
        """
        buf = cls()
        with Path(path).open("rb") as fp:
            while True:
                length_bytes = fp.read(4)
                if len(length_bytes) < 4:
                    break
                length = int.from_bytes(length_bytes, "little")
                frame = fp.read(length)
                if len(frame) < length:
                    break
                buf._frames.append(frame)
        return buf
