"""Experimental validation suite for test biotope diffusion.

This module defines hypothesis-driven checks for deterministic ecosystem behavior, API constraints, and simulation invariants. The tests map computational rules to biological interpretations, including metabolic attrition, trigger-gated signaling, and O(1) spatial locality assumptions, to ensure that implementation details remain aligned with the PHIDS scientific model.
"""

from __future__ import annotations

from phids.engine.core.biotope import GridEnvironment


def test_signal_diffusion_applies_threshold() -> None:
    """Validates the signal diffusion applies threshold invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    env = GridEnvironment(width=6, height=6, num_signals=1, num_toxins=1)
    env.signal_layers[0, 2, 2] = 1e-6

    env.diffuse_signals()

    assert float(env.signal_layers[0].sum()) == 0.0


def test_signal_diffusion_wind_does_not_wrap_across_edges() -> None:
    """Validates the signal diffusion wind does not wrap across edges invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    env = GridEnvironment(width=6, height=6, num_signals=1, num_toxins=1)
    env.signal_layers[0, 5, 3] = 1.0
    env.set_uniform_wind(1.0, 0.0)

    env.diffuse_signals()

    assert float(env.signal_layers[0, 0, :].sum()) == 0.0


def test_signal_diffusion_fast_path_clears_stale_write_buffer_state() -> None:
    """Validates the signal diffusion fast path clears stale write-buffer state when a layer becomes quiescent.

    The diffusion routine may skip convolution for layers whose concentrations fall entirely below the
    sparsity threshold. This optimization remains scientifically valid only if the skipped branch also
    clears the write buffer, because otherwise the subsequent double-buffer swap could resurrect stale
    concentration mass from a previous tick. The present regression therefore seeds a non-zero signal,
    diffuses once, manually quiesces the read layer, and verifies that a second diffusion pass yields a
    strictly zero field rather than a ghost plume.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.
    """
    env = GridEnvironment(width=6, height=6, num_signals=1, num_toxins=1)
    env.signal_layers[0, 2, 2] = 1.0

    env.diffuse_signals()
    env.signal_layers[0].fill(0.0)
    env.diffuse_signals()

    assert float(env.signal_layers[0].sum()) == 0.0
