"""Unit tests for deterministic per-tick state serialisation and msgpack roundtrip fidelity.

This module validates that :func:`~phids.io.replay.serialise_state` and
:func:`~phids.io.replay.deserialise_state` form a lossless roundtrip for representative tick
state dictionaries. The hypothesis is that nested Python structures — including scalar
integers, booleans, and nested lists of floating-point values representing NumPy layer data —
are preserved byte-for-byte through the msgpack encode-decode cycle, ensuring that replay
files can be loaded on any supported interpreter without data corruption or type coercion.
"""

from __future__ import annotations

from phids.io.replay import deserialise_state, serialise_state


def test_replay_roundtrip_msgpack() -> None:
    """Verifies that serialise_state and deserialise_state form a lossless msgpack roundtrip.

    A representative tick state dict is encoded and immediately decoded. The decoded dict must
    compare equal to the original, confirming that all field types (int, bool, nested lists)
    survive the msgpack encode-decode cycle without type coercion or value loss.
    """
    state = {
        "tick": 10,
        "terminated": False,
        "plant_energy_layer": [[0.0, 1.2], [2.3, 0.0]],
        "signal_layers": [[[0.0, 0.1], [0.0, 0.0]]],
    }

    encoded = serialise_state(state)
    decoded = deserialise_state(encoded)

    assert decoded == state
