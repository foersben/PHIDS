from __future__ import annotations

from phids.io.replay import deserialise_state, serialise_state


def test_replay_roundtrip_msgpack() -> None:
    state = {
        "tick": 10,
        "terminated": False,
        "plant_energy_layer": [[0.0, 1.2], [2.3, 0.0]],
        "signal_layers": [[[0.0, 0.1], [0.0, 0.0]]],
    }

    encoded = serialise_state(state)
    decoded = deserialise_state(encoded)

    assert decoded == state
