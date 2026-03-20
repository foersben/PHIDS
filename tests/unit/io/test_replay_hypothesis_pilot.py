"""Bounded Hypothesis pilot for replay frame round-trip invariants."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from phids.io.replay import deserialise_state, serialise_state

try:
    from hypothesis import given, settings, strategies as st
except ModuleNotFoundError:
    pytest.skip("Install hypothesis to run optional property pilots.", allow_module_level=True)


def _matrix_strategy(max_size: int = 4):
    """Return a bounded square-matrix strategy using finite sampled float values."""
    values = st.sampled_from((0.0, 0.1, 0.25, 0.5, 1.0))
    return st.integers(min_value=1, max_value=max_size).flatmap(
        lambda size: st.lists(
            st.lists(values, min_size=size, max_size=size),
            min_size=size,
            max_size=size,
        )
    )


@pytest.mark.hypothesis_pilot
@settings(max_examples=96, deadline=None, derandomize=True)
@given(
    tick=st.integers(min_value=0, max_value=512),
    terminated=st.booleans(),
    state_revision=st.integers(min_value=0, max_value=512),
    plant_energy_layer=_matrix_strategy(),
    flow_field=_matrix_strategy(),
    wind_vector_x=_matrix_strategy(),
    wind_vector_y=_matrix_strategy(),
)
def test_serialise_deserialise_roundtrip_preserves_state_payload(
    tick: int,
    terminated: bool,
    state_revision: int,
    plant_energy_layer: list[list[float]],
    flow_field: list[list[float]],
    wind_vector_x: list[list[float]],
    wind_vector_y: list[list[float]],
) -> None:
    """Replay frame serialization preserves bounded snapshot payloads without structural drift."""
    width = len(plant_energy_layer)
    height = len(plant_energy_layer[0])

    # Keep layer families shape-aligned with grid dimensions for valid snapshot semantics.
    signal_layer = [[0.0 for _ in range(height)] for _ in range(width)]
    toxin_layer = [[0.0 for _ in range(height)] for _ in range(width)]
    state = {
        "tick": tick,
        "terminated": terminated,
        "termination_reason": "done" if terminated else None,
        "state_revision": state_revision,
        "plant_energy_layer": plant_energy_layer,
        "signal_layers": [signal_layer],
        "toxin_layers": [toxin_layer],
        "flow_field": flow_field,
        "wind_vector_x": wind_vector_x,
        "wind_vector_y": wind_vector_y,
    }

    decoded = deserialise_state(serialise_state(state))

    assert decoded == state


@pytest.mark.hypothesis_pilot
@settings(max_examples=72, deadline=None, derandomize=True)
@given(
    values=st.lists(st.integers(min_value=0, max_value=10_000), min_size=1, max_size=16),
    max_frames=st.integers(min_value=1, max_value=16),
)
def test_replay_buffer_spill_and_save_load_preserve_ordered_frames(
    values: list[int],
    max_frames: int,
) -> None:
    """Replay spill mode preserves frame order and payload integrity through save/load boundaries."""
    from phids.io.replay import ReplayBuffer

    states = [
        {
            "tick": tick,
            "value": value,
        }
        for tick, value in enumerate(values)
    ]

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        spill_path = root / "spill.bin"
        merged_path = root / "merged.replay"

        replay = ReplayBuffer(max_frames=max_frames, spill_to_disk=True, spill_path=spill_path)
        for state in states:
            replay.append(state)

        assert len(replay) == len(states)
        if len(states) > max_frames:
            assert spill_path.exists()

        for idx, expected in enumerate(states):
            assert replay.get_frame(idx) == expected

        replay.save(merged_path)
        reloaded = ReplayBuffer.load(merged_path)
        assert len(reloaded) == len(states)
        for idx, expected in enumerate(states):
            assert reloaded.get_frame(idx) == expected
