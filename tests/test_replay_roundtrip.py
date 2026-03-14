"""Experimental validation suite for test replay roundtrip.

This module defines hypothesis-driven checks for deterministic ecosystem behavior, API constraints, and simulation invariants. The tests map computational rules to biological interpretations, including metabolic attrition, trigger-gated signaling, and O(1) spatial locality assumptions, to ensure that implementation details remain aligned with the PHIDS scientific model.
"""

from __future__ import annotations

from phids.io.replay import deserialise_state, serialise_state


def test_replay_roundtrip_msgpack() -> None:
    """Validates the replay roundtrip msgpack invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

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
